# Streaming Defect Triage — 2026-10-07

Status: triage only. **This document adds no source changes.** It verifies twelve
findings raised by three separate audits against the live tree, reorders them by the
acceptance language in [Specification.md](../../Specification.md) §12 and §7, and
fixes a dependency order.

Date: 2026-10-07. Subjects:

- `Source/TheWood/Private/WoodWorldStreaming.cpp` (the Unreal adapter, 93 lines)
- `Source/TheWood/Private/Generation/WoodStreaming.cpp` + `Public/Generation/WoodStreaming.h` (the pure planner)
- `Source/TheWood/Private/WoodPreparedChunk.cpp`, `WoodRuntime.h`, `WoodWorld.cpp`
- `Source/TheWood/Private/Tests/WoodRuntimeTests.cpp`, `WoodInstanceRetentionTests.cpp`

## 0. Method, and what could not be verified

Every claim below was re-derived by reading the files named above. Line numbers
refer to the live tree at `30c6424` plus the uncommitted working state; the copies
under `.statefulclanker/worktrees/W06` and `W07` are byte-identical for these two
streaming files, so all workers audited the same code.

**Two limits apply to everything in this document, per `Docs/clanker/WorkerBrief.md`:**

- **No C++ compiler is present on this machine.** No test in `Tests/` or
  `Source/TheWood/Private/Tests/` was executed. All timing figures are arithmetic
  over the code, not measurements, and are labelled as such.
- **Unreal Engine 5.8 is reinstalling; its source is not on disk.** Two claims
  that depend on engine internals — `TFuture::IsReady()` after a consumed future,
  and `.clanker/REVIEW.md:53`'s assertion that HISM `ApplyBuildTree` clears
  instance-ID tracking — **could not be checked** and are marked *unresolved*
  rather than confirmed or refuted. Both appear in §3 (H4) and §3 (L1) and neither
  triage verdict depends on the answer.

One item was **not provided**: the finding list jumps `L1 → L3 → L4`. Whatever
`L2` said is not triaged here and must not be assumed covered.

## 1. Verdicts at a glance

| ID | Claim | Verdict | One-line correction |
|---|---|---|---|
| **H1** | Null pawn collapses the window to the origin and unloads everything in one tick | **Real, mechanism confirmed** | Correct — but "everything" is only true beyond 6 chunks (768 m) from the origin, which is why no test catches it. It also *causes* an H2 stall. |
| **H2** | ~21k-sample synchronous generation on the game thread | **Real** | The count is right (21,125). "Every boundary crossing" is wrong — it fires on teleports, on outrunning the queue, on H1 frames, and 9× at `BeginPlay`. |
| **H3** | Background jobs compute mesh attributes that are discarded | **Real, narrower than stated** | Only the *second* attribute pass is wasted (after a terrain-only realise), it is off-thread, and its size equals H2's fallback count. |
| **H4** | A throwing job wedges into a permanent crash loop | **Real** | Confirmed, and it holds regardless of the unverified `IsReady()` semantics. |
| **M1** | Per-frame deep copy of the profile table | **Real mechanism, overstated severity** | It is per *dispatch* (≤2/tick), kilobyte-scale, and required by the value-capture design. |
| **M2** | No cancellation path for queued work | **Real** | Correct, and it compounds M3 rather than causing starvation alone. |
| **M3** | One chunk realised per tick in non-deterministic map order | **Real code, overstated as today's bottleneck** | The drain cap is real and `TMap` order is arbitrary, but at current per-chunk cost the *2-job concurrency* binds first. M3 becomes the bottleneck only **after** H2 is fixed. |
| **M4** | `retained()` / `Plan.removed` / `maxConcurrentJobs` have no runtime caller; chunk size tripled | **Real** | Verified, plus a fourth item the audit missed: three *different* radii live in one function. |
| **M5** | `Plan.removed` cannot cover terrain-only chunks | **Real but latent** | No live bug — the adapter does not use `Plan.removed`. It becomes a bug the moment M4 is "fixed" naively. |
| **L1** | Instance identity is an array slot | **Wrong as stated** | Removal is by stable `FPrimitiveInstanceId`, not by slot. The real (smaller) issue is an unasserted `Placements`/`Vegetation` coupling. |
| **L3** | `LoadedChunkCount` over-reports | **Weak / unproven** | It has **no caller at all**. "Over-reports" is only true against an unwritten contract. |
| **L4** | Invariants enforced by exceptions out of `Tick` | **Real, systemic** | Correct, and it is the enabling condition for H4. But the atmosphere trigger raised by the 2026-10-06 review is **refuted**, and the remaining live triggers all need a non-finite position. |

## 2. The numbers the severities rest on

Verified by counting, not measuring:

