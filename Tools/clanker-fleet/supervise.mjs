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
// The spec is the first bare argument, not argv[3] -- argv[3] is often a flag.
// Getting this wrong once made the supervisor reconcile against a stale spec.
const SPEC = process.argv.slice(2).find((a) => !a.startsWith("--") && isNaN(Number(a))) || "squadron.json";
const INTERVAL_MIN = arg("--interval", 30);
const MAX_ROUNDS = arg("--max-rounds", 0);

function journal(kind, data) {
  mkdirSync(SQ, { recursive: true });
  appendFileSync(HB, JSON.stringify({ ts: new Date().toISOString(), kind, ...data }) + "\n");
}

const ACTIVE = new Set(["STARTING", "RUNNING", "WAITING", "BLOCKED"]);
const TERMINAL = new Set(["COMPLETE", "FAILED", "CANCELLED", "LOST"]);
/** IDLE means the turn ended without worker_finish: the agent is alive but done. */
const GAVE_UP = "IDLE";
const STALL_MS = 25 * 60 * 1000;

/**
 * Tasks in the spec, matched to every worker that ever attempted them.
 *
 * Two bugs lived here.
 *
 * 1. It matched only `task.assigned_worker`. A retried task spawns a NEW task
 *    record, so each retry saw the original unassigned worker and retried again
 *    - three workers independently wrote the same 500-line design. Matching on
 *    title across all buckets fixed that.
 *
 * 2. `neverFinished.length > 0` made a task permanently dead. One attempt dying
 *    poisoned the result forever, so a task with a healthy worker running RIGHT
 *    NOW was still reported dead and reassigned alongside it. A live worker must
 *    protect the task; only its own silence may retire it.
 */
function reconcile(spec) {
  const now = Date.now();
  const all = tasks();
  return spec.workers.map((w) => {
    const attempts = all.filter((t) => t.title.startsWith(w.title));
    const ws = attempts
      .map((t) => workers().find((x) => x.id === t.assigned_worker))
      .filter(Boolean);

    const receipts = ws.filter((x) => x.results?.length);
    const done = receipts.length > 0;

    const age = (x) => now - new Date(x.last_activity).getTime();
    const active = ws.filter((x) => ACTIVE.has(x.status));
    // An active worker that has touched the event log recently is making progress.
    const progressing = active.filter((x) => age(x) < STALL_MS);
    const stale = active.filter((x) => age(x) >= STALL_MS);
    const gaveUp = ws.filter((x) => x.status === GAVE_UP && !x.results?.length);
    const died = ws.filter((x) => TERMINAL.has(x.status) && x.status !== "COMPLETE" && !x.results?.length);

    // A task is only dead when nothing is currently working on it.
    const alive = progressing.length > 0;
    const dead = !done && !alive;

    const why = done ? ""
      : ws.length === 0 ? "never spawned"
      : alive ? "in progress"
      : stale.length ? `stalled ${Math.round(Math.max(...stale.map(age)) / 60000)}m with no event`
      : gaveUp.length ? `ended turn without worker_finish (${gaveUp.length})`
      : died.length ? `${died.length} attempt(s) failed`
      : "no active attempt";

    return {
      key: w.key, spec: w,
      attempts: ws.length,
      worker: receipts[0] ?? ws[ws.length - 1] ?? null,
      done,
      receipt: receipts.length ? receipts[0].results[receipts[0].results.length - 1] : null,
      dead,
      alive,
      liveWorkers: progressing.length,
      why,
      model: receipts[0] ? `${receipts[0].provider}/${receipts[0].model}` : null,
    };
  });
}

