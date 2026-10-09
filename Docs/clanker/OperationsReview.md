# Operations review — StatefulClanker fleet harness

Author: W05 ("Ledger") · Task `t-0005` · 2026-10-08
Scope: `Tools/clanker-fleet/squadron.mjs`, `Tools/clanker-fleet/squadron-op.mjs`,
`Tools/clanker-fleet/supervise.mjs`, and the installed StatefulClanker extension.
Method: static review of the sources plus the recorded fleet results in
`Docs/clanker/ModelDossier.md`. No compiler or test runner is available
(`WorkerBrief.md` §Toolchain), so every claim below is from reading code or
recorded run output; none is from a live execution.

**The harness was not modified. This document is the only change.**

### Path shorthands

- `SQ` = `Tools/clanker-fleet/squadron.mjs`
- `OP` = `Tools/clanker-fleet/squadron-op.mjs`
- `SV` = `Tools/clanker-fleet/supervise.mjs`
- `SC` = `C:\Users\Chris\.pi\agent\git\github.com\bobcatchris15-eng\StatefulClanker`
  (the installed extension; not part of this repo)

---

## 1. Constraints that actually bite

These are the four facts a new operator hits first. Three are encoded only in
comments, which is why the harness exists rather than documentation.

### 1.1 The operator must outlive its launcher

StatefulClanker ties worker lifetime to the operator process. On
`session_shutdown` the extension stops every worker it spawned
(`SC/operator.ts:71-74`, which loops `mgr.runtime(w.id)?.stop()`). A short-lived
launcher therefore kills its own fleet on exit. `SQ:11-13` states the
consequence for `pi -p`, and `OP:4-6` repeats it as the design reason for the
module. The mitigation is a long-lived `pi --mode rpc` operator (`OP:20-25`) with
`stdio` piped, and `up` stays resident and watches because the operator's stdin
is what keeps the supervisor alive (`SQ:199-205`).

This is the constraint that most changes how you operate: you cannot fire a
squadron and walk away from the shell running `up`. See §2.3 for the escape
hatch that appears to contradict it.

### 1.2 Prompts must use `streamingBehavior: "followUp"` or they vanish

A bare prompt delivered while the operator is mid-turn is rejected with
`"Agent is already processing. Specify streamingBehavior ('steer' or 'followUp')
to queue the message."` and is silently dropped — no error surfaced to the
caller. `OP:70-78` hard-codes `streamingBehavior: "followUp"` in `ask()` for
exactly this reason. `Docs/clanker/ModelDossier.md` records four of six prompts
lost this way in the first fleet. Any new caller that hand-rolls a prompt
instead of going through `ask()` re-opens the bug.

### 1.3 `git worktree add` checks out ~777 files and dominates spawn latency

`SQ:137-139`: a worktree "checks out ~777 files and takes tens of seconds", so
`awaitNewWorker` waits **90 s** for a read-only task and **240 s** for a
worktree task; the same figure appears in `SV:121-123`. Two operational
consequences:

- Spawning is **sequential** (`SQ:173-175`), each worker awaiting up to 240 s per
  attempt with 2 attempts (`SQ:133-144`). A 6-worker spec can spend 40+ minutes
  just creating worktrees before any work runs. The `worktree: false` fast path
  is not a micro-optimisation — it is the difference between seconds and minutes
  per worker.
- A timeout is not proof the spawn failed; the registry is polled every 2 s
  (`SQ:99-110`), so a slow-but-successful spawn can be reported as failed if the
  machine stalls.

### 1.4 A pinned model is a request, not a guarantee

`SQ:14-16` records that the operator was asked to pin `fledge-alpha-free` and
spawned `exo-free` instead. The harness therefore never trusts the spawn call:
it diffs the resulting registry entry against the requested `provider/model` and
reports `PIN MISMATCH` / `WARNING: pin not honoured` (`SQ:141-143`, `182-193`).
`ModelDossier.md`'s secondary observation confirms the operator "follows
instructions loosely". `doctor()` also warns if a pinned model is absent from
`settings.enabledModels`, because selection will never choose it
(`SQ:53-63`). Verify the actual assignment in the registry; do not assume the
spec was honoured.

---

## 2. Fragile or surprising for a new operator

### 2.1 `up` says it leaves a previous operator alone, then orphans it

When a prior operator is live, `up` logs *"operator from a previous run is still
live … leaving it alone"* (`SQ:163-166`) — but the very next line unconditionally
spawns a fresh operator (`SQ:168-169`), and `spawnOperatorWithPipe` overwrites
`operator.json` (`OP:66`). Net effect: the old operator keeps running with its
workers, but it is no longer the recorded one. `lastOperator()` and `down()`
only see the newest (`SQ:72-77`, `271-280`), so `down` can leave the older
operator's workers alive and report success. The wording "leaving it alone" is
misleading; the behaviour is "start another one and forget the first".

### 2.2 `shell: true` means the recorded pid is the shell, not `pi`

`spawnOperatorWithPipe` launches via `{ shell: true }` (`OP:24`) and stores
`child.pid` (`OP:66`). On Windows that pid is `cmd.exe`, so `alive()`
(`SQ:26`) tests the shell and `child.kill()` targets the shell — the grandchild
`pi --mode rpc` process can survive. This is exactly why `down` falls back to
*"kill stray pi --mode rpc processes by hand"* (`SQ:276`). Treat `operator.json`
as a hint, and check for orphaned `pi` processes after a teardown.

### 2.3 `SQUADRON_NO_WATCH` appears to defeat the constraint it sits under

The comment at `SQ:199-201` is explicit that the operator must outlive the
launcher; the `if (!process.env.SQUADRON_NO_WATCH)` branch then stays resident and
watches (`SQ:202-205`). With `SQUADRON_NO_WATCH` set, `up` falls through, returns,
and the Node process exits, closing the write end of the operator's stdin pipe —
the documented failure mode. Either the flag is broken or it needs a detached
re-parenting strategy; it is not referenced anywhere else in the repo, so it is
an untested escape hatch. Do not use it expecting the fleet to survive.

### 2.4 Documented commands that are not wired up

- `detach` is listed in the header (`SQ:24`) but has no dispatch branch
  (`SQ:325-333`); it falls through to the help text.
- `supervise` is documented as `node squadron.mjs supervise …` (`SV:20`) but
  `squadron.mjs` never references `supervise`. To use the safety net you must
  invoke `supervise.mjs` directly. Since `supervise.mjs` is the only thing that
  notices a silent give-up (see §3.2), the gap matters: `up` alone does not run
  it.

### 2.5 `watch()` never exits if the registry is empty

`SQ:233` only settles when `ws.length && settled + ok >= ws.length`. With zero
workers the guard is false forever, so `watch()` loops on a 15 s sleep
indefinitely. Cosmetic, but it means `up` on an empty registry hangs rather than
returns.

### 2.6 `integrate` can clobber your working tree

`integrate()` copies every uncommitted, non-`.clanker` file from a worker's
worktree over the repo root (`SQ:307-322`) with no dirty-tree check and no scope
validation. If the operator has uncommitted edits to the same paths, they are
overwritten silently. `harvest` at least lists uncommitted files first
(`SQ:283-305`); `integrate` does not.

### 2.7 Cancellation is best-effort and time-boxed

`cancelAll` sends a cancel/retire prompt per worker, sleeps a fixed 4 s, then
kills the operator child (`OP:82-91`). Prompts have a 120 s default timeout
(`OP:57-60`), but the fixed sleep means a slow retire can be cut off by the kill.
There is no verification that a worker actually reached `CANCELLED`.

### 2.8 Observability gaps

- `operator-events.jsonl` records only the event `type`, discarding the payload
  (`OP:46-49`). Fine for a heartbeat trace, useless for post-mortem.
- The LF-framing parser deliberately drops unparseable lines (`OP:42-43`); this
  is the right call given `readline` splits on U+2028/U+2029 (`OP:30-31`), but a
  malformed record disappears without a counter.
- `doctor()` reads a global `~/.pi/agent/settings.json` and only checks the
  proxy when an `opencode-free/` model is pinned (`SQ:53-70`); a project-local
  configuration would not be seen.

---

## 3. Two concrete defects in the StatefulClanker extension

### 3.1 Single-sample nudge rewrites a curated rating but not its source tag

`SC/catalog/profiles.ts` resolves each capability in layers: `derived`
(`:80`), then `curated` (`:84-87`, which sets `source[c] = "curated"`), then
`observed` (`:92-107`). When an aggregate has at least `minSamples` (default 8,
`:75`) observations, the rating is recomputed and `source[c] = "observed"`
(`:100`). The defect is the small-sample branch:

```
:101      else if (ratings[c] !== "unknown") {
:102        const i = STEPS.indexOf(ratings[c]);
:103        const j = sr >= 0.9 ? Math.min(3, i + 1) : sr < 0.5 ? Math.max(0, i - 1) : i;
:104        ratings[c] = STEPS[j]!;
:105      }
```

For `n < minSamples` — including `n === 1` — this branch **mutates
`ratings[c]` by one step based on a success rate with no statistical weight, and
never touches `source[c]`**. A curated `good` becomes `excellent` after a single
success while `source[c]` still reads `"curated"`, i.e. the provenance tag now
lies about a value that was in fact machine-adjusted. `derived` ratings are
nudged the same way while still tagged `"derived"`. The wrong tag is
user-visible: `SC/catalog/service.ts:144` prints `rating(source)` in the explain
output, and `select.ts:34` consumes the resolved profile.

Fix candidates (not applied): require a minimum sample count before any nudge,
or set a distinct source such as `observed(n=1)`/`observed-low-confidence` so
downstream code can tell a human rating from a one-sample adjustment.

### 3.2 A receipt exists only if the worker calls `worker_finish`

`worker_finish` is a tool the worker must actively call
(`SC/worker.ts:62-74`); the worker only emits an `SC1` `{kind:'finish'}` notify,
and the manager writes the receipt when it receives it. In
`SC/workers/manager.ts`:

- `onSc` returns early for anything that is not `finish` (`:142`).
- Only on `finish` does it build the result, write
  `receipts/workers/<id>-<ts>.json` (`:152-153`), append `worker.completed`
  (`:155`), and set status `COMPLETE`.
- `onExit` (`:161-167`) marks the worker `LOST` and emits `worker.failed` but
  writes **no receipt**.

Worse, a worker that simply ends its turn without finishing is not even `LOST`:
`SC/workers/status.ts:21-24` maps `agent_end` to `IDLE` when `finished` is false,
and only a process exit maps to `LOST` (`:33-36`). A clean give-up therefore
looks idle and receipt-less. The fleet tools surface the empty result —
`show` prints `(no receipt - worker did not call worker_finish)` (`SQ:264`) and
`watch` reports `no receipt` (`SQ:236`) — but nothing recovers the task.
`SV:12-13` names this precisely: *"A worker that ends its turn without calling
worker_finish leaves no receipt. The task is silently lost - there is no timeout
that notices."* This is `W04`'s outcome in `ModelDossier.md`: the task was lost
entirely because the model ended its turn without finishing.

The only mitigation in the harness is the optional `supervise.mjs`, which
heartbeats and re-dispatches dead tasks (`SV:3-17`) — and per §2.4 it is **not**
invoked by `up`. A new operator running `up` alone has no protection against a
silent give-up.

---

## 4. Recommendations (for a future change; nothing here was applied)

1. Make the no-receipt loss survivable: run `supervise` by default, or have the
   manager write a synthetic `LOST`/`IDLE` receipt on `agent_end`/`onExit` so the
   task record shows an outcome instead of silence.
2. Fix the provenance lie in `profiles.ts`: any nudge must update `source`
   (ideally to a low-confidence observed tag) or be suppressed below a sample
   threshold.
3. Stop minting a second operator on `up` when a live one exists, or record all
   operator pids and make `down` cancel through each; fix the "leaving it alone"
   wording.
4. Drop `shell: true` so `child.pid` is the `pi` process; this removes the stray
   `pi --mode rpc` cleanup problem.
5. Either implement/re-parent `SQUADRON_NO_WATCH` or remove it.
6. Wire up or delete the documented `detach` and `supervise` command names.

## Verification notes

- Findings are static. `WorkerBrief.md` states the engine is reinstalling and
  MSVC/clang/gcc are absent, so no build or test was attempted.
- `SC/` files were read from the installed extension at
  `C:\Users\Chris\.pi\agent\git\github.com\bobcatchris15-eng\StatefulClanker`
  (extension commits are outside this repo; line numbers are as installed on
  2026-10-08).
- No file under `Tools/clanker-fleet/` or `.statefulclanker/` was modified.