- A chunk is `(cells+1)² = 65×65 = 4,225` vertices at `cells=64`
  (`WoodGeneration.cpp:151`, `WoodWorld.cpp:37`).
- `WoodPrepareChunk` makes **5 `World::sample()` calls per vertex** —
  `WoodPreparedChunk.cpp:15-17`: one for the surface, four for the finite-difference
  normal. `4,225 × 5 = 21,125` samples. **The audits' "21k" is exact.**
- Each `sample()` performs one `climate()` (hex warp + up to 19 cells × 6 margin
  dots) and **five `ground()` calls** (`WoodGeneration.cpp:118-120`), each `ground()`
  running ≈9 `noise()` evaluations ≈36 hashes. So ≈3.8 M hash evaluations plus the
  hex weights per terrain-only chunk. **Order 10² ms of game-thread work** — the
  arithmetic is shown so it can be checked; it is not a measurement.
- A detailed job adds three feature layers (`WoodGeneration.cpp:268-270`: 8.5 m,
  1.5 m, 6 m lattices) each calling `sample()` per candidate point, plus discovery
  planning over 19 hex cells (`WoodGeneration.cpp:175-192`). A detailed chunk is
  several times the cost of a terrain-only one.

## 3. Verification, finding by finding

### H1 — null pawn recentres the window on the origin · **REAL**

`WoodWorld.cpp:129-131` substitutes `FVector::ZeroVector` for a missing pawn and
calls `Stream()`. `WoodWorldStreaming.cpp:61` then derives the streaming centre
from that vector.

The consequence is more precise than "unloads everything": `WoodWorldStreaming.cpp:64`
destroys every resident outside `ChunkRadius+2` = **6 chunks = 768 m** of the
origin. The default start is `ExplorerStart()` = `(-180, -180)` m
(`WoodWorldStreaming.cpp:14-17`), i.e. chunk `(-2,-2)` — inside 768 m of the
origin. **That is precisely why every runtime test passes.**

`Wood.Runtime.GroundAndObservation` performs the defect on every run at
`WoodRuntimeTests.cpp:26`: `Fixture.TickTestWorld()` executes with no player
controller and no pawn in the world. The nine `BeginPlay` chunks survive because
they sit within 6 chunks of `(0,0)`.

**The corrected claim:** a null pawn does three things in one tick — it centres the
window on the origin, it synchronously generates chunk `(0,0)` (an H2 stall on a
chunk unrelated to the player, via `WoodWorldStreaming.cpp:60 → :22`), and it
dispatches up to 2 jobs per tick toward the origin for as long as the pawn stays
null. Once a player has travelled more than 768 m from the origin — about three
minutes at the 4.2 m/s walk speed of `WoodCharacter.cpp:26` — a single null-pawn
frame destroys up to 169
resident chunks (component destroy + `RemoveInstancesById` on shared ISM), and the
next valid-pawn frame rebuilds them.

This is the highest-severity finding because it is a correctness failure, not a
performance one, and the fix is a single branch.

### H2 — synchronous ~21k-sample generation on the game thread · **REAL**

`WoodWorldStreaming.cpp:22` calls `WoodPrepareChunk` inline on the game thread. The
count is exact (§2). **The trigger description in the audit is wrong, and the
difference matters for the fix.**

`EnsureTerrainAround` only runs when the chunk is *not resident*
(`WoodWorldStreaming.cpp:21`). The planner requests chunks within
`desiredRadius = ChunkRadius = 4` (`WoodWorldStreaming.cpp:74`), i.e. 512 m ahead.
At walking speed the player's own chunk is therefore normally already resident and
the fallback does **not** fire on an ordinary boundary crossing. It fires on:

1. **Teleports and debug moves** — the path both runtime tests exercise
   (`WoodInstanceRetentionTests.cpp:77`, `WoodRuntimeTests.cpp:56`).
2. **Outrunning the queue** — which M3's one-per-tick drain makes *more* likely, so
   H2 and M3 are coupled (§6, Group C).
3. **Every null-pawn frame** (H1) — generating chunk `(0,0)`.
4. **Nine times at `BeginPlay`** — `WoodWorld.cpp:123` realises a 3×3 block
   synchronously, with `Details=true`, so it is the *expensive* path, before
   `Stream()` even runs.

`t-0006`'s brief frames this as "every chunk-boundary crossing and once at
BeginPlay". **The BeginPlay half is right and understated (9×, with features); the
boundary-crossing half is wrong and would aim the fix at the wrong trigger.**

There is a second, smaller stall in the same code path that no audit named:
`WoodWorldStreaming.cpp:41` calls `Generator.sample()` 65 times inside the water
ribbon loop of every `Realize()`, and `:39` calls `streamX`/`streamHalfWidth` 65
times. That is 65 extra full samples per chunk realisation on the game thread, and
`streamHalfWidth` runs `validatePoint`, so it is another throw site (§L4).