async function reassign(op, row, tried) {
  const w = row.spec;
  // The operator must keep clanking across a flaky pool. A dead or silent endpoint
  // is this layer's problem to absorb, NOT a reason to narrow the user's configured
  // pool, so pin explicitly to a model this task has not already failed on.
  // Selection has no "exclude these models" input, so the choice is made here.
  const pool = Object.keys(jread(join(process.env.USERPROFILE, ".pi", "agent", "settings.json"), {})
    .enabledModels || []);
  const seen = tried[row.key] || {};
  const triedModels = Object.keys(seen).filter((k) => k !== "__n");
  const untried = pool.filter((m) => !triedModels.includes(m));
  const pin = untried.length ? untried[0] : (triedModels[0] ?? w.model);

  const spec =
    `  assignment: ${JSON.stringify(w.assignment)}\n` +
    `  task_title: ${JSON.stringify(w.title + " (round " + ((seen.__n || 1) + 1) + ")")}\n` +
    `  ability_profile: ${w.profile || "implementation"}\n` +
    (pin ? `  model: ${JSON.stringify(pin)}\n` : `  (omit model - selection will pick)\n`)+
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
      const t = tried[row.key] || {};
      t.__n = (t.__n || 1) + 1;
      t[`${m.provider}/${m.model}`] = new Date().toISOString();
      tried[row.key] = t;
      writeFileSync(TRIED, JSON.stringify(tried, null, 2));
      journal("reassigned", {
        key: row.key, worker: m.id, model: `${m.provider}/${m.model}`,
        previous: row.model, round: t.__n, alreadyTried: triedModels.length,
      });
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
      dead: dead.map((d) => ({ key: d.key, why: d.why, attempts: d.attempts })),
      rows: rows.map((r) => ({ key: r.key, done: r.done, alive: r.alive, attempts: r.attempts, why: r.why })),
      workers: workers().map((w) => ({
        id: w.id, status: w.status, model: `${w.provider}/${w.model}`,
        name: w.display_name || null, last: w.last_activity,
      })),
    });

    console.log(
      `\n${new Date().toISOString().slice(0, 16).replace("T", " ")}  round ${round}  ` +
      `${done} done / ${live.length} live / ${dead.length} dead`,
    );
    for (const r of live) console.log(`  live  ${r.key.padEnd(22)} ${r.attempts} attempt(s) ${r.liveWorkers} active ${r.why}`);
    for (const r of dead) console.log(`  DEAD  ${r.key.padEnd(22)} ${r.attempts} attempt(s) ${r.why}`);

    // Exit only when EVERY task has produced a receipt. "No task is dead" is not
    // completion: one worker still in flight made the whole squadron look settled
    // once, and the supervisor exited out from under it.
    if (rows.length && rows.every((r) => r.done)) {
      console.log("  all tasks delivered a receipt");
      await integrateAll();
      journal("supervisor-complete", {});
      op.child.kill();
      process.exit(0);
    }

    if (round >= MAX_ROUNDS) {
      // 0 means never give up: keep rotating through the pool. A flaky endpoint is
      // the supervisor's job to absorb, not a reason to stop clanking.
      if (MAX_ROUNDS !== 0) {
        console.log(`  reached --max-rounds ${MAX_ROUNDS}; leaving remaining tasks for a human`);
        journal("supervisor-out-of-rounds", { remaining: dead.map((d) => d.key) });
        break;
      }
      console.log(`  still ${dead.length} unresolved - continuing, pool keeps rotating`);
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

    // Stay responsive when something is actually dead; back off when healthy.
    const wait = dead.length ? Math.min(INTERVAL_MIN, 5) : INTERVAL_MIN;
    console.log(`  sleeping ${wait}m`);
    await sleep(wait * 60 * 1000);
  }
  shutdown();
}

/** Copy every completed worker's uncommitted files onto the working tree.
 *
 *  The dedupe set is persisted across rounds. It used to be rebuilt each round, so
 *  a worker that finished in round 1 got its file overwritten in round 2 by a later
 *  attempt at the same task. First writer wins unless the content actually differs,
 *  in which case the newer version is kept and journalled as a revision.
 */
async function integrateAll() {
  const wtRoot = join(SC, "worktrees");
  if (!existsSync(wtRoot)) return;
  const { readdirSync, copyFileSync, mkdirSync, readFileSync: rf, existsSync: ex } = await import("node:fs");
  const { dirname, join: pjoin } = await import("node:path");
  const { execFileSync } = await import("node:child_process");

  const SEEN = join(SQ, "integrated.json");
  const seen = jread(SEEN, {});
  let changed = 0;

  for (const id of readdirSync(wtRoot)) {
    const wt = pjoin(wtRoot, id);
    if (!ex(pjoin(wt, ".git"))) continue;
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
      const dst = pjoin(ROOT, rel);
      const src = pjoin(wt, rel);
      let same = false;
      try { same = ex(dst) && rf(src, "utf8") === rf(dst, "utf8"); } catch { same = false; }
      if (same) continue;

      const prior = seen[rel];
      if (prior && prior !== `${id}:${w.provider}/${w.model}`) {
        // A second attempt at the same task produced a different version. Keep the
        // newer one, but say so - silent overwrites lose the earlier analysis.
        journal("integrate-revised", {
          rel, was: prior, now: `${id}:${w.provider}/${w.model}`,
          lines: rf(src, "utf8").split("\n").length,
        });
        console.log(`  REVISED ${rel}  (${prior} -> ${id})`);
      }
      mkdirSync(dirname(dst), { recursive: true });
      copyFileSync(src, dst);
      seen[rel] = `${id}:${w.provider}/${w.model}`;
      journal("integrated", { worker: id, model: `${w.provider}/${w.model}`, file: rel, revision: !!prior });
      console.log(`  integrated ${rel}  (${id} ${w.provider}/${w.model})`);
      changed++;
    }
  }
  if (changed) writeFileSync(SEEN, JSON.stringify(seen, null, 2));
}

main().catch((e) => {
  journal("supervisor-error", { message: String(e) });
  console.error(e);
  process.exit(1);
});