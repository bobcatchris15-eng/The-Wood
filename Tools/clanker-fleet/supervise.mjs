#!/usr/bin/env node
/**
 * Squadron supervisor — keeps a squadron alive unattended.
 *
 * Why this is not optional
 * ------------------------
 * StatefulClanker ties worker lifetime to the operator process that spawned it:
 * on session_shutdown the extension stops every worker. So anything that goes
 * quiet is not "idle", it is orphaned. Two concrete unattended failures this
 * prevents:
 *
 *   1. A worker that ends its turn without calling worker_finish leaves no
 *      receipt. The task is silently lost - there is no timeout that notices.
 *   2. A worker that stops making progress keeps its task "active" forever.
 *
 * So: heartbeat on an interval, detect dead tasks, and re-dispatch them on a
 * different model. Tasks already tried on a model are not retried on it again.
 *
 * Usage
 *   node squadron.mjs supervise [spec.json] [--interval <minutes>] [--max-rounds <n>]
 *
 * Journal: .statefulclanker/squadron/heartbeat.log   (append-only)
 */

import { readFileSync, writeFileSync, appendFileSync, existsSync, mkdirSync, readdirSync } from "node:fs";
import { join } from "node:path";
import { spawnOperatorWithPipe, ask } from "./squadron-op.mjs";

const ROOT = process.cwd();
const SC = join(ROOT, ".statefulclanker");
const SQ = join(SC, "squadron");
const HB = join(SQ, "heartbeat.log");
const TRIED = join(SQ, "attempts.json");