`CreateMeshSection_LinearColor(..., true)` at `WoodWorldStreaming.cpp:34` also
cooks collision synchronously, so each realisation compounds the sampling cost with
a trimesh cook. This is a distinct, already-documented item
(`.clanker/CLAUDE_REVIEW.md` `streaming-4`) and belongs in the same fix.

`Docs/Status.md:9`'s claim that "Runtime object realization stays separate from
background value generation" is contradicted by `:22` and `:123`. That is a
documentation defect, not a code defect, but §11 forbids it.

### H3 — background jobs compute mesh attributes that are discarded · **REAL, NARROWER**

The mechanics: `Realize` builds the ground mesh **once**, inside
`if(!Resident.Ground)` (`WoodWorldStreaming.cpp:28-51`), consuming
`Prepared.Normals`, `Prepared.HabitatUV` and `Prepared.BiomeColors` at `:32`. On a
later detailed realise of the same chunk, `Ground` is non-null, that block is
skipped, and `:52` returns only after adding vegetation. The detailed job's
attribute arrays are dropped.

**Three corrections:**

1. **It is not every background job.** It is exactly one wasted attribute pass per
   chunk that was first realised terrain-only by `EnsureTerrainAround` — the same
   set of chunks that already paid H2's game-thread cost. Its magnitude is
   therefore *H2's fallback count*, not 81 and not the whole window.
2. **It is off the game thread.** It does not stall a frame directly; it stalls
   the two worker slots, which extends the post-teleport refill. The §12 impact is
   real but indirect and second-order — it should not be ranked with H2.
3. **The `Placements` half is not wasted.** `:53-56` consumes them.

There is a related waste the audits missed: `WoodPrepareChunk` computes the full
attribute set even when `Details=false`
(`WoodPreparedChunk.cpp:14-22`, unconditional; the `!Details` early-out is at
`:24`, *after* the loop). The terrain-only fallback therefore pays 21,125 samples
to produce normals it does use — so that half is necessary — while the *second*
pass is pure waste.

### H4 — a throwing background job wedges into a permanent crash loop · **REAL**

`WoodWorldStreaming.cpp:63` calls `Get()` **before** `Remove(Key)`. If the task
body throws, the exception escapes `Get()`, propagates out of `Stream()` and out of
`AWoodWorld::Tick`, and the key is never removed. There is no `try`/`catch`
anywhere in the file.

**The wedge holds under either answer to the unverified `IsReady()` question:**

- If `IsReady()` keeps returning true, every later tick re-selects the same
  never-removed entry, re-throws and crashes again — an infinite loop.
- If `IsReady()` returns false after consumption, the entry is never drained and
  never cleared: both slots stay occupied, `Runtime->Jobs.Num() >= 2`
  (`WoodWorldStreaming.cpp:76`) blocks all dispatch forever, and the key is
  permanently absent from `Pending` for the planner
  (`WoodWorldStreaming.cpp:73`), so that chunk is **never requested again**. The
  world is permanently short one chunk either way.

There is no runtime path that removes a job key except the success path at `:63`.

**Reachable triggers, ranked honestly:**

| Trigger | Path | Reachability |
|---|---|---|
| Non-finite pawn position | `WoodWorld.cpp:130` → `plan` `WoodStreaming.cpp:16` | Possible; requires a physics/NaN event. `FloorToInt(NaN)` is undefined *before* the throw, so the guard must precede the coordinate math. |
| Chunk index ≥ 7805 | `WoodStreaming.cpp:19` accepts; `WoodGeneration.cpp:151-152` rejects | The two layers genuinely disagree on the legal range (this is the mechanism `t-0007` identified). At the 4.2 m/s walk speed this is ≈999 km ≈ **66 hours** of unbroken travel. Real, not reachable in a session. |
| Any future throw in `WoodPrepareChunk` | — | The function is `check`-guarded at `:6` (compiled out in Shipping) and indexes with no bounds assertions. |

**Two cheaper reproducers, found in the parallel H4 design
(`Docs/superpowers/specs/2026-10-07-streaming-h4-fix.md` §7.3), verified here and
incorporated because they raise H4's standing:**

- **A launch argument, with no code change.** `-WoodStartX=999040` makes
  `ExplorerStart()` return `99,904,000` cm (`WoodWorldStreaming.cpp:17`), so
  `WoodWorld.cpp:123` asks for chunk `7805` and `WoodGeneration.cpp:152` throws —
  **inside `Generate()`, before `Tick` ever runs.** H4 therefore also has a
  *synchronous* BeginPlay face that a task-body `try`/`catch` cannot fix; that half
  needs the bounds guard (step 2 / Group D).
- **The developer console.** `AWoodCharacter::WoodView` (`WoodCharacter.cpp:75`)
  calls `GroundAt` (`:106`) and `EnsureTerrainAround` (`:107`), both of which throw
  on the same bound.

