#!/usr/bin/env node
/**
 * Spawns the audit fleet and holds the operator resident.
 *
 * The operator must stay alive: StatefulClanker's session_shutdown handler stops
 * every worker it spawned, so a one-shot `pi -p` would kill the fleet on exit.
 */
import { spawn } from "node:child_process";
import { writeFileSync, appendFileSync, mkdirSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.cwd();
const SC = join(ROOT, ".statefulclanker");
mkdirSync(SC, { recursive: true });
const EVENTS = join(SC, "operator-events.jsonl");

const FLEET = [
  { key: "streaming-audit", profile: "implementation", model: "opencode-go/space-bunny",
    title: "Streaming correctness audit",
    assignment: `Audit Source/TheWood/Private/Generation/WoodStreaming.cpp, Source/TheWood/Private/WoodWorldStreaming.cpp and Source/TheWood/Public/Generation/WoodStreaming.h against Docs/Specification.md sections 7 and 13 and against Docs/Status.md.

Hunt real defects, not style: chunk-order determinism, retention-buffer correctness, cancellation safety of background tasks, stable instance identity across unload/reload, and the "terrain under the player is protected" claim.

Docs/Status.md admits unloaded places currently regenerate reproducibly, which is NOT irreversible forgetting and is a documented deferral - do not report that as a bug.

Read the code. Cite file:line for every finding. Do NOT edit any source file. Produce a findings report in your worker_finish summary.` },

  { key: "fledge-subject", profile: "review", model: "opencode-free/fledge-alpha-free",
    title: "Test coverage vs acceptance gates",
    assignment: `Map what is actually tested against what is claimed. Read Tests/*.cpp (GenerationTests, BiomeTests, HexTests, DiscoveryTests, StreamingTests, AtmosphereTests, SoundscapeTests), Source/TheWood/Private/Tests/*.cpp, and Docs/Status.md.

Produce a table: claim in Status.md -> covering test -> genuinely covered / partially / NOT covered. Be adversarial about the "photographic gate remains open" and packaged-performance items: name which Status.md sentences have no corresponding test.

Cite file:line. Do not edit source.` },

  { key: "docs-audit", profile: "review", model: null,
    title: "Documentation honesty audit",
    assignment: `This project's specification makes an explicit demand: it must never overstate what is built. README.md and Docs/Specification.md repeatedly forbid representing the repo as the completed game or as achieving 60fps.

Check every quantitative and status claim in README.md, Docs/Status.md and Docs/Design.md against Source/ and Tests/. Report any claim that overstates, any internal contradiction between documents, and any claim with no supporting evidence. Also flag stale references: Docs/BiomeGeneration.md, Docs/BiomeCatalog.md and Docs/DiscoveryCatalog.md are described as future specifications, so confirm the README does not present them as implemented.

Do not edit any file. Cite file:line.` },

  { key: "persistence-design", profile: "architecture", model: null,
    title: "Save/resume and forgetting design",
    assignment: `Milestone 2 in Docs/Specification.md section 11 requires: generate ahead asynchronously, retain nearby geography, discard distant regions beyond the backtracking buffer, save retained state and pending identities, and make an interrupted generation task resume without creating a different seam.

Read Source/TheWood/Public/Generation/WoodStreaming.h, WoodWorld.h, WoodHex.h and the streaming implementation, then write a concrete design to Docs/superpowers/specs/2026-10-06-save-resume-design.md covering: the on-disk save format, what "fresh identity" means for a forgotten region so it cannot be regenerated from the same seed, how pending generation jobs are journalled, and how resume guarantees the same landmark.

Match existing code conventions and the metres-vs-centimetres unit boundary. Write that one file; do not modify source.` },

  { key: "perf-harness", profile: "implementation", model: null,
    title: "Packaged performance harness",
    assignment: `Docs/Specification.md section 12 requires acceptance on packaged builds at 1920x1080/60fps with recorded CPU, GPU, RAM, driver, engine patch, resolution and scalability settings, and states average frame rate alone is insufficient - stalls during generation and photo capture must be measured.

Read Tools/Test-Unreal.ps1, Tools/Build-Unreal.ps1 and Tools/Render-Review.ps1 to learn existing PowerShell conventions, then write Tools/Profile-Performance.ps1 that: builds the packaged 1080p client, records machine and driver metadata, walks a fixed route, and reports frame-time percentiles (p50/p95/p99) plus explicit stall-event counts for chunk realisation and photo capture, separated from steady state.

Follow the argument and error-handling style of the existing scripts. Write that one file; do not modify source.` },

  { key: "probability-audit", profile: "research", model: null,
    title: "Ruin and unreal probability audit",
    assignment: `Docs/Specification.md section 5 states approximately one tenth of regions may receive unreal character and approximately one third may contain a ruin, as INDEPENDENT assignments - a place can be ordinary with a ruin, unreal without one, both, or neither - and explicitly says these are generation defaults across many regions, not a quota forcing exactly one ruin per three adjacent regions.

Read Source/TheWood/Public/Generation/WoodDiscovery.h, Source/TheWood/Private/Generation/WoodDiscovery.cpp and the hex ownership code, and determine what the implementation actually does with those probabilities. Report measured or nominal rates, whether the two assignments are truly independent, and whether the implementation is per-cell or per-chunk.

Do not edit source. Cite file:line and state plainly if spec and code disagree.` },
];

const OPERATOR_MODEL = process.env.FLEET_OPERATOR_MODEL || "opencode-go/space-bunny";
const HOLD_MS = Number(process.env.FLEET_HOLD_MS || 3_600_000);

const child = spawn("pi", [
  "--mode", "rpc",
  "--provider", OPERATOR_MODEL.split("/")[0],
  "--model", OPERATOR_MODEL.split("/")[1],
  "--session-dir", join(SC, "operator-sessions"),
], { cwd: ROOT, stdio: ["pipe", "pipe", "pipe"], shell: true });

let buf = "";
child.stdout.on("data", (c) => {
  buf += c.toString("utf8");
  for (;;) {
    const i = buf.indexOf("\n");
    if (i === -1) break;
    let line = buf.slice(0, i); buf = buf.slice(i + 1);
    if (line.endsWith("\r")) line = line.slice(0, -1);
    if (!line.trim()) continue;
    let rec; try { rec = JSON.parse(line); } catch { continue; }
    if (rec.type === "response" && rec.command === "prompt")
      appendFileSync(EVENTS, JSON.stringify({ ts: Date.now(), kind: "prompt-response", rec }) + "\n");
    else if (rec.type !== "response")
      appendFileSync(EVENTS, JSON.stringify({ ts: Date.now(), kind: rec.type, data: rec }) + "\n");
  }
});
child.stderr.on("data", (d) => appendFileSync(join(SC, "operator-stderr.log"), String(d)));
const send = (o) => child.stdin.write(JSON.stringify(o) + "\n");

setTimeout(async () => {
  const only = process.env.FLEET_ONLY ? process.env.FLEET_ONLY.split(",") : null;
  for (const t of FLEET) {
    if (only && !only.includes(t.key)) continue;
    const spec =
      `  assignment: ${JSON.stringify(t.assignment)}\n` +
      `  task_title: "${t.title}"\n` +
      `  ability_profile: ${t.profile}\n` +
      (t.model ? `  model: "${t.model}"\n` : `  (omit model - let selection choose)\n`) +
      `  worktree_required: true\n` +
      `  expected_outputs: ["a findings report with file:line citations"]\n`;
    send({
      id: `spawn-${t.key}`,
      type: "prompt",
      // Without this the command is rejected while the operator is mid-turn:
      // "Agent is already processing." followUp queues it instead of dropping it.
      streamingBehavior: "followUp",
      message:
        `Call worker_spawn exactly once with these parameters:\n${spec}\n` +
        `Reply with only the JSON worker_spawn returned, verbatim. Do not poll the worker.`,
    });
    await new Promise((r) => setTimeout(r, 4000));
  }
}, 8000);

setTimeout(() => { child.kill(); process.exit(0); }, HOLD_MS);
process.on("SIGTERM", () => { child.kill(); process.exit(0); });
process.on("SIGINT", () => { child.kill(); process.exit(0); });
console.log(`fleet operator up: ${OPERATOR_MODEL}; holding ${(HOLD_MS / 60000).toFixed(0)}min`);