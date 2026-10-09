#!/usr/bin/env node
/**
 * Squadron — one command to lash a set of StatefulClanker workers together.
 *
 * Why this exists
 * ---------------
 * StatefulClanker's `worker_spawn` is only reachable through a running operator
 * session, and an operator session is an LLM. That makes spawning awkward in two
 * ways this tool removes:
 *
 *   1. `pi -p` cannot host workers. The extension's session_shutdown handler stops
 *      every worker it spawned, so a one-shot prompt kills its own fleet on exit.
 *      A long-lived `pi --mode rpc` operator is required.
 *   2. The operator drops instructions. Asked to pin `fledge-alpha-free`, it spawned
 *      `exo-free` instead. So every spawn is verified against the registry and
 *      repaired rather than trusted.
 *
 * Commands
 *   up [spec]      preflight, ensure an operator, spawn the squadron, verify
 *   status         table of workers with model, task, receipt state
 *   show <id>      full receipt for one worker
 *   down           cancel and retire every live worker
 *   doctor         preflight checks only
 *   detach         stop the operator without cancelling workers
 *
 * Spec is JSON: { workers: [ { key, title, assignment, profile?, model?, worktree? } ] }
 * With no argument, up reads squadron.json in the project root.
 */

import { spawn } from "node:child_process";
import { existsSync, readFileSync, writeFileSync, mkdirSync, openSync, readdirSync, copyFileSync } from "node:fs";
import { execFileSync } from "node:child_process";
import { join, dirname } from "node:path";
import { spawnOperatorWithPipe, ask, cancelAll } from "./squadron-op.mjs";

const ROOT = process.cwd();
const SC = join(ROOT, ".statefulclanker");
const SQ = join(SC, "squadron");
const OPERATOR_JSON = join(SQ, "operator.json");
const SPEC_FILE = process.argv[3] && !process.argv[3].startsWith("-")
  ? (existsSync(process.argv[3]) ? process.argv[3] : join(ROOT, process.argv[3]))
  : join(ROOT, "squadron.json");

const jread = (p, d) => { try { return JSON.parse(readFileSync(p, "utf8")); } catch { return d; } };
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const registry = () => jread(join(SC, "workers", "registry.json"), { next: 1, workers: {} });
const workers = () => Object.values(registry().workers);
const alive = (pid) => { try { process.kill(pid, 0); return true; } catch (e) { return e.code === "EPERM"; } };
const ts = () => new Date().toISOString().slice(11, 19);

// ------------------------------------------------------------------ preflight

async function doctor() {
  const problems = [];
  const notes = [];

  if (!existsSync(join(ROOT, ".git"))) problems.push("not a git repository - worktrees will fail");

  const settings = jread(join(process.env.USERPROFILE, ".pi", "agent", "settings.json"), {});
  const enabled = settings.enabledModels;

  const spec = existsSync(SPEC_FILE) ? jread(SPEC_FILE, { workers: [] }).workers || [] : [];
  const pinned = spec.filter((w) => w.model).map((w) => w.model);

  if (enabled) {
    const missing = pinned.filter((m) => !enabled.includes(m));
    if (missing.length)
      problems.push(`not in enabledModels (selection will never pick them): ${missing.join(", ")}`);
    const freeViaProxy = pinned.filter((m) => m.startsWith("opencode-free/"));
    if (freeViaProxy.length && !enabled.some((m) => m.startsWith("opencode-free/")))
      notes.push("opencode-free models selected: proxy required, and they cannot host long tasks");
  } else notes.push("enabledModels not set - selection uses the whole authenticated pool");

  if (pinned.some((m) => m.startsWith("opencode-free/"))) {
    try {
      const r = await fetch("http://127.0.0.1:4097/health", { signal: AbortSignal.timeout(3000) });
      if (!r.ok) problems.push("proxy :4097 not healthy - run Tools/oc-proxy/start.sh");
      else notes.push("proxy :4097 healthy");
    } catch {
      problems.push("proxy :4097 unreachable but an opencode-free model is pinned - run Tools/oc-proxy/start.sh");
    }
  }

  const live = workers().filter((w) => !["COMPLETE", "CANCELLED", "FAILED", "LOST"].includes(w.status));
  if (live.length) notes.push(`${live.length} worker(s) already live`);

  notes.push(`spec: ${existsSync(SPEC_FILE) ? SPEC_FILE : "(missing)"} with ${spec.length} worker(s)`);
  for (const p of problems) console.log(`  PROBLEM  ${p}`);
  for (const n of notes) console.log(`  ok       ${n}`);
  return problems.length === 0;
}

