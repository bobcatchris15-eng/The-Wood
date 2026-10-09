# oc-proxy — OpenCode free models for pi

Bridges pi to OpenCode's zero-cost models. OpenCode's free tier rejects requests
that do not originate from an OpenCode session, so the only working path is
through a running OpenCode server. This proxy translates pi's OpenAI-style
requests into OpenCode session turns.

## Layout

| File | Purpose |
|---|---|
| `proxy.mjs` | The server. OpenAI `/v1` on `:4097` → OpenCode on `:4096`. |
| `probe.mjs` | Health probe: every model plus a tool round trip. |
| `start.sh` | Idempotent launcher. |
| `~/.pi/agent/models.json` | Registers the models with pi as provider `opencode-free`. |

## Usage

```bash
bash Tools/oc-proxy/start.sh                    # start (needs OpenCode on :4096)
node Tools/oc-proxy/probe.mjs                   # verify all models
pi --model opencode-free/exo-free               # use one
```

Check the upstream is alive: `curl -s http://127.0.0.1:4096/global/health`

## Models (10, all $0)

`big-pickle` `exo-free` `fledge-alpha-free` `ling-3.1-flash-free`
`longcat-2.5-preview-free` `mimo-v2.6-flash-free`
`muse-spark-1.3-contributor-free` `nemotron-3-ultra-free`
`nemotron-3.5-lightning-free` `space-bunny-free`

Verified 10/10 responding, 2026-10-06.

### Not served

- **`ling-3.0-flash-fin-free`** — dead upstream. OpenCode itself returns
  `Endpoint is unavailable` after ~70s. Verified against `:4096` directly, so
  this is not a proxy defect. Re-test with `probe.mjs` if OpenCode revives it.

## Design notes

Three things are load-bearing and easy to break:

1. **`tools: {}` must stay empty.** Setting any entry to `false` reroutes the
   upstream call to `opencode.ai/inference/openai/v1` instead of
   `opencode.ai/zen/v1`, which returns `403 FreeTierError`. OpenCode's native
   tools are suppressed through the system prompt instead.

2. **Sessions are keyed on the opening turn**, not a slice of message content.
   Two conversations that start alike must not share a session, or the second
   one sees an empty delta and returns blank text.

3. **OpenCode's token accounting is unusable on this build.** It reports 2-4
   input tokens for a full 17k-token system prompt. The proxy recomputes usage
   from the text it sent and received; pi's cost display would otherwise be
   nonsense.

## Fidelity limits

Read these before trusting output.

- **Streaming is synthetic.** OpenCode returns a completed turn, so the full
  answer is delivered as one delta after the turn finishes. Time-to-first-token
  equals total turn latency — typically 3-10s, but `muse-spark` was seen at 63s
  and `ling-3.1` at 23s. A cancellation mid-stream cannot be honoured upstream.
- **Tool calls are emulated by prompt, not native.** Pi's tool schemas are
  passed in the system prompt and the model is asked to emit a fenced
  ```tool_call block, which the proxy parses into OpenAI `tool_calls`. Small
  free models follow this inconsistently; a model may answer in prose instead
  of calling a tool. Round trips do work when the model complies.
- **No reasoning/thinking blocks.** These models report
  `reasoning: true` upstream but their chains of thought are not surfaced.
  Pi's `/thinking` control has nothing to act on.
- **Context windows are declared, not enforced.** The advertised limits come
  from the OpenCode catalog. OpenCode applies its own compaction and will not
  error the way a direct API would.
- **Per-conversation sessions are held in memory** and grow unbounded for the
  life of the process. Restart to clear.

## Safety

The proxy runs OpenCode sessions against a scratch directory
(`<repo>/.oc-proxy-scratch`), not the repository, so OpenCode's own agent loop
cannot edit project files. Pi still executes its own tools normally — verified:
a write issued through the proxy landed on disk as expected.