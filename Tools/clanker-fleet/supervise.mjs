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

/** Tasks in the spec, matched to their worker by title. */
function reconcile(spec) {
  const all = tasks();
  return spec.workers.map((w) => {
    const task = all.find((t) => t.title === w.title);
    const worker = task?.assigned_worker ? workers().find((x) => x.id === task.assigned_worker) : null;
    const receipt = worker?.results?.length ? worker.results[worker.results.length - 1] : null;
    const terminal = worker ? ["COMPLETE", "FAILED", "CANCELLED", "LOST"].includes(worker.status) : true;
    const stalled = worker && !terminal && !receipt &&
      Date.now() - new Date(worker.last_activity).getTime() > 25 * 60 * 1000;
    return {
      key: w.key, spec: w, task, worker,
      done: !!receipt,
      dead: !receipt && (terminal || stalled),
      why: !worker ? "never spawned" : receipt ? "" :
        stalled ? `stalled (no activity since ${worker.last_activity})` : worker.status,
      model: worker ? `${worker.provider}/${worker.model}` : null,
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
      console.log("  all tasks resolved - supervisor exiting");
      journal("supervisor-complete", {});
      op.child.kill();
      process.exit(0);
    }

    if (round >= MAX_ROUNDS) {
      console.log(`  reached --max-rounds ${MAX_ROUNDS}; leaving remaining tasks for a human`);
      journal("supervisor-out-of-rounds", { remaining: dead.map((d) => d.key) });
      break;
    }

    for (const row of dead) {
      console.log(`  reassigning ${row.key} (${row.why})`);
      await reassign(op, row, tried);
      await sleep(3000);
    }
    round++;

    console.log(`  sleeping ${INTERVAL_MIN}m`);
    await sleep(INTERVAL_MIN * 60 * 1000);
  }
  shutdown();
}

main().catch((e) => {
  journal("supervisor-error", { message: String(e) });
  console.error(e);
  process.exit(1);
});