// ------------------------------------------------------------------- operator

/** Last recorded operator, if it is still alive. Informational only: we cannot
 *  re-attach to an operator we did not spawn, so `up` always starts its own. */
function lastOperator() {
  const o = jread(OPERATOR_JSON, null);
  return o && o.pid && alive(o.pid) ? o : null;
}

// ---------------------------------------------------------------------- spawn

/** Wait until the registry gains a worker, or timeout. Returns the new worker. */
async function awaitNewWorker(before, timeoutMs) {
  const start = Date.now();
  while (Date.now() - start < timeoutMs) {
    const now = workers();
    const fresh = now.filter((w) => !before.includes(w.id));
    if (fresh.length) return fresh[0];
    await sleep(2000);
  }
  return null;
}

/**
 * Ask the operator for exactly one worker, then verify. Retries once on a miss,
 * because the operator sometimes answers a spawn prompt with prose only.
 */
async function spawnOne(op, w, known) {
  const spec =
    `  assignment: ${JSON.stringify(w.assignment)}\n` +
    `  task_title: ${JSON.stringify(w.title)}\n` +
    `  ability_profile: ${w.profile || "implementation"}\n` +
    (w.model ? `  model: ${JSON.stringify(w.model)}\n` : `  (omit model - let selection choose)\n`) +
    `  worktree_required: ${w.worktree === false ? "false" : "true"}\n` +
    (w.expected_outputs ? `  expected_outputs: ${JSON.stringify(w.expected_outputs)}\n` : "");

  const prompt =
    `Call worker_spawn exactly once with these parameters:\n${spec}\n` +
    `Reply with only the JSON worker_spawn returned. Do not poll the worker.`;

  for (let attempt = 1; attempt <= 2; attempt++) {
    const before = workers().map((x) => x.id);
    await ask(op, prompt, `sq-${w.key}-${attempt}-${Date.now()}`);

    // A worktree checks out ~777 files and takes tens of seconds; read-only tasks
    // skip it entirely and come back in seconds.
    const got = await awaitNewWorker(before, w.worktree === false ? 90000 : 240000);
    if (got) {
      const want = w.model ? `${w.model.split("/")[0]}/${w.model.split("/").slice(1).join("/")}` : null;
      const ok = !want || `${got.provider}/${got.model}` === want;
      return { ok: true, worker: got, pinned: want, matched: ok, attempts: attempt };
    }
  }
  return { ok: false, key: w.key, attempts: 2 };
}

// ----------------------------------------------------------------------- main

