# Model dossier — behavioural fingerprints

Standing record of how individual models actually behave when driven through
`Tools/oc-proxy`, versus pi's native tool calling.

Kept because these models are worth knowing before trusting them. Entries are
observations with the method that produced them, not impressions. Anything
unverified is marked so.

---

## Harness under test

`Tools/oc-proxy` translates pi's OpenAI requests into OpenCode session turns,
because OpenCode's free tier rejects anything that did not originate from an
OpenCode session (`FreeTierError`, 403, enforced server-side; header spoofing
does not defeat it).

Consequences:

- **Tool calling is emulated.** pi's tool schemas go into the system prompt; the
  model is asked to emit a fenced ```tool_call block; the proxy parses it back
  into OpenAI `tool_calls`.
- **Streaming is synthetic.** A full turn is one delta, so time-to-first-token
  equals total turn latency and cancellation cannot be honoured mid-stream.
- **OpenCode's own tools remain live.** In the OpenCode message API, `tools: {}`
  means *no overrides*, not *no tools*.

---

## Security finding — file reach (resolved)

**Observation.** With the proxy's OpenCode session root placed inside the repo,
`exo-free` read `Source/TheWood/Public/Generation/WoodStreaming.h` and returned
its first two lines **without emitting a single tool call**. The proxy request
carried no tool permission at all; the read happened through OpenCode's built-in
agent tools.

**Why it matters.** A StatefulClanker worker is supposed to be confined to its own
git worktree. A model with ambient read access resolves relative paths against the
operator's tree instead, so receipts could describe files the worker never touched
— worktree isolation defeated without any error.

**Fix.** OpenCode resolves relative paths upward to a detected project root, so
the session root now lives in a per-process temp directory outside every repo:

```
scratch C:\Users\Chris\AppData\Local\Temp\oc-proxy-scratch-a02affe1
```

Re-tested after the fix: the same request returns `UNREADABLE`. Containment is
enforced by session location, not by prompt.

**Residual risk.** OpenCode's tools cannot be switched off through this API
without rerouting to `opencode.ai/inference`, which returns 403 for the free
tier. Prompt-based suppression is defence in depth only. Do not treat the proxy
as a sandbox.

---

## exo-free

**Verdict so far: the strongest free model in the pool, but it takes shortcuts.**

- **Ambient file read (see above).** Reached repo files with no tool call.
- **Honest summary under test.** Asked to read `WoodHex.h` and describe it, it
  returned an accurate account: `namespace wood::hex`, `radius=950`,
  `halfWidth=100`, the 19-element influence array, cube rounding with the
  largest-error fixup, the `|x|,|y| > 2,000,000` guard, and `t*t*(3-2*t)`
  correctly identified as smoothstep. Checked line by line against the file: no
  errors. This is unusually precise for a 32K-context free tier.
- **Fails the worker naming protocol.** In a full StatefulClanker run it skipped
  `worker_name` entirely (`display_name` came back undefined) while still calling
  `worker_finish`. Compliant with the mandatory part, silent on the rest.
- **Operates a second, invisible tool surface — and says so.** Asked for the current
  time, it returned *"The system clock reported October 6, 2026, at 9:14:16 PM
  (UTC−05:00). I got it by running PowerShell's `Get-Date` command"*, with **zero**
  OpenAI-level tool calls. The command genuinely ran — through OpenCode's native
  shell, inside the per-process temp root, where it has no access to the repo.
  **Correction:** this was initially recorded here as fabricated provenance. It is
  not. The claim is true and the tool call is real; it is simply invisible in the
  OpenAI transcript, because it happens on the OpenCode side.
  The practical lesson is about the *transcript*, not the honesty: a `tool_calls:
  none` signal from this proxy does **not** mean the model did nothing, and an
  answer produced this way is not independently reproducible through pi.
- **Protocol compliance is prompt-sensitive.** With a weak instruction it answers
  in prose and skips the tool block. With an explicit "your entire reply must be
  the block" instruction it complies reliably for pi-level tools.
- **Latency.** 1.9s–9s for trivial prompts.

**Second tool surface.** Every model on this path inherits OpenCode's built-in
tools — `bash`/`read`/`grep`/`glob` and friends — rooted at the temp directory.
They are confined by *location*, not by configuration: `tools: {}` in the message
API means "no overrides", so switching them off through this API is not possible
without rerouting to `opencode.ai/inference`, which 403s the free tier.
This means the proxy can do real compute, but not real repository work.

---

## Fleet results — 2026-10-07 (first parallel fleet)

Five workers, six planned. The split by model produced an unambiguous result.

| Worker | Model | Outcome |
|---|---|---|
| W01 | `opencode-go/space-bunny` (paid) | **COMPLETE in 4m02s.** 8 reads, 9 bashes, `worker_name`, `worker_progress`, `worker_finish`. Full protocol compliance. |
| W02 | `opencode-free/exo-free` | ~8 min, ~1 tool call. No receipt. |
| W03 | `opencode-free/fledge-alpha-free` | ~8 min, 0 tool calls. No receipt. |
| W04 | `opencode-free/space-bunny-free` | Ended turn without `worker_finish`. **No receipt, task lost.** |
| W05 | `opencode-free/nemotron-3-ultra-free` | ~8 min, ~1 tool call. No receipt. |

**The proxy cannot host a worker.** W01 completed a task requiring dozens of tool
calls in four minutes. The free workers managed roughly one tool call per eight
minutes, and one of them abandoned the task entirely.

The cause is the synthetic-stream design, not model quality. Every tool call is a
full round trip: pi asks, the proxy blocks on a complete OpenCode session turn
(2s–40s measured), and only then returns. A worker needs a *sequence* of tool
calls, so cost multiplies. An audit that took W01 twenty tool calls would take a
free worker hours, and one that gave up produced no receipt at all — the task is
silently lost because a receipt is only written on `worker_finish`.

W04 is the sharpest data point: `space-bunny-free` is the fastest and cleanest
model in the pool (1.4s, clean output, no observed defects) and **still** could
not finish a task through this path. That isolates the fault to the transport.

**Conclusion: paid `opencode-go` models are the only viable worker fleet here.**
They use pi's native tool calling with no proxy in the path. Keep the proxy for
short single-turn work, where its latency is irrelevant.

### Secondary observation — the operator follows instructions loosely

Dispatched with explicit per-worker parameters, the operator spawned task #1 and
task #4 correctly but assigned the wrong model to task #2 (`exo-free` where
`fledge-alpha-free` was specified, because the model pin was dropped). Verify
worker-to-task assignment in the registry after spawning; do not assume the
requested mapping was honoured.

### Also worth recording

Four of six prompts were rejected with `"Agent is already processing. Specify
streamingBehavior ('steer' or 'followUp') to queue the message."` Prompts fired at
4-second intervals raced the operator's turn and were silently dropped. Queue with
`streamingBehavior: "followUp"` and allow ~40s per worktree creation (777 files
checked out each).

