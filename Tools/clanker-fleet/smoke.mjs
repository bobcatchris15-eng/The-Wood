#!/usr/bin/env node
/**
 * Spawns one worker and holds the operator alive so the worker can finish.
 * Used to validate the SC1 loop through the local free-tier proxy before
 * committing to a parallel fleet.
 *
 *   node smoke.mjs <model> <profile>
 */
import { spawn } from "node:child_process";
import { writeFileSync, appendFileSync, mkdirSync, existsSync, readFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.cwd();
const SC = join(ROOT, ".statefulclanker");
mkdirSync(SC, { recursive: true });
const MODEL = process.argv[2] || "opencode-free/exo-free";
const PROFILE = process.argv[3] || "implementation";

const ASSIGNMENT = `Read the file Source/TheWood/Public/Generation/WoodHex.h and report, in under 150 words, what the hex cell coordinate system does and what canonical edge keys are for. Then call worker_finish with status "complete" and a summary containing your findings.`;

const child = spawn("pi", ["--mode", "rpc", "--session-dir", join(SC, "operator-sessions")], {
  cwd: ROOT, stdio: ["pipe", "pipe", "pipe"], shell: true,
});

let buf = "";
const seen = [];
child.stdout.on("data", (c) => {
  buf += c.toString("utf8");
  for (;;) {
    const i = buf.indexOf("\n");
    if (i === -1) break;
    let line = buf.slice(0, i); buf = buf.slice(i + 1);
    if (line.endsWith("\r")) line = line.slice(0, -1);
    if (!line.trim()) continue;
    let rec; try { rec = JSON.parse(line); } catch { continue; }
    if (rec.type !== "response") {
      seen.push(rec.type);
      appendFileSync(join(SC, "smoke-events.jsonl"), JSON.stringify(rec) + "\n");
      if (rec.type === "message" || rec.type === "message_part") {
        const p = rec.part ?? rec.message ?? {};
        if (p.text) appendFileSync(join(SC, "smoke-text.log"), p.text + "\n");
      }
    } else {
      appendFileSync(join(SC, "smoke-responses.log"), JSON.stringify(rec) + "\n");
    }
  }
});
child.stderr.on("data", (d) => appendFileSync(join(SC, "smoke-stderr.log"), String(d)));

const send = (o) => child.stdin.write(JSON.stringify(o) + "\n");

setTimeout(() => {
  const msg =
    `You are the StatefulClanker operator. Spawn exactly ONE worker using worker_spawn with these parameters:\n` +
    `  assignment: ${JSON.stringify(ASSIGNMENT)}\n` +
    `  task_title: "Hex cell smoke test"\n` +
    `  ability_profile: ${PROFILE}\n` +
    `  model: "${MODEL}"\n` +
    `  worktree_required: true\n\n` +
    `Reply with only the JSON that worker_spawn returned, verbatim. Do not poll the worker.`;
  send({ id: "spawn1", type: "prompt", message: msg });
}, 7000);

// Hold the operator open so session_shutdown does not kill the worker.
const HOLD_MS = Number(process.env.SMOKE_HOLD_MS || 240000);
setTimeout(() => { child.kill(); process.exit(0); }, HOLD_MS);

process.on("SIGTERM", () => { child.kill(); process.exit(0); });