async function up() {
  console.log("preflight");
  if (!(await doctor())) {
    console.log("\npreflight failed - fix the problems above");
    process.exit(1);
  }
  const spec = jread(SPEC_FILE, { workers: [] }).workers || [];
  if (!spec.length) {
    console.log(`no workers in ${SPEC_FILE}`);
    process.exit(1);
  }

  const prev = lastOperator();
  console.log(prev
    ? `\noperator from a previous run is still live (pid ${prev.pid}); leaving it alone`
    : `\nstarting operator (${process.env.SQUADRON_OPERATOR_MODEL || "opencode-go/space-bunny"})`);

  // A fresh operator per `up`. Workers owned by an earlier operator keep running.
  const op = await spawnOperatorWithPipe();

  console.log(`\nspawning ${spec.length} worker(s)\n`);
  const results = [];
  for (const w of spec) {
    process.stdout.write(`  ${w.key.padEnd(22)} `);
    const r = await spawnOne(op, w, registry());
    if (!r.ok) {
      console.log("FAILED to spawn (2 attempts)");
      results.push({ key: w.key, ok: false });
      continue;
    }
    const m = r.worker;
    const flag = r.pinned ? (r.matched ? "pin ok" : `PIN MISMATCH (wanted ${r.pinned})`) : "auto";
    console.log(
      `${m.id} ${m.provider}/${m.model} ${m.status} [${flag}]${m.worktree ? "" : " no-worktree"}`,
    );
    results.push({ key: w.key, ok: true, id: m.id, model: `${m.provider}/${m.model}`, matched: r.matched });
  }

  const okCount = results.filter((r) => r.ok).length;
  console.log(`\n${okCount}/${results.length} spawned`);
  const mismatched = results.filter((r) => r.ok && r.matched === false);
  if (mismatched.length)
    console.log(`WARNING: pin not honoured: ` + mismatched.map((m) => `${m.key}->${m.model}`).join(", "));
  const missing = results.filter((r) => !r.ok);
  if (missing.length)
    console.log(`WARNING: ${missing.length} never spawned: ` + missing.map((m) => m.key).join(", "));
  writeFileSync(join(SQ, "last-up.json"), JSON.stringify({ at: new Date().toISOString(), results }, null, 2));

  // The operator must outlive this process: its stdin holds the worker supervisor
  // alive, so exiting here would stop every worker just spawned. `up` stays
  // resident and watches instead.
  if (!process.env.SQUADRON_NO_WATCH) {
    console.log("\nwatching. Ctrl-C stops the operator, which cancels the fleet.");
    console.log("other shells:  node Tools/clanker-fleet/squadron.mjs status\n");
    await watch();
  } else {
    console.log(`\nstatus:  node Tools/clanker-fleet/squadron.mjs status`);
    console.log(`down:    node Tools/clanker-fleet/squadron.mjs down`);
  }
}

const SYMBOL = { COMPLETE: "ok  ", RUNNING: "RUN ", STARTING: "....", IDLE: "idle",
  BLOCKED: "BLK ", FAILED: "FAIL", CANCELLED: "cncl", LOST: "LOST", WAITING: "wait" };

/** Live rack until every worker reaches a terminal state. */
async function watch() {
  const last = new Map();
  for (;;) {
    const ws = workers();
    let line = "";
    let settled = 0;
    for (const w of ws) {
      if (["COMPLETE", "FAILED", "CANCELLED", "LOST"].includes(w.status)) { settled++; continue; }
      if (last.get(w.id) !== w.status) { last.set(w.id, w.status); console.log(`  ${w.id} -> ${w.status}`); }
      const mins = Math.round((Date.now() - new Date(w.started_at).getTime()) / 60000);
      line += `  ${w.id} ${(SYMBOL[w.status] ?? w.status.slice(0, 4)).padEnd(5)} ` +
        `${(w.provider + "/" + w.model).replace(/^(opencode-go|opencode-free|openrouter)\//, "")} ` +
        `${(w.display_name || "-").padEnd(12)} ${(w.current_action || w.current_tool || "").slice(0, 30)} ${mins}m\n`;
    }
    if (line) console.log("\n" + line);
    const ok = ws.filter((w) => w.status === "COMPLETE").length;
    console.log(`  ${ts()}  ${ok} receipt(s), ${settled} settled of ${ws.length}`);
    if (ws.length && settled + ok >= ws.length) {
      console.log("\nsquadron settled.");
      for (const w of ws.filter((x) => x.status === "COMPLETE")) console.log(`  ${w.id} ${(w.display_name || "").padEnd(12)} receipt ok`);
      for (const w of ws.filter((x) => x.status !== "COMPLETE")) console.log(`  ${w.id} ${w.status.padEnd(9)} no receipt`);
      process.exit(0);
    }
    await sleep(15000);
  }
}

function status() {
  const ws = workers();
  if (!ws.length) return console.log("no workers");
  console.log("id    status      model                              task      name          receipt");
  for (const w of ws) {
    const r = w.results?.[w.results.length - 1];
    console.log(
      `${w.id}  ${w.status.padEnd(10)}  ${(w.provider + "/" + w.model).padEnd(32)}  ` +
      `${(w.task_id || "-").padEnd(8)}  ${(w.display_name || "-").padEnd(12)}  ${r ? r.status : "-"}`,
    );
  }
  console.log(`\n${ts()}  ${ws.filter((w) => w.status === "COMPLETE").length} complete, ` +
    `${ws.filter((w) => !["COMPLETE", "CANCELLED", "FAILED", "LOST"].includes(w.status)).length} live`);
}