---

## fledge-alpha-free

**Verdict so far: unreliable output quality; use only as a subject, not a worker.**

- **Output corruption on trivial input.** Asked to reply `PONG`, it returned
  `PONGPong: PONGONG`. Token-level duplication on a one-word instruction is a bad
  sign for instruction-following generally.
- **Latency.** 2.5s–5s on the same corpus where `space-bunny-free` ran at 1.4s.
- **Not yet characterised** on: accuracy, tool-protocol compliance, instruction
  adherence under a long brief, or whether it fabricates results the way exo-free
  does. It is pinned to fleet task 2 precisely to gather this.

**Operational guidance.** Do not assign billable or correctness-critical work.
Rate cap in `.statefulclanker/profiles.json` is `fair` across coding and tool_use
until real data exists.

---

## Other models in the pool

Baseline compliance, trivial prompt, proxy path, 2026-10-07:

| Model | Latency | Note |
|---|---|---|
| `space-bunny-free` | 1.4s | fastest, cleanest |
| `muse-spark-1.3-contributor-free` | 2.0s | 63s observed on a separate run |
| `mimo-v2.6-flash-free` | 2.7s | |
| `nemotron-3-ultra-free` | 2.6s | 1M ctx |
| `longcat-2.5-preview-free` | 4.4s | |
| `big-pickle` | 7.3s | 200K/32K |
| `ling-3.1-flash-free` | 7.7s | |
| `nemotron-3.5-lightning-free` | 39.5s | highly variable (2.7s–39s) |

`ling-3.0-flash-fin-free` is excluded from the proxy entirely: upstream
OpenCode returns `Endpoint is unavailable` after ~70s.

Latency here is dominated by the synthetic-stream design, not by the models.

---

## Open questions

1. Does fledge-alpha fabricate provenance the way exo-free does?
2. Can the tool protocol be made robust enough that free models are usable as
   unattended workers at all?
3. Is the "Prompt caching" field the proxy sends ever populated? OpenCode's own
   token counters report 2–4 input tokens for a full 17k system prompt, which
   makes per-model cost comparisons meaningless on this path.
4. Does any free model actually emit `reasoning_content`? If so, pi's `/thinking`
   control has something to act on and the `reasoning: true` flags in
   `models.json` are honest.