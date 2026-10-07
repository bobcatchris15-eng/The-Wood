#!/usr/bin/env node
/**
 * Exercises every model the proxy exposes, plus the tool-call round trip.
 * Run the proxy first, then: node Tools/oc-proxy/probe.mjs
 */

const P = process.env.OC_PROXY_URL || "http://127.0.0.1:4097/v1";

const post = async (body) => {
  const r = await fetch(`${P}/chat/completions`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  return { status: r.status, body: await r.json() };
};

const list = await (await fetch(`${P}/models`)).json();
const models = list.data.map((m) => m.id);
console.log(`probing ${models.length} models via ${P}\n`);

const results = [];
for (const model of models) {
  const t0 = Date.now();
  try {
    const { status, body } = await post({
      model,
      messages: [{ role: "user", content: "Reply with exactly: PONG" }],
    });
    const text = body.choices?.[0]?.message?.content ?? "";
    const ok = status === 200 && /pong/i.test(text);
    results.push({ model, ok, status, ms: Date.now() - t0, note: text.slice(0, 40) });
  } catch (e) {
    results.push({ model, ok: false, status: "ERR", ms: Date.now() - t0, note: e.message.slice(0, 40) });
  }
}

console.log("model".padEnd(32), "ok".padEnd(5), "ms".padEnd(7), "note");
for (const r of results)
  console.log(
    r.model.padEnd(32),
    (r.ok ? "yes" : "NO").padEnd(5),
    String(r.ms).padEnd(7),
    r.note.replace(/\n/g, " "),
  );

console.log(`\n${results.filter((r) => r.ok).length}/${results.length} models respond correctly`);

// Tool round trip: request a call, feed a result back, expect prose.
console.log("\n--- tool round trip (exo-free) ---");
const tools = [{ type: "function", function: { name: "get_time", description: "Get current time" } }];
const first = await post({
  model: "exo-free",
  messages: [{ role: "user", content: "Use the get_time tool to get the time." }],
  tools,
});
const call = first.body.choices?.[0]?.message?.tool_calls?.[0];
console.log("tool_calls:", call ? `${call.function.name}(${call.function.arguments})` : "none");
if (call) {
  const second = await post({
    model: "exo-free",
    tools,
    messages: [
      { role: "user", content: "Use the get_time tool to get the time." },
      { role: "assistant", content: null, tool_calls: [call] },
      { role: "tool", tool_call_id: call.id, name: "get_time", content: "12:00 UTC" },
    ],
  });
  const txt = second.body.choices?.[0]?.message?.content ?? "";
  console.log("follow-up:", txt.slice(0, 160).replace(/\n/g, " "));
}