Both confirm the same verdict: **H4's fix is two changes, not one** — an
exception-safe task body *and* a position guard. Doing only the first leaves the
BeginPlay and console paths fatal.

So: **high impact, low likelihood, cheap to fix.** It ranks above the performance
findings only because it is unrecoverable and it also permanently consumes the
pipeline.

### M1 — per-frame deep copy of the placement profile table · **REAL, OVERSTATED**

`WoodWorldStreaming.cpp:78` copies `Runtime->Kinds`, `Runtime->Profiles`,
`Runtime->Available` and `Generator` into the loop body, and `:79` captures them by
value into the lambda. `FWoodPlacementProfile` holds `TArray<FVector> Roots`
(`WoodGrounding.h:9`), so this is a genuine deep copy.

Corrections: it runs **once per dispatched job**, not once per frame — at most
twice per tick, and only while the queue is non-empty. The payload is a few hundred
`FVector`s: kilobytes, not milliseconds. And the copy is *required* by the design —
`.clanker/CLAUDE_REVIEW.md` `streaming-5` explicitly endorses value captures over
`this`-capturing tasks. The correct fix is to hoist the snapshots out of the loop
(or share one immutable `TSharedPtr<const>` per session), which is a tidy-up, not a
performance fix. It belongs in the same change as H2 because both touch `:78-79`.

### M2 — no cancellation path for queued work · **REAL**

Confirmed. There is no cancel flag, no stale list, and no `Plan::stale`. Out-of-range
results are discarded *after* completing (`WoodWorldStreaming.cpp:63`), which is
correct for lifetime but wastes the whole job. `plan()` also counts *all* in-flight
coords toward `availableJobs` regardless of distance
(`WoodStreaming.cpp:23`), so after a teleport both slots stay busy with far-away
work until it finishes. Severity is bounded: at most two wasted jobs of bounded
cost, no correctness impact. It matters mainly because it delays near refills,
which is the same symptom M3 causes.

### M3 — one chunk per tick, non-deterministic map order · **REAL CODE, OVERSTATED AS A BOTTLENECK**

Both halves are confirmed:

- `WoodWorldStreaming.cpp:62` `for(...) if(IsReady()) {Done.Add(...); break;}` — the
  `break` admits **at most one** ready job per tick, and `Done` therefore holds at
  most one entry.
- `Runtime->Jobs` is a `TMap` (`WoodRuntime.h:9`). Iteration order depends on
  element-ID assignment and hash layout, which vary with insertion and removal
  history. **Which** ready chunk is drained is not reproducible run to run.

**But the audit's implied claim — that this starves streaming — does not hold at
the current cost profile.** With `maxConcurrentJobs = 2` and per-chunk cost `T` ms,
throughput saturates at `2/T` chunks per second. The drain cap allows 60 chunks/s
at 60 fps. For the drain to bind, `T` would have to be under ≈33 ms, and §2's
arithmetic plus the feature-layer and discovery cost put a detailed chunk well above
that. **The 2-job concurrency is the binding constraint today; the drain cap is not.**

This produces the most useful ordering result in the triage: **fixing H2 raises
throughput and thereby exposes M3 as the next bottleneck.** Fixing M3 first, or
without a per-frame time budget, would realise multiple chunks per frame and
multiplicate the synchronous collision cook at `WoodWorldStreaming.cpp:34` — making
§12 *worse*, not better.

### M4 — dead contract and duplicated chunk size · **REAL**

Every clause verified:

- `retained()` (`WoodStreaming.cpp:9`) is called only from `plan()` at `:28` and from
  `Tests/StreamingTests.cpp:24-25`. **No adapter caller.**
- `Plan::removed` is computed at `WoodStreaming.cpp:28` and asserted at
  `Tests/StreamingTests.cpp:23`. **The adapter never reads it.**
- `Settings::maxConcurrentJobs` is passed as a bare literal `2` at
  `WoodWorldStreaming.cpp:74` and is then **ignored**: dispatch is gated by the
  hard-coded `Runtime->Jobs.Num() >= 2` at `:76`. Changing the literal at `:74`
  would silently not change dispatch.
- Chunk size appears as `12800` at `WoodWorldStreaming.cpp:21` and `:61`,
  `WoodWorld.cpp:122`, **and three more times in the test file**
  (`WoodInstanceRetentionTests.cpp:24,55,77`); as `128` three times in one
  expression (`WoodWorldStreaming.cpp:39-40`); and as a bare literal in two
  independent settings constructions (`WoodWorld.cpp:37`,
  `WoodWorldStreaming.cpp:74`) that must agree with the header defaults
  (`WoodGeneration.h:9`, `WoodStreaming.h:12`). **The audits' "three literals"
  understates it once the test file is counted.**

