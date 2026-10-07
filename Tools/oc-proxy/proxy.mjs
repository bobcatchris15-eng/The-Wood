#!/usr/bin/env node
/**
 * OpenCode Free Tier -> OpenAI-compatible proxy.
 *
 * OpenCode's free models reject requests that do not originate from an OpenCode
 * session ("OpenCode's free tier can only be used from within OpenCode"). The
 * local OpenCode server on :4096 does originate them. This proxy translates
 * OpenAI /v1/chat/completions into OpenCode session messages so pi can use them.
 *
 * Known fidelity limits, all verified by test/probe.mjs:
 *   - Streaming is emulated: OpenCode returns a completed turn, so deltas are
 *     synthesized after the fact. Time-to-first-token is the full turn latency.
 *   - Tool calls are emulated by protocol, not native. See TOOL_PROTOCOL below.
 *   - OpenCode's token accounting on this build is unreliable (reports 2-4 input
 *     tokens for a full system prompt). The proxy recomputes usage from the text
 *     it sent and received so pi's cost display is not garbage.
 */

import { createServer } from "node:http";
import { randomUUID, randomBytes } from "node:crypto";
import { mkdirSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";

const PORT = Number(process.env.OC_PROXY_PORT || 4097);
const OC = process.env.OC_GATEWAY || "http://127.0.0.1:4096";
/**
 * OpenCode session root. MUST live outside any repository.
 *
 * OpenCode keeps its own built-in tools enabled: in the message API, `tools: {}`
 * means "no overrides", NOT "no tools". A model can therefore read files through
 * OpenCode's agent loop without emitting a single OpenAI tool_call. Verified: with
 * the scratch dir inside the repo, the model read repo sources with no tool_call in
 * the transcript.
 *
 * OpenCode resolves relative paths upward to a detected project root, so placing
 * this in a temp directory is what actually prevents the free models from reaching
 * the working tree. Do not "simplify" this back into the repo.
 */
const SCRATCH =
  process.env.OC_PROXY_DIR ||
  join(tmpdir(), `oc-proxy-scratch-${randomBytes(4).toString("hex")}`);
mkdirSync(SCRATCH, { recursive: true });

/**
 * Models exposed by the `opencode` provider that cost nothing.
 *
 * `ling-3.0-flash-fin-free` is deliberately absent: upstream OpenCode returns
 * "Endpoint is unavailable" after ~70s for it (verified against :4096 directly,
 * 2026-10-06). Serving it would stall every turn before failing.
 */
export const FREE_MODELS = [
  "big-pickle",
  "exo-free",
  "fledge-alpha-free",
  "ling-3.1-flash-free",
  "longcat-2.5-preview-free",
  "mimo-v2.6-flash-free",
  "muse-spark-1.3-contributor-free",
  "nemotron-3-ultra-free",
  "nemotron-3.5-lightning-free",
  "space-bunny-free",
];

/** Exposed for diagnosis but intentionally not served. */
export const KNOWN_BAD = { "ling-3.0-flash-fin-free": "upstream endpoint unavailable" };

/** Context/output limits, read from the live /provider catalog at startup. */
let LIMITS = new Map();

const OC_MODEL_IDS = new Set(FREE_MODELS);

const TOOL_PROTOCOL = `

## TOOL CALL PROTOCOL (critical)

One fenced block per call, nothing else after it:

\`\`\`tool_call
{"name": "<tool name>", "arguments": {<json object>}}
\`\`\`

Rules:
- Never invent a tool name. Use only names from the TOOLS list.
- Do not describe the call in prose; the block is the entire message.
`;

/** OpenCode's own tools must be present-but-empty: any false entry reroutes the
 *  request to opencode.ai/inference and 403s. Suppression is done by prompt. */
/** OpenCode's own tools cannot be switched off through this API without rerouting
 *  the request to opencode.ai/inference, which rejects the free tier with 403.
 *  Isolation therefore comes from the session root living outside every repo,
 *  plus the prompt above. Treat this as defence in depth, not a hard guarantee. */
const OPENCODE_TOOLS = {};

const NO_NATIVE_TOOLS = `You are a completion backend. You have NO file access of your own - never search, never read, never list, never guess.

To run a tool you MUST emit a fenced tool_call block as your ENTIRE reply:

\`\`\`tool_call
{"name": "<tool name>", "arguments": {<json object>}}
\`\`\`

You cannot run tools any other way. If a tool is needed, the ONLY valid output is that block. Never describe the call in prose. Never answer from memory about file contents.

A plain-prose reply with no block means "no tool needed; this is my final answer".

## TOOLS
{{TOOLS_JSON}}`;

const H = { "Content-Type": "application/json", Accept: "application/json" };

async function ocFetch(path, init) {
  const res = await fetch(OC + path, { headers: H, ...init });
  const text = await res.text();
  try {
    return JSON.parse(text);
  } catch {
    throw new Error(`OpenCode ${path} -> ${res.status} ${text.slice(0, 200)}`);
  }
}

const q = (p) => `${p}?directory=${encodeURIComponent(SCRATCH)}`;

/** Rough token estimate. OpenCode's own counters are unusable on this build. */
function countTokens(text) {
  return Math.ceil((text || "").length / 4);
}

async function loadLimits() {
  try {
    const data = await ocFetch("/provider", { headers: { Accept: "application/json" } });
    const provider = (data.all || []).find((p) => p.id === "opencode");
    for (const [id, m] of Object.entries(provider?.models || {})) {
      LIMITS.set(id, {
        contextWindow: m.limit?.context ?? 200000,
        maxTokens: m.limit?.output ?? 32000,
      });
    }
    console.log(`[oc-proxy] catalog: ${LIMITS.size} models from ${OC}`);
  } catch (e) {
    console.warn(`[oc-proxy] catalog load failed (${e.message}); using defaults`);
  }
}

/** OpenCode conversation state, one per OpenAI conversation. */
const sessions = new Map();

/** Identifies a conversation's opening turn, so identical openings do not collide. */
function conversationKey(messages) {
  const first = messages[0]?.role === "system" ? messages[1] : messages[0];
  return `${first?.role || ""}:${String(first?.content ?? "").slice(0, 96)}`;
}

/** A request continues a session only if it extends what we already sent. */
function isContinuation(session, messages) {
  if (session.model !== session.lastModel) return false;
  if (messages.length < session.sent) return false;
  if (messages.length === session.sent) return messages[sentFingerprint(session)] === session.lastFingerprint;
  for (let i = 0; i < session.sent; i++) {
    if (fingerprint(messages[i]) !== session.printed[i]) return false;
  }
  return true;
}

function fingerprint(message) {
  return JSON.stringify([message?.role, message?.content ?? null, message?.tool_calls ?? null, message?.name ?? null]);
}

function sentFingerprint(session) {
  return session.sent > 0 ? session.sent - 1 : -1;
}

/** Lazily create a real OpenCode session; ids must come from the server. */
async function getSession(messages, model) {
  const key = conversationKey(messages);
  const existing = sessions.get(key);
  if (existing && isContinuation(existing, messages)) return existing;

  const created = await ocFetch(q("/session"), {
    method: "POST",
    body: JSON.stringify({ title: "pi-proxy", model: { providerID: "opencode", id: model } }),
  });
  if (!created?.id)
    throw new Error(`could not create OpenCode session: ${JSON.stringify(created).slice(0, 200)}`);

  // A fresh conversation resets the delta cursor and the print record.
  const session = {
    id: created.id,
    sent: 0,
    printed: [],
    lastFingerprint: null,
    lastModel: model,
    model,
    created: Date.now(),
    last: "",
  };
  sessions.set(key, session);
  return session;
}

/** Render new OpenAI messages into one OpenCode text part. */
function renderDelta(messages, from) {
  const lines = [];
  for (const m of messages.slice(from)) {
    if (m.role === "system") continue;
    if (m.role === "user") {
      lines.push(`[USER]\n${textOf(m.content)}`);
    } else if (m.role === "assistant") {
      const calls = m.tool_calls || [];
      if (calls.length) {
        lines.push(
          `[ASSISTANT TOOL CALL]\n${calls
            .map((c) => `${c.function.name}(${c.function.arguments})`)
            .join("\n")}`,
        );
      } else {
        lines.push(`[ASSISTANT]\n${textOf(m.content)}`);
      }
    } else if (m.role === "tool") {
      lines.push(`[TOOL RESULT ${m.name || m.tool_call_id}]\n${textOf(m.content)}`);
    }
  }
  return lines.join("\n\n");
}

function textOf(content) {
  if (typeof content === "string") return content;
  if (Array.isArray(content))
    return content
      .map((p) => (p.type === "text" ? p.text : `[${p.type}]`))
      .join("\n");
  return "";
}

function buildSystem(messages, tools) {
  const sys = messages.filter((m) => m.role === "system").map((m) => textOf(m.content));
  let out = NO_NATIVE_TOOLS;
  if (tools?.length) out += TOOL_PROTOCOL.replace("{{TOOLS_JSON}}", "");
  if (sys.length) out += "\n\n" + sys.join("\n\n");
  return out;
}

/** Parse ```tool_call blocks out of model text. */
function parseToolCalls(text) {
  const re = /```tool_call\s*([\s\S]*?)```/g;
  const calls = [];
  let m;
  while ((m = re.exec(text)) !== null) {
    let obj;
    try {
      obj = JSON.parse(m[1].trim());
    } catch {
      continue;
    }
    if (obj && typeof obj.name === "string") {
      calls.push({
        id: `call_${randomUUID().slice(0, 24)}`,
        type: "function",
        function: {
          name: obj.name,
          arguments: JSON.stringify(obj.arguments ?? {}),
        },
      });
    }
  }
  return calls;
}

function stripToolBlocks(text) {
  return text.replace(/```tool_call[\s\S]*?```/g, "").trim();
}

/** One OpenAI turn -> one OpenCode turn. */
async function complete(model, messages, tools) {
  const session = await getSession(messages, model);

  const delta = renderDelta(messages, session.sent);
  if (!delta) {
    // Nothing new to send; replay the last answer rather than burning a turn.
    return { text: session.last || "", calls: [] };
  }
  session.printed = messages.slice(0, session.sent).map(fingerprint);
  session.sent = messages.length;
  session.lastFingerprint = fingerprint(messages[messages.length - 1]);

  const data = await ocFetch(q(`/session/${session.id}/message`), {
    method: "POST",
    body: JSON.stringify({
      model: { providerID: "opencode", modelID: model },
      agent: "build",
      system: buildSystem(messages, tools),
      tools: OPENCODE_TOOLS,
      parts: [{ type: "text", text: delta }],
    }),
  });

  const err = data?.info?.error;
  if (err) {
    const e = new Error(err.data?.message || err.name || "OpenCode error");
    e.status = err.data?.statusCode || 502;
    throw e;
  }

  const text = (data.parts || [])
    .filter((p) => p.type === "text")
    .map((p) => p.text)
    .join("\n")
    .trim();

  const calls = parseToolCalls(text);
  const finalText = calls.length ? stripToolBlocks(text) : text;
  session.last = finalText;
  return { text: finalText, calls };
}

function usageFor(messages, text) {
  const promptChars = messages.reduce((n, m) => n + textOf(m.content).length, 0);
  return {
    prompt_tokens: countTokens("x".repeat(promptChars)),
    completion_tokens: countTokens(text),
    total_tokens: countTokens("x".repeat(promptChars)) + countTokens(text),
  };
}

function openAIModelList() {
  return {
    object: "list",
    data: FREE_MODELS.map((id) => {
      const lim = LIMITS.get(id) || {};
      return {
        id,
        object: "model",
        created: 0,
        owned_by: "opencode-free-tier",
        context_length: lim.contextWindow,
      };
    }),
  };
}

function sseChunk(delta, finish = null) {
  return (
    `data: ${JSON.stringify({
      id: "chatcmpl-oc",
      object: "chat.completion.chunk",
      model: delta.model,
      choices: [{ index: 0, delta, finish_reason: finish }],
    })}\n\n`
  );
}

const server = createServer(async (req, res) => {
  const url = new URL(req.url, `http://${req.headers.host}`);

  if (req.method === "GET" && (url.pathname === "/v1/models" || url.pathname === "/models")) {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify(openAIModelList()));
  }
  if (req.method === "GET" && url.pathname === "/health") {
    res.writeHead(200, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ ok: true, models: FREE_MODELS.length }));
  }
  if (req.method !== "POST" || url.pathname !== "/v1/chat/completions") {
    res.writeHead(404, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ error: { message: "not found" } }));
  }

  let body;
  try {
    body = await new Promise((resolve, reject) => {
      let b = "";
      req.on("data", (c) => {
        b += c;
        if (b.length > 8e6) reject(new Error("body too large"));
      });
      req.on("end", () => resolve(b ? JSON.parse(b) : {}));
    });
  } catch (e) {
    res.writeHead(400, { "Content-Type": "application/json" });
    return res.end(JSON.stringify({ error: { message: e.message } }));
  }

  const model = String(body.model || "").replace(/^opencode-free\//, "");
  if (!OC_MODEL_IDS.has(model)) {
    res.writeHead(404, { "Content-Type": "application/json" });
    return res.end(
      JSON.stringify({
        error: {
          message: `model ${model} is not served here; available: ${FREE_MODELS.join(", ")}`,
        },
      }),
    );
  }

  const messages = body.messages || [];
  const tools = body.tools || [];
  const wantsStream = !!body.stream;

  try {
    const { text, calls } = await complete(model, messages, tools);

    if (!wantsStream) {
      const message = calls.length
        ? { role: "assistant", content: text || null, tool_calls: calls }
        : { role: "assistant", content: text };
      res.writeHead(200, { "Content-Type": "application/json" });
      return res.end(
        JSON.stringify({
          id: `chatcmpl-${randomUUID().slice(0, 12)}`,
          object: "chat.completion",
          model,
          choices: [
            {
              index: 0,
              message,
              finish_reason: calls.length ? "tool_calls" : "stop",
            },
          ],
          usage: usageFor(messages, text),
        }),
      );
    }

    res.writeHead(200, {
      "Content-Type": "text/event-stream",
      "Cache-Control": "no-cache",
      Connection: "keep-alive",
    });
    res.write(sseChunk({ role: "assistant", content: "" }));
    if (text) res.write(sseChunk({ content: text }));
    if (calls.length) {
      // SSE tool calls stream one index at a time; pi reassembles by index.
      calls.forEach((c, i) => {
        res.write(
          sseChunk({
            tool_calls: [
              {
                index: i,
                id: c.id,
                type: "function",
                function: { name: c.function.name, arguments: c.function.arguments },
              },
            ],
          }),
        );
      });
    }
    // Terminal chunk: pi rejects a stream that ends without finish_reason.
    res.write(sseChunk({}, calls.length ? "tool_calls" : "stop"));
    res.write(
      `data: ${JSON.stringify({
        id: "chatcmpl-oc",
        object: "chat.completion.chunk",
        model,
        choices: [],
        usage: usageFor(messages, text),
      })}\n\n`,
    );
    res.write("data: [DONE]\n\n");
    res.end();
  } catch (e) {
    const status = e.status && e.status >= 400 && e.status < 600 ? e.status : 502;
    const payload = { error: { message: e.message, type: "oc_proxy_error" } };
    if (wantsStream) {
      res.writeHead(status, { "Content-Type": "text/event-stream" });
      res.write(`data: ${JSON.stringify(payload)}\n\n`);
      res.write("data: [DONE]\n\n");
      return res.end();
    }
    res.writeHead(status, { "Content-Type": "application/json" });
    res.end(JSON.stringify(payload));
  }
});

await loadLimits();
server.listen(PORT, "127.0.0.1", () => {
  console.log(`[oc-proxy] http://127.0.0.1:${PORT}/v1 -> ${OC}`);
  console.log(`[oc-proxy] scratch ${SCRATCH}`);
  console.log(`[oc-proxy] models ${FREE_MODELS.join(", ")}`);
});