function show(id) {
  const w = workers().find((x) => x.id === id);
  if (!w) return console.log(`no worker ${id}`);
  const r = w.results?.[w.results.length - 1];
  console.log(`${w.id}  ${w.status}  ${w.provider}/${w.model}  task=${w.task_id}`);
  if (w.worktree) console.log(`worktree ${w.worktree.path}\nbranch   ${w.worktree.branch}`);
  if (!r) return console.log("\n(no receipt - worker did not call worker_finish)");
  console.log(`\n${r.summary}`);
  if (r.changed_files?.length) console.log(`\nchanged: ${r.changed_files.join(", ")}`);
  if (r.known_risks?.length) console.log(`risks:   ${r.known_risks.join("; ")}`);
  if (r.unresolved_questions?.length) console.log(`open:    ${r.unresolved_questions.join("; ")}`);
}

async function down() {
  const op = lastOperator();
  const live = workers().filter((w) => !["COMPLETE", "CANCELLED", "FAILED", "LOST"].includes(w.status));
  console.log(`${live.length} live worker(s)`);
  for (const w of live) console.log(`  ${w.id} ${w.status} ${w.provider}/${w.model}`);
  if (!op) return console.log("\nno live operator recorded - kill stray pi --mode rpc processes by hand");
  console.log("\ncancelling through a fresh operator...");
  const fresh = await spawnOperatorWithPipe();
  await cancelAll(fresh, live.map((w) => w.id));
  console.log("done");
}

async function harvest() {
  const wtRoot = join(SC, "worktrees");
  if (!existsSync(wtRoot)) return console.log("no worktrees");
  const out = [];
  for (const id of readdirSync(wtRoot)) {
    const wt = join(wtRoot, id);
    if (!existsSync(join(wt, ".git"))) continue;
    const files = execFileSync("git", ["-C", wt, "status", "--porcelain"], { encoding: "utf8" })
      .split("\n").filter((l) => l.trim());
    const w = workers().find((x) => x.id === id);
    out.push({
      id,
      model: w ? `${w.provider}/${w.model}` : "(archived)",
      name: w?.display_name ?? null,
      receipt: !!(w?.results?.length),
      files: files.map((l) => l.slice(3).trim()),
    });
  }
  console.log("id    model                        name           receipt  uncommitted");
  for (const o of out)
    console.log(`${o.id}  ${o.model.padEnd(28)} ${(o.name || "-").padEnd(13)} ${(o.receipt ? "yes" : "NO").padEnd(7)} ${o.files.length}`);
  console.log("\nIntegrate with:  node squadron.mjs integrate <workerId>");
}

/** Copy a worker's uncommitted files onto the working tree, then commit nothing. */
function integrate(id) {
  const wt = join(SC, "worktrees", id);
  if (!existsSync(wt)) return console.log(`no worktree for ${id}`);
  const lines = execFileSync("git", ["-C", wt, "status", "--porcelain"], { encoding: "utf8" })
    .split("\n").filter((l) => l.trim() && !l.includes(".clanker"));
  if (!lines.length) return console.log(`${id}: nothing to integrate`);
  for (const l of lines) {
    const rel = l.slice(3).trim().replace(/^"/, "").replace(/"$/, "");
    if (!rel || rel.includes("->")) continue;
    const src = join(wt, rel), dst = join(ROOT, rel);
    mkdirSync(dirname(dst), { recursive: true });
    copyFileSync(src, dst);
    console.log(`  ${rel}`);
  }
  console.log(`\nintegrated ${lines.length} file(s) from ${id}. Review, then commit.`);
}

const cmd = process.argv[2] || "status";
if (cmd === "doctor") await doctor();
else if (cmd === "up") await up();
else if (cmd === "status") status();
else if (cmd === "show") show(process.argv[3]);
else if (cmd === "harvest") harvest();
else if (cmd === "integrate") integrate(process.argv[3]);
else if (cmd === "down") await down();
else console.log("commands: up | status | show <id> | down | doctor");