**One item the audits missed, and it is the substantive one:** `Stream` uses three
different radii with no named relationship — `ChunkRadius+1` for the realise window
(`:63`), `ChunkRadius+2` for unload (`:64`), and `ChunkRadius`/`ChunkRadius+2` handed
to `plan()` as `desiredRadius`/`retainRadius` (`:74`). They currently agree, by
construction and by coincidence. `retained()` is the function that *should* express
the retain test and is the one nobody calls. This is a drift hazard, not a current
bug — and it is exactly what §7's retention requirement will be written against.

### M5 — `Plan.removed` cannot cover terrain-only chunks · **REAL BUT LATENT**

Verified: the `loaded` vector passed to `plan()` is built from
`Entry.Value.Detailed` only (`WoodWorldStreaming.cpp:72`), and `plan()`'s removal
loop iterates that set alone (`WoodStreaming.cpp:28`). A resident chunk realised
terrain-only (`Detailed == false`) is invisible to `Plan::removed`.

**There is no live bug**, because the adapter never uses `Plan::removed` — it
unloads through its own loop at `:64`, which covers *all* residents. M5 becomes a
bug the instant someone satisfies M4 by wiring `Plan.removed` in. See §5(b): this
is the single most dangerous item in the list.

### L1 — instance identity is an array slot · **WRONG AS STATED**

`FWoodRuntime::Instances` is `TArray<TArray<FPrimitiveInstanceId>>`
(`WoodRuntime.h:6`), indexed by the global vegetation slot, and unload passes those
ids at `WoodWorldStreaming.cpp:66-68`. That part is accurate.

**But identity is not the slot.** `:55` calls `AddInstancesById(Placements[I], true,
false)` — the `true` is `bShouldReturnIndices`, so the returned
`FPrimitiveInstanceId`s *are* stable per-instance handles, and unload uses
`RemoveInstancesById` with them. The audit's own wording ("array slot, not a stable
feature identity") conflates the **storage index** (a slot into a global component
list) with the **removal key** (a stable id). Those are different things, and only
the first is positional. `.clanker/CLAUDE_REVIEW.md` `streaming-3` reached the same
conclusion from the opposite direction and reached "no new code is needed".

What is genuinely fragile, and much smaller:

1. `:54` indexes `Placements[I]` for `I < Vegetation.Num()`, but
   `Placements` is sized by `Kinds.Num()` inside the worker
   (`WoodPreparedChunk.cpp:23`). Equality holds only because `Generate` appends to
   `Vegetation`, `Kinds`, `Profiles` and `Available` in lockstep
   (`WoodWorld.cpp:115-119`) **before** any job is dispatched. **Nothing asserts
   it.** Any future palette reload or resize turns this into an out-of-bounds read.
2. `:55` passes `bWorldSpace = false`, i.e. the grounded world-space transforms are
   interpreted as component-local. That is correct today only because the
   vegetation components are attached to an untransformed root
   (`WoodWorld.cpp:85`) and the actor is never moved. Moving `AWoodWorld` shifts
   every plant.

**Unresolved, and not decided here:** `.clanker/REVIEW.md:53` claims UE 5.8's HISM
`ApplyBuildTree` calls `ClearIdTracking`, which would invalidate the stored
`FPrimitiveInstanceId`s — a *different* mechanism producing the same class of
damage. I could not read the engine source to confirm it. Against it:
`WoodInstanceRetentionTests.cpp:74-79` exercises exactly that property across two
successive unloads and is reported passing (`Docs/Status.md:27`). **Treat REVIEW.md
as unresolved, not as confirmed, and do not let either audit's version stand as
authority.** Verification requires the engine source or a packaged run.

### L3 — `LoadedChunkCount` over-reports · **WEAK / UNPROVEN**

`WoodWorldStreaming.cpp:19` returns `Runtime->Chunks.Num()`. **It has no caller.**
`grep` over `Source/`, `Tests/` and `Tools/` finds only the definition
(`WoodWorld.h:25`) — no test, no script, no adapter use.

