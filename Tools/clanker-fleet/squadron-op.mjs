/**
 * Operator process handling for squadron.mjs.
 *
 * An operator must be a long-lived `pi --mode rpc` process: the extension stops
 * every worker it spawned on session_shutdown, so nothing short-lived can host a
 * fleet. Kept separate so the spawn/cancel prompts and the JSONL framing live in
 * one place.
 */
import { spawn } from "node:child_process";
import { mkdirSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const ROOT = process.cwd();
const SQ = join(ROOT, ".statefulclanker", "squadron");
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

/** Starts a fresh operator with piped stdio and returns a handle we can write to. */
export async function spawnOperatorWithPipe(model = process.env.SQUADRON_OPERATOR_MODEL || "opencode-go/space-bunny") {
  mkdirSync(SQ, { recursive: true });
  const child = spawn(
    "pi",
    ["--mode", "rpc", "--provider", model.split("/")[0], "--model", model.split("/")[1],
     "--session-dir", join(SQ, "sessions")],
    { cwd: ROOT, stdio: ["pipe", "pipe", "pipe"], shell: true },
  );

  const responses = new Map();
  let seq = 0;

  // Strict LF framing only: node:readline also splits on U+2028/U+2029, which are
  // legal inside JSON strings.
  let buf = "";
  child.stdout.on("data", (c) => {
    buf += c.toString("utf8");
    for (;;) {
      const i = buf.indexOf("\n");
      if (i === -1) break;
      let line = buf.slice(0, i);
      buf = buf.slice(i + 1);
      if (line.endsWith("\r")) line = line.slice(0, -1);
      if (!line.trim()) continue;
      let rec;
      try { rec = JSON.parse(line); } catch { continue; }
      if (rec.type === "response" && rec.id !== undefined) {
        const p = responses.get(String(rec.id));
        if (p) { responses.delete(String(rec.id)); p(rec); }
      } else if (rec.type !== "response") {
        writeFileSync(join(SQ, "operator-events.jsonl"),
          JSON.stringify({ ts: new Date().toISOString(), type: rec.type }) + "\n", { flag: "a" });
      }
    }
  });
  child.stderr.on("data", (d) => {
    writeFileSync(join(SQ, "operator-stderr.log"), String(d), { flag: "a" });
  });

  const call = (obj, timeoutMs = 120000) =>
    new Promise((resolve) => {
      const id = obj.id ?? `q${++seq}`;
      const t = setTimeout(() => { responses.delete(id); resolve({ success: false, error: "timeout" }); }, timeoutMs);
      responses.set(id, (rec) => { clearTimeout(t); resolve(rec); });
      child.stdin.write(JSON.stringify({ ...obj, id }) + "\n");
    });

  await sleep(8000); // extension registration
  writeFileSync(join(SQ, "operator.json"), JSON.stringify({ pid: child.pid, model, started: new Date().toISOString() }, null, 2));
  return { child, call };
}

/** Queues a prompt. followUp is required: a bare prompt during a turn is rejected
 *  with "Agent is already processing" and silently lost. */
export async function ask(op, message, id) {
  return op.call({
    id: id ?? `q-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`,
    type: "prompt",
    streamingBehavior: "followUp",
    message,
  });
}

/** Cancels then retires each worker, through the operator that owns them. */
export async function cancelAll(op, ids) {
  if (!op?.child || op.child.killed) {
    console.log("  operator not attachable from this process - workers may need manual cleanup");
    return;
  }
  for (const id of ids) {
    await ask(op, `Call worker_cancel with id "${id}", then worker_retire with id "${id}". Reply with only "done ${id}".`, `cancel-${id}`);
    await sleep(4000);
  }
  op.child.kill();
}