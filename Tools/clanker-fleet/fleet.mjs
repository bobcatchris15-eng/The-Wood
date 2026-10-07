#!/usr/bin/env node
/**
 * StatefulClanker fleet controller.
 *
 * My own session cannot call worker_spawn (the package was installed after this
 * session started), so this drives a `pi --mode rpc` operator process instead.
 * The parent must stay alive: the extension's session_shutdown handler stops every
 * worker, so a one-shot `pi -p` would kill its own fleet the moment it exited.
 *
 * Usage:
 *   node fleet.mjs plan                 # dry-run the selection for each task
 *   node fleet.mjs spawn                # spawn the fleet, stay resident
 *   node fleet.mjs watch <seconds>      # attach to a running fleet and report
 */

import { spawn } from "node:child_process";
import { writeFileSync, mkdirSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.cwd();
const LOG = join(ROOT, ".statefulclanker", "fleet-log.jsonl");
const PIDFILE = join(ROOT, ".statefulclanker", "fleet.pid");

/**
 * Independent, bounded, read-and-report tasks. Nothing here needs the Unreal
 * editor, so the fleet cannot collide on a build lock.
 */
export const TASKS = [
  {
    key: "streaming-audit",
    model: "opencode-free/exo-free",
    profile: "implementation",
    title: "Streaming correctness audit",
    assignment: `Audit Source/TheWood/Private/Generation/WoodStreaming.cpp, Source/TheWood/Private/WoodWorldStreaming.cpp and Source/TheWood/Public/Generation/WoodStreaming.h against the requirements in Docs/Specification.md section 7 and section 13, and against Docs/Status.md.

Focus on real defects, not style: chunk-order determinism, retention-buffer correctness, cancellation safety of background tasks, stable instance identity across unload/reload, and the "terrain under the player is protected" claim. Note that Docs/Status.md admits unloaded places currently regenerate reproducibly, which is NOT irreversible forgetting - do not report that as a bug, it is a documented deferral.

Read the code. Cite file:line for every finding. Do NOT edit any source file; you are producing a findings report only.`,
  },
  {
    key: "test-coverage-audit",
    model: "opencode-free/fledge-alpha-free",
    profile: "review",
    title: "Test coverage vs acceptance gates",
    assignment: `Map what is actually tested against what is claimed. Read Tests/*.cpp (GenerationTests, BiomeTests, HexTests, DiscoveryTests, StreamingTests, AtmosphereTests, SoundscapeTests), Source/TheWood/Private/Tests/*.cpp, and Docs/Status.md.

Produce a table: claim in Status.md -> test that covers it -> genuinely covered / partially / NOT covered. Be adversarial about the "photographic gate remains open" and packaged-performance items: identify which specific Status.md sentences have no corresponding test. Do not edit source. Cite file:line.`,
  },
  {
    key: "docs-overclaim-audit",
    model: null,
    profile: "review",
    title: "Documentation honesty audit",
    assignment: `This project's specification makes an explicit and unusual demand: it must never overstate what is built. README.md and Docs/Specification.md repeatedly forbid representing the repo as the completed game or as achieving 60fps.

Check every quantitative and status claim in README.md, Docs/Status.md and Docs/Design.md against Source/ and Tests/. Report any claim that overstates, any internal contradiction between documents, and any claim with no supporting evidence. Also flag stale references: Docs/BiomeGeneration.md, Docs/BiomeCatalog.md and Docs/DiscoveryCatalog.md are described as future specifications, so confirm the README does not present them as implemented. Do not edit any file. Cite file:line.`,
  },
  {
    key: "persistence-design",
    model: null,
    profile: "architecture",
    title: "Save/resume and forgetting design",
    assignment: `Milestone 2 in Docs/Specification.md section 11 requires: generate ahead asynchronously, retain nearby geography, discard distant regions beyond the backtracking buffer, save retained state and pending identities, and make an interrupted generation task resume without creating a different seam.

Read Source/TheWood/Public/Generation/WoodStreaming.h, WoodWorld.h, WoodHex.h and the streaming implementation, then write a concrete design to Docs/superpowers/specs/2026-10-06-save-resume-design.md. It must cover: the on-disk save format, what "fresh identity" means for a forgotten region so it cannot be regenerated from the same seed, how pending generation jobs are journalled, and how resume guarantees the same landmark. Match the existing code conventions and the metres-vs-centimetres unit boundary. Write the file; do not modify source.`,
  },
  {
    key: "perf-harness",
    model: null,
    profile: "implementation",
    title: "Packaged performance harness",
    assignment: `Docs/Specification.md section 12 requires acceptance on packaged builds at 1920x1080/60fps with recorded CPU, GPU, RAM, driver, engine patch, resolution and scalability settings, and states that average frame rate alone is insufficient - stalls during generation and photo capture must be measured.

Read Tools/Test-Unreal.ps1, Tools/Build-Unreal.ps1 and Tools/Render-Review.ps1 to learn the existing PowerShell conventions, then write Tools/Profile-Performance.ps1 that: builds the packaged 1080p client, records machine and driver metadata, walks a fixed route, and reports frame-time percentiles (p50/p95/p99) plus explicit stall-event counts for chunk realisation and photo capture, separating them from steady-state. Follow the argument and error-handling style already used in those scripts. Write the file; do not modify source.`,
  },
  {
    key: "discovery-probability-audit",
    model: null,
    profile: "research",
    title: "Ruin and unreal probability audit",
    assignment: `Docs/Specification.md section 5 states approximately one tenth of regions may receive unreal character and approximately one third may contain a ruin, as INDEPENDENT assignments - a place can be ordinary with a ruin, unreal without one, both, or neither - and explicitly says these are generation defaults across many regions, not a quota forcing exactly one ruin per three adjacent regions.

Read Source/TheWood/Public/Generation/WoodDiscovery.h, Source/TheWood/Private/Generation/WoodDiscovery.cpp and the hex ownership code, and determine what the implementation actually does with those probabilities. Report the measured or nominal rates, whether the two assignments are truly independent, and whether the implementation is per-cell or per-chunk. Do not edit source. Cite file:line and state plainly if the spec and code disagree.`,
  },
];

// ---------------------------------------------------------------- rpc plumbing

function jsonl(onRecord, onEvent) {
  let buf = "";
  return (chunk) => {
    buf += chunk.toString("utf8");
    for (;;) {
      const i = buf.indexOf("\n");
      if (i === -1) break;
      let line = buf.slice(0, i);
      buf = buf.slice(i + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (!line.trim()) continue;
      let rec;
      try {
        rec = JSON.parse(line);
      } catch {
        continue;
      }
      if (rec.type === "response") onRecord(rec);
      else onEvent(rec);
    }
  };
}

function startOperator() {
  const child = spawn(
    process.execPath,
    [join(ROOT, "Tools", "oc-proxy", "..", "..", "node_modules", "pi", "dist", "cli.js")],
    { cwd: ROOT, stdio: ["pipe", "pipe", "pipe"], shell: false },
  );
  return child;
}

function operatorArgv() {
  // Resolve the pi CLI the same way the extension resolves its own child.
  const base = process.env.PI_CLI || "pi";
  return { cmd: base, args: ["--mode", "rpc", "--session-dir", join(ROOT, ".statefulclanker", "operator-sessions")] };
}

export async function withOperator(fn) {
  const { cmd, args } = operatorArgv();
  const child = spawn(cmd, args, {
    cwd: ROOT,
    stdio: ["pipe", "pipe", "pipe"],
    shell: process.platform === "win32",
  });
  const pending = new Map();
  const events = [];
  let seq = 0;
  const send = (obj) => child.stdin.write(JSON.stringify(obj) + "\n");

  child.stdout.on("data", jsonl(
    (rec) => {
      const p = pending.get(String(rec.id));
      if (p) {
        pending.delete(String(rec.id));
        p(rec);
      }
    },
    (ev) => {
      events.push(ev);
      if (ev.type) mkdirSync(join(ROOT, ".statefulclanker"), { recursive: true });
      writeFileSync(LOG, JSON.stringify({ ts: Date.now(), ev: ev.type, data: ev }, null, 0) + "\n", { flag: "a" });
    },
  ));
  child.stderr.on("data", (d) => process.stderr.write(`[op-err] ${d}`));

  const call = (obj, timeoutMs = 120000) =>
    new Promise((resolve) => {
      const id = obj.id ?? `r${++seq}`;
      const t = setTimeout(() => {
        pending.delete(id);
        resolve({ type: "response", command: obj.type, success: false, data: { error: "timeout" } });
      }, timeoutMs);
      pending.set(id, (rec) => {
        clearTimeout(t);
        resolve(rec);
      });
      send({ ...obj, id });
    });

  await new Promise((r) => setTimeout(r, 6000)); // let the extension register
  try {
    return await fn({ send, call, events, child });
  } finally {
    child.kill();
  }
}

if (process.argv[2] === "spawn") {
  mkdirSync(join(ROOT, ".statefulclanker"), { recursive: true });
  const results = [];
  await withOperator(async ({ send, call }) => {
    const brief = TASKS.map(
      (t, i) => `${i + 1}. ${t.title} (${t.key})`,
    ).join("\n");

    for (const t of TASKS) {
      const args = {
        type: "prompt",
        message:
          `You are the StatefulClanker operator. Spawn ${TASKS.length} workers in parallel for these independent audit tasks:\n${brief}\n\n` +
          `Spawn them ONE AT A TIME with worker_spawn (calls are quick and non-blocking) but do not wait for results between spawns.\n\n` +
          `For the worker titled "${t.title}" (key ${t.key}) use exactly these parameters:\n` +
          `  assignment: ${JSON.stringify(t.assignment)}\n` +
          `  task_title: "${t.title}"\n` +
          `  ability_profile: ${t.profile}\n` +
          (t.model ? `  model: "${t.model}"\n` : `  (omit model so selection picks)\n`) +
          `  worktree_required: true\n\n` +
          `After all spawns, reply with one line per worker: the worker_id and the chosen model. Do not poll them and do not report results yet.`,
      };
      const r = await call(args);
      results.push({ task: t.key, response: r?.data ?? r });
      // let the spawn land before issuing the next
      await new Promise((r2) => setTimeout(r2, 1500));
      send({ type: "get_state", id: `st${Date.now()}` });
    }
  });
  writeFileSync(PIDFILE, String(process.pid));
  console.log(JSON.stringify(results, null, 1));
}