const jread = (p, d) => { try { return JSON.parse(readFileSync(p, "utf8")); } catch { return d; } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const registry = () => jread(join(SC, "workers", "registry.json"), { next: 1, workers: {} });
const workers = () => Object.values(registry().workers);

/** Task records from all three status buckets. */
const tasks = () =>
  ["active", "complete", "cancelled"].flatMap((b) => {
    const dir = join(SC, "tasks", b);
    if (!existsSync(dir)) return [];
    return readdirSync(dir).filter((f) => f.endsWith(".json"))
      .map((f) => jread(join(dir, f), null)).filter(Boolean);
  });

const arg = (flag, def) => {
  const i = process.argv.indexOf(flag);
  return i > -1 && process.argv[i + 1] ? Number(process.argv[i + 1]) : def;
};
const SPEC = process.argv[3] && !process.argv[3].startsWith("--") ? process.argv[3] : "squadron.json";
const INTERVAL_MIN = arg("--interval", 30);
const MAX_ROUNDS = arg("--max-rounds", 3);

function journal(kind, data) {
  mkdirSync(SQ, { recursive: true });
  appendFileSync(HB, JSON.stringify({ ts: new Date().toISOString(), kind, ...data }) + "\n");
}

/**
 * Tasks in the spec, matched to every worker that ever attempted them.
 *
 * Earlier this matched only `task.assigned_worker`, which was a bug: a retried task
 * spawns a NEW task record, so each retry saw the original still-unassigned worker
 * and retried again. Three workers independently wrote the same 500-line design
 * because of it. Matching on title across ALL task buckets fixes it.
 */
function reconcile(spec) {
  const all = tasks();
  return spec.workers.map((w) => {
    const attempts = all.filter((t) => t.title.startsWith(w.title));
    const ws = attempts.map((t) => workers().find((x) => x.id === t.assigned_worker)).filter(Boolean);
    const receipts = ws.flatMap((x) => (x.results?.length ? [x.results[x.results.length - 1]] : []));
    const winner = ws.find((x) => x.results?.length);
    const stalled = ws.filter((x) => !x.results?.length &&
      !["COMPLETE", "FAILED", "CANCELLED", "LOST"].includes(x.status));
    const lastActivity = ws.length
      ? ws.map((x) => new Date(x.last_activity).getTime()).sort((a, b) => b - a)[0] : 0;
    const stalledRecently = stalled.length && Date.now() - lastActivity > 25 * 60 * 1000;
    const neverFinished = ws.filter((x) => !x.results?.length &&
      ["FAILED", "CANCELLED", "LOST"].includes(x.status));

    return {
      key: w.key, spec: w, attempts: attempts.length,
      worker: winner ?? ws[ws.length - 1] ?? null,
      done: receipts.length > 0,
      receipt: receipts[0] ?? null,
      // Only dead if NO attempt ever produced a receipt.
      dead: receipts.length === 0 && (ws.length === 0 || stalledRecently || neverFinished.length > 0),
      why: ws.length === 0 ? "never spawned"
        : receipts.length ? ""
        : stalledRecently ? `stalled (${ws.length} attempt(s), none active)`
        : `${neverFinished.length} attempt(s) died without a receipt`,
      model: winner ? `${winner.provider}/${winner.model}` : null,
    };
  });
}

async function reassign(op, row, tried) {
  const w = row.spec;
  // Never retry a model this task already failed on: free-tier failures are
  // usually the transport, and repeating it just burns quota.
  const candidates = Object.keys(tried[row.key] || {});
  const exclude = candidates.filter((m) => m !== undefined);
  const pin = w.model && !exclude.includes(w.model) ? w.model : undefined;

  const spec =
    `  assignment: ${JSON.stringify(w.assignment)}\n` +
    `  task_title: ${JSON.stringify(w.title + " (round " + ((tried[row.key]?.__n || 1) + 1) + ")")}\n` +
    `  ability_profile: ${w.profile || "implementation"}\n` +
    (pin ? `  model: ${JSON.stringify(pin)}\n` : `  (omit model - selection will pick an untried one)\n`) +
    `  worktree_required: ${w.worktree === false ? "false" : "true"}`;

  await ask(op,
    `Call worker_spawn exactly once with these parameters:\n${spec}\n` +
    `Reply with only the JSON worker_spawn returned. Do not poll the worker.`,
    `re-${row.key}-${Date.now()}`);

  // Give it time to appear. No worktree is seconds; a worktree is ~777 files.
  const before = workers().map((x) => x.id);
  const limit = (w.worktree === false ? 90000 : 240000);
  const start = Date.now();
  while (Date.now() - start < limit) {
    const fresh = workers().filter((x) => !before.includes(x.id));
    if (fresh.length) {
      const m = fresh[0];
      tried[row.key] = { ...(tried[row.key] || {}), __n: (tried[row.key]?.__n || 1) + 1 };
      tried[row.key][`${m.provider}/${m.model}`] = new Date().toISOString();
      writeFileSync(TRIED, JSON.stringify(tried, null, 2));
      journal("reassigned", { key: row.key, worker: m.id, model: `${m.provider}/${m.model}`, previous: row.model });
      return true;
    }
    await sleep(3000);
  }
  journal("reassign-failed", { key: row.key, why: row.why });
  return false;
}

async function main() {
  const spec = jread(join(ROOT, SPEC), { workers: [] });
  if (!spec.workers?.length) {
    console.error(`no workers in ${SPEC}`);
    process.exit(1);
  }
  mkdirSync(SQ, { recursive: true });
  const tried = jread(TRIED, {});
  journal("supervisor-start", { spec: SPEC, intervalMin: INTERVAL_MIN, maxRounds: MAX_ROUNDS });

  console.log(`supervising ${SPEC} (${spec.workers.length} tasks), heartbeat every ${INTERVAL_MIN}m`);
  console.log(`journal: ${HB}`);

  const op = await spawnOperatorWithPipe();
  journal("operator-up", { pid: op.child.pid });
  console.log(`operator pid ${op.child.pid}`);

  const shutdown = () => {
    journal("supervisor-stop", {});
    try { op.child.kill(); } catch { /* already gone */ }
    process.exit(0);
  };
  process.on("SIGINT", shutdown);
  process.on("SIGTERM", shutdown);

  let round = 0;
  for (;;) {
    const rows = reconcile(spec);
    const done = rows.filter((r) => r.done).length;
    const dead = rows.filter((r) => r.dead);
    const live = rows.filter((r) => !r.done && !r.dead);

    journal("heartbeat", {
      round,
      done,
      live: live.length,
      dead: dead.map((d) => ({ key: d.key, why: d.why, model: d.model })),
      workers: workers().map((w) => ({
        id: w.id, status: w.status, model: `${w.provider}/${w.model}`,
        name: w.display_name || null, last: w.last_activity,
      })),
    });

    console.log(
      `\n${new Date().toISOString().slice(0, 16).replace("T", " ")}  round ${round}  ` +
      `${done} done / ${live.length} live / ${dead.length} dead`,
    );
    for (const r of live) console.log(`  live  ${r.key.padEnd(20)} ${r.model} ${r.why}`);
    for (const r of dead) console.log(`  DEAD  ${r.key.padEnd(20)} ${r.model ?? "-"} ${r.why}`);

    if (!dead.length) {
      console.log("  all tasks resolved");
      await integrateAll();
      journal("supervisor-complete", {});
      op.child.kill();
      process.exit(0);
    }

    if (round >= MAX_ROUNDS) {
      console.log(`  reached --max-rounds ${MAX_ROUNDS}; leaving remaining tasks for a human`);
      journal("supervisor-out-of-rounds", { remaining: dead.map((d) => d.key) });
      break;
    }

    for (const row of rows) {
      if (row.done) continue;
      console.log(`  reassigning ${row.key} (${row.why})`);
      await reassign(op, row, tried);
      await sleep(3000);
    }
    round++;

    // Integrations are the operator's job, and skipping it is how six completed
    // workers produced zero artifacts on main. Do it every round.
    await integrateAll();

    console.log(`  sleeping ${INTERVAL_MIN}m`);
    await sleep(INTERVAL_MIN * 60 * 1000);
  }
  shutdown();
}

/** Copy every completed worker's uncommitted files onto the working tree. */
async function integrateAll() {
  const wtRoot = join(SC, "worktrees");
  if (!existsSync(wtRoot)) return;
  const { readdirSync, copyFileSync, mkdirSync } = await import("node:fs");
  const { dirname, join: pjoin } = await import("node:path");
  const { execFileSync } = await import("node:child_process");
  const done = new Set();

  for (const id of readdirSync(wtRoot)) {
    const wt = pjoin(wtRoot, id);
    if (!existsSync(pjoin(wt, ".git"))) continue;
    const w = workers().find((x) => x.id === id);
    if (!w?.results?.length) continue;           // only completed work
    let lines = [];
    try {
      lines = execFileSync("git", ["-C", wt, "status", "--porcelain"], { encoding: "utf8" })
        .split("\n").filter((l) => l.trim() && !l.includes(".clanker") && !l.includes("->"));
    } catch { continue; }
    for (const l of lines) {
      const rel = l.slice(3).trim().replace(/^"/, "").replace(/"$/, "");
      if (!rel) continue;
      const key = rel;
      if (done.has(key)) { journal("integrate-dup", { rel, skipped: true }); continue; }
      try {
        mkdirSync(dirname(pjoin(ROOT, rel)), { recursive: true });
        copyFileSync(pjoin(wt, rel), pjoin(ROOT, rel));
        done.add(key);
        journal("integrated", { worker: id, model: `${w.provider}/${w.model}`, file: rel });
        console.log(`  integrated ${rel}  (${id} ${w.provider}/${w.model})`);
      } catch (e) { journal("integrate-error", { worker: id, rel, message: String(e) }); }
    }
  }
}

main().catch((e) => {
  journal("supervisor-error", { message: String(e) });
  console.error(e);
  process.exit(1);
});