"Over-reports" is only meaningful against a written contract, and there is none.
The count does include terrain-only residents (`Detailed == false`) alongside fully
realised ones, so it conflates "resident" with "realised". That is a real ambiguity
for a future retention test — and it matters, because
`.clanker/CLAUDE_REVIEW.md` `streaming-6` proposed exactly such a test ("assert
loaded count ≤ (2*retain+1)²"). **If L3 is right, that proposed test is vacuous,
and it was never implemented anyway.** The honest verdict: this is dead public API
with an undefined contract, not a misreporting bug. Severity: lowest in the list.

### L4 — invariants enforced by exceptions out of `Tick` · **REAL, SYSTEMIC**

Confirmed, with a narrowed trigger set. `Tick` (`WoodWorld.cpp:126-131`) calls
`Stream()`, which can throw at four points, and `Tick` then calls `sample()` at
`:133` and `atmosphere()` at `:134`, both of which throw on bad input. No catch
exists anywhere on the path.

Throw sites reachable from `Tick`:

| Site | Condition | Reachable? |
|---|---|---|
| `WoodStreaming.cpp:16` | non-finite position, or `desiredRadius > 32` / `retainRadius > 64` / `retainRadius < desiredRadius` / `maxConcurrentJobs == 0` | Position: yes, on NaN. Settings: `ChunkRadius` is clamped 1–4 by `UPROPERTY` metadata (`WoodWorld.h:29`) — **editor UI only**; a value set from code or from corrupted serialisation reaches `plan()` unchecked. |
| `WoodStreaming.cpp:19` | chunk index beyond `INT_MAX - retainRadius` | No — far past the generator's own bound. |
| `WoodGeneration.cpp:26` (`validatePoint`) | `\|x\| > 1,000,000` m | ≈1000 km from the origin; ≈66 h of travel at 4.2 m/s. |
| `WoodGeneration.cpp:152` | chunk index ≥ 7805 | Same bound, one layer down. |
| `WoodAtmosphere.cpp:13` | `forestWeight` outside `[0,1]` | **Refuted.** `climate()` sets `forest = Σ(w·canopy)/Σw` with `canopy ≤ 0.96` (`WoodGeneration.cpp:43`), so `forest ≤ 0.96` up to float rounding. `.clanker/CLAUDE_REVIEW.md`'s "biome weights can round to 1.0000001" concerns `s.biome[]`, which `atmosphere()` never receives. |

The severity is not in any single trigger; it is that the invariant mechanism is an
exception escaping a frame function. That is what makes H4 unrecoverable, and it is
the reason H4 and L4 must be fixed as one design rather than two.

## 4. Severity ordering

Two gates, quoted:

- **§12** (line 184): "Acceptance uses packaged builds and measured frame times,
  including movement, generation, photography, and accelerated observation. **Average
  frame rate alone is insufficient when frequent generation or capture stalls
  interrupt exploration.**"
- **§7** (line 105): "Visible landmarks must remain consistent and reachable where
  the terrain permits; **the system must not show a mountain and replace it before
  the player arrives.**" §7 (line 107): "Distant regions can be removed only after
  they are beyond both relevant visibility and a local backtracking buffer… **immediate
  surroundings must remain stable.**"

§12 discriminates between findings that cost frame time and findings that cost
correctness — it demands measured *worst-case* behaviour during generation, not
average. §7 disqualifies anything that removes or replaces terrain the player can
see. Note also that **no packaged measurement is possible on this machine**, so
every §12 finding below is real by inspection and unproven by measurement. None of
them may be reported as "verified within the performance target".

### P0 — violates §7 directly; correctness, not performance

1. **H1.** A single null-pawn frame destroys the entire loaded world for any player
   more than 768 m from the world origin, and every null-pawn frame additionally
   triggers H2 and a 2-job/tick burst toward the origin. It violates "immediate
   surroundings must remain stable" in the most direct way available in this
   codebase, and it is live in the test suite today (`WoodRuntimeTests.cpp:26`).
   Fix is one branch.
2. **H4 + L4 together.** Unrecoverable: no state on earth returns the pipeline. L4
   is the mechanism, H4 the outcome, and fixing either alone leaves the other.
   Ranked here rather than in P1 because there is no mitigation and no self-heal.

### P1 — attacks the §12 gate directly

3. **H2.** The only finding that puts 10²-millisecond work on the game thread inside
   the movement loop. §12 names this case verbatim. It also fires 9× at level start
   (`WoodWorld.cpp:123`), and its synchronous collision cook
   (`WoodWorldStreaming.cpp:34`) is a second stall in the same call.
4. **H3.** Same wasted arithmetic as H2, but off-thread: it costs worker-slot
   occupancy and post-teleport refill time, not frame time. Second-order under §12;
   first-order under nothing, which is why it must be fixed *with* H2 rather than
   before it.

### P2 — streaming continuity; ordered by when they become binding

5. **M3.** Real and arbitrary-order, but the 2-job concurrency binds first.
   Becomes the bottleneck the moment H2 lands. Must not be fixed without a
   per-frame time budget.
6. **M2.** Same symptom as M3 from the other side; no correctness impact; bounded
   waste. Naturally paired with M3.
7. **M1.** Real, small, and required by the current task-capture design. Hygiene.

### P3 — contract and documentation defects; no current misbehaviour

8. **M4.** Dead API surface plus a drift hazard in the literal chunk size and in
   three unnamed radii. No present symptom; a direct hazard for the retention work
   §7 still requires.
9. **M5.** Latent, and a trap for whoever fixes M4.
10. **L3.** Dead accessor with an undefined contract.
11. **L1.** Wrong as stated; the two real preconditions (unasserted array coupling,
    component-local transform assumption) are small and cheap to *test*.

## 5. Contradictions between workers

**(a) M3 vs the 2026-10-06 review — a cap that was deliberate.**
`.clanker/CLAUDE_REVIEW.md` `streaming-4` says "**Keep the one-job-per-frame cap or
a time budget.**" `streaming-1` in the same review already noted "The live code also
drains only one ready job per frame" as an aside, not as a defect. The M3 audit
treats the same line as unintended. Both readings are defensible: the cap was an
intentional bound on per-frame realisation cost, and its *replacement* must be a
time budget, not an unbounded drain. **Resolve as: replace the count cap with a
millisecond budget — do not simply delete it.**

**(b) M4 vs M5 — satisfying one creates the other.** This is the most dangerous
interaction in the set. M4 says `Plan::removed` has no runtime caller and reads as
"wire it up". M5 proves that wiring it up makes every terrain-only resident
unremovable, because `loaded` at `WoodWorldStreaming.cpp:72` filters on `Detailed`.
`.agents/ue-project-context.md` records **M4 without M5**, i.e. exactly the half that
is dangerous on its own. They are one unit; M4 must not be actioned alone.

**(c) H2's trigger vs `t-0006`'s brief.** `t-0006` is scoped to "every chunk-boundary
crossing and once at BeginPlay". §3/H2 shows the boundary-crossing case does **not**
normally fire, and the BeginPlay case is **9× with features**, not once. A fix
designed against those words will optimise the wrong path. Recommend `t-0006`
re-read §3/H2 before writing its design.

**(d) H1 vs H2 as independent items.** They are causal: every null-pawn frame runs
the H2 fallback on chunk `(0,0)`. `.agents/ue-project-context.md` lists them
separately; fixing H1 removes a large share of H2's worst cases for the cost of one
branch. This is why H1 is ordered first despite not appearing in the perf gate.

**(e) L1 vs `.clanker/REVIEW.md:53`.** REVIEW.md says the *stored instance IDs* are
invalidated by an engine-side rebuild; L1 says the identity is the *array slot*.
They describe different mechanisms for the same symptom and cannot both be the
defect. I could not read engine source to settle it. Until someone can, **the
authoritative statement is L1 as corrected**: removal is by stable id, so the
storage slot is not the removal key; REVIEW.md's engine claim remains unresolved.

**(f) L3 vs `CLAUDE_REVIEW` `streaming-6`.** `streaming-6` proposed a retention
bound asserted through `LoadedChunkCount`. L3 shows the counter is undefined and
uncalled. So that coverage **was never delivered**, and the §7 retention bound has
no test. Nobody should assume otherwise from `Docs/Status.md:27`.

## 6. Which fixes are safe together

Grouping is by shared lines and by whether one change can invalidate another's
reasoning — not by severity.

**Group A — independent, zero-risk, land first.** H1's guard (`WoodWorld.cpp:130`,
`WoodWorldStreaming.cpp:59-61`); a finite/range position check ahead of the
coordinate math. None changes scheduling semantics; each is independently
verifiable. (L3 is hygiene rather than a guard, so it is listed in step 7 rather
than here.)

**Group B — one design, one change: H2 + H3 + M1 + the water-ribbon samples +
collision cooking.** All five live in the same two functions
(`WoodPrepareChunk` and `Realize`/`Stream`) and describe one coherent defect: value
production is per-vertex-expensive, partly duplicated, partly on the wrong thread.
Splitting them guarantees a partially-fixed state where attributes are still
recomputed. Fix the duplication by *caching the attribute pass per chunk* so the
detailed realise reuses it, hoist the job snapshots out of the dispatch loop, skip
the water ribbon's redundant `sample()` calls, and enable async cooking for
neighbour chunks. **Do not add M3's drain change here.**

**Group C — M3, strictly after Group B.** Replacing the `break` at
`WoodWorldStreaming.cpp:62` with a millisecond budget is only safe once realisation
cost is bounded. Landing M3 first means several `CreateMeshSection_LinearColor` +
collision cooks per frame — a §12 regression. M2 belongs here too, because a
cancel flag is most useful exactly where the pipeline is fastest.

**Group D — H4 + L4, with M2's job-lifecycle half.** H4's stop-gap (catch inside
the task body, always remove the key, post an error result) and L4's boundary guard
share the drain loop at `:62-63`. **H4 needs both halves and the task-body half
alone is not sufficient** — the synchronous `Generate()` throw and the
`WoodCharacter::WoodView` console path are not reachable from a task body and
require the bounds guard. **L4 must not be implemented as a blanket
`try`/`catch` around `Stream()`** — that converts a hard crash into silent
corruption and hides exactly the generator errors the spec wants surfaced. It should
be an explicit `noexcept` validity predicate plus a `noexcept` task body.

**Group E — M4 + M5, one unit, in the pure core, last.** Both change `plan()`'s
contract and therefore `Tests/StreamingTests.cpp`, which currently asserts
`removed.size() == 1` from a Detailed-shaped input (`:23`). Touching the pure
planner in the same change as the adapter loop makes regressions hard to attribute.

**Do not bundle Group E with Group B/C:** changing `plan()`'s semantics while
rewriting the adapter that calls it removes the ability to tell which change caused
a failure.

## 7. Dependency order

Each step depends only on those above it.

| # | Step | Depends on | Why here |
|---|---|---|---|
| 0 | H1 guard + explicit position validity check | — | Cheapest, highest severity, removes an H2 trigger and a job-burst trigger in one branch. |
| 1 | H4 stop-gap: catch in the task body, always remove the key | 0 | Must land before anything increases the chance of a throw. Stops the unrecoverable async wedge. Does **not** cover the synchronous `Generate()` throw. |
| 2 | L4 done properly: `noexcept` predicate at the `Tick` **and** `BeginPlay` boundaries, `noexcept` job body, bounded logging | 1 | After 1, so the drain is already exception-safe and the new guard has somewhere safe to return. This is the half that covers the launch-argument and console paths. |
| 3 | Group B design, then implementation: H2 + H3 + M1 + water-ribbon + async cooking | 0, 2 | Largest single change; benefits from a position guard and a non-throwing job body already in place. |
| 4 | M3: replace the one-per-tick `break` with a per-frame millisecond budget | 3 | **Hard dependency.** Bounded realisation cost must exist first. |
| 5 | M2: cancellation / stale-job handling | 3, 4 | Most valuable once the pipeline is fast enough for a stale job to be worth cancelling. |
| 6 | Group E: M4 + M5 in `WoodStreaming.cpp`, with `Tests/StreamingTests.cpp` updated together | 3, 4 | Pure-core contract change, last, with a clean adapter baseline. |
| 7 | L3 contract naming; L1's two preconditions turned into tests | any | Independent hygiene; no code risk. |

Parallel-safe: step 7 may run at any time. Steps 0 and 7 may run concurrently with
everything. **Do not start 4 before 3, and do not start 6 before 4.**

## 8. Notes for whoever implements

- **Chunk size.** Do not "fix M4" by editing the three `12800`s alone. Introduce one
  named centimetre constant derived from `wood::Settings::chunkSize`, and use it at
  `WoodWorldStreaming.cpp:21,39,40,61` and `WoodWorld.cpp:122`. Then update
  `WoodInstanceRetentionTests.cpp:24,55,77` in the same change or the test file
  becomes a fourth copy. Also reconcile the bare `128` in the `plan()` settings
  literal at `:74` with `WoodWorld.cpp:37`'s `wood::World({Seed,128,64})`.
- **Radii.** Three unnamed radii (`+1` realise, `+2` unload, `desiredRadius`/
  `retainRadius`) currently agree. Expressing them through the already-written
  `retained()` is the intent of M4; do it in Group E, not in Group C.
- **H1's guard placement.** The check must precede
  `FMath::FloorToInt(Position.X/12800)`, because `FloorToInt` of a non-finite
  double is undefined before any guard can see it. A guard placed inside `Stream()`
  after line 61 is too late.
- **H4's fix placement.** Catch inside the lambda at
  `WoodWorldStreaming.cpp:79` and return a result-or-error value; do **not** catch
  around `Get()` at `:63` and continue, which would leave the wedged key in place.
- **Tests that would have caught these.** A null-pawn tick more than 768 m from the
  origin (H1); a chunk whose attributes are prepared once and realised twice (H3);
  a job body that throws (H4); `LoadedChunkCount` asserted against the retain
  bound (L3, and the `streaming-6` gap). The existing suite performs the H1 defect
  at `WoodRuntimeTests.cpp:26` and asserts nothing about it.

## 9. Unresolved

1. **`L2` was not supplied.** The list jumps `L1 → L3`. This triage cannot claim
   coverage of it.
2. **`TFuture::IsReady()` after a consumed future** (UE 5.8) — engine source
   unavailable. H4's verdict holds either way; the *symptom* differs (crash loop
   vs silent permanent stall + one missing chunk).
3. **`REVIEW.md:53`'s `ClearIdTracking` claim** — unverifiable here; contradicted in
   practice by the passing retention test at `WoodInstanceRetentionTests.cpp:74-79`.
4. **Every performance magnitude in this document is arithmetic, not measurement.**
   §12 requires packaged frame times on a recorded PC; that is not obtainable on
   this machine. Nothing here may be reported as meeting or failing the 60 fps
   target.