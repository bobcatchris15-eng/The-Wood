# Streaming exception safety and the coordinate contract (H4)

Status: **design only.** No source file was modified. No compile, no editor launch,
no automation run was performed — see `Docs/clanker/WorkerBrief.md:30-33` (Unreal
reinstalling, Visual Studio Build Tools absent, no MSVC/clang/gcc). Every claim
below is derived by reading source. Where a claim depends on Unreal runtime
behaviour that cannot be checked without the engine, it is marked **[unverified]**
and the fix is designed to be correct under either outcome.

Related prior findings, with different ids: `.clanker/CLAUDE_REVIEW.md:33-37`
(`gen-core-3`, "Generator throws at 1000 km with no catch anywhere") and
`.clanker/CLAUDE_REVIEW.md:56-60` (`streaming-1`, stale pending jobs, no cancel
output). This document supersedes neither; it turns both into a concrete change.

---

## 1. The defect, exactly as written

`Source/TheWood/Private/WoodWorldStreaming.cpp:59-93` is `AWoodWorld::Stream`. Its
first three phases, in order:

| Line | Phase | Can it throw? |
| --- | --- | --- |
| `:60` | `EnsureTerrainAround(Position)` — synchronous full chunk generation for the centre chunk | **Yes**, `WoodGeneration.cpp:152` |
| `:62-63` | drain one ready background job, `Get()`, `Remove()` | **Yes**, via `Get()` |
| `:74` | `wood::streaming::plan(...)` | **Yes**, `WoodStreaming.cpp:16` and `:19` |

There is no `try` anywhere in the file. `AWoodWorld::Tick` calls `Stream` unguarded
at `WoodWorld.cpp:131`.

The specific defect is at `WoodWorldStreaming.cpp:63`:

```cpp
for(auto Key:Done) {auto Chunk=Runtime->Jobs[Key].Get();Runtime->Jobs.Remove(Key); ...}
```

`Runtime->Jobs` (`WoodRuntime.h:9`) is the **sole owner** of every
`TFuture<FWoodPreparedChunk>`. `Get()` is called while the map still owns the future,
and the map entry is only released on the normal-return path. If the task terminated
by throwing, `Get()` rethrows, control leaves `Stream` at that point, and
`Runtime->Jobs.Remove(Key)` at column 74 of the same line never executes.

Two misconceptions make the existing code look safe:

1. **`IsReady()` at `:62` is a completion test, not a success test.** A task that
   ended by throwing is *ready*. That is precisely what makes `:62` select the
   poisoned entry on every subsequent pass.
2. **`Remove` is treated as cleanup.** It is not; on the throwing path it is the
   only thing standing between a one-chunk content failure and a permanently
   degraded stream.

### 1.1 What is guaranteed, and what is conditional

This matters because the audit describes a "permanent crash loop", and the first
crash makes that phrasing contestable.

- **Guaranteed.** On the first throw, `Stream` never returns, `Remove` never runs,
  and the key stays in `Runtime->Jobs`. Whatever the host does next, the invariant
  "the map entry is released before any throwing operation on that entry" is
  violated. That is the defect, and it is a defect in the source regardless of host
  behaviour.
- **Conditional [unverified].** Whether later ticks actually *re-select* the entry
  depends on how the engine's `Async` future handles a task that threw. If an
  exception escaping `Tick` terminates the process, the loop is never entered and
  the observable symptom is one fatal crash. If the host swallows it and continues
  the frame, `:62` re-selects the same never-removed ready entry every tick and
  throws forever, with `Runtime->Jobs.Num() >= 2` holding permanently once both
  slots are poisoned — halving streaming throughput for the rest of the session.

The fix must not depend on resolving this. Remove-before-`Get` is correct under
either host behaviour, which is exactly why it is the right shape.

**One item to confirm when the engine returns:** read the installed
`Async/Future.h` / `Async.h` and confirm whether `TFuture::Get()` rethrows a task
failure and whether destroying an unconsumed `TFuture` blocks. The fix below relies
on the first and depends on the second being false. Record the answer here.

---

## 2. Ownership discipline: why `Remove` must precede or accompany `Get`

The invariant, stated once:

> No operation that can throw may execute between the moment `Runtime->Jobs` stops
> being the sole owner of a future and the moment that key is absent from the map.

`Get()` is the throwing operation. Therefore `Get()` must come **after** the entry is
released, never before.

### 2.1 The fix

Illustrative sketch for `WoodWorldStreaming.cpp:62-63`. Not applied.

```cpp
TArray<FIntPoint> Done;
for (auto& Job : Runtime->Jobs) if (Job.Value.IsReady()) { Done.Add(Job.Key); break; }
for (FIntPoint Key : Done) {
  TFuture<FWoodPreparedChunk> Job = MoveTemp(Runtime->Jobs[Key]); // 1. map stops owning
  Runtime->Jobs.Remove(Key);                                     // 2. entry is gone
  FWoodPreparedChunk Chunk;
  try { Chunk = Job.Get(); }                                     // 3. may rethrow; nothing left behind
  catch (const std::exception& E) { UE_LOG(LogTemp, Error, TEXT("Chunk (%d,%d) failed: %s"), Key.X, Key.Y, UTF8_TO_TCHAR(E.what())); Runtime->Refused.Add(Key); continue; }
  catch (...) { UE_LOG(LogTemp, Error, TEXT("Chunk (%d,%d) failed: unknown exception"), Key.X, Key.Y); Runtime->Refused.Add(Key); continue; }
  if (FMath::Abs(Key.X - Center.X) <= ChunkRadius + 1 && FMath::Abs(Key.Y - Center.Y) <= ChunkRadius + 1) Realize(Chunk);
}
```

`MoveTemp` is required, not stylistic: `TFuture` is move-only, so the future cannot
be copied out and a reference is the only other option — and a reference is exactly
what makes "remove first" impossible.

`MoveTemp` at step 1 and `Remove` at step 2 are both non-throwing, so their relative
order does not matter. What matters is that both precede step 3.

### 2.2 Rejected alternatives

- **`Remove(Key)` first, then `Get()` on a reference taken beforehand.** Use after
  free. `TMap::Remove` invalidates references and pointers to the removed element.
- **`Remove` inside the `catch`.** It works, but it leaves the map as owner while an
  exception is unwinding and puts the only correct cleanup inside a handler, where a
  second throw (for example in `UE_LOG` formatting) loses it again.
- **`IsReady()` then `Get()` unquestioned.** That is the current bug.
- **Adding `Wait()` anywhere.** A blocking wait inside `Tick` converts an exception
  bug into a frame-time bug. Do not.

### 2.3 The same discipline applies to the other two maps

This is not a one-line fix at `:63`. `Runtime->Jobs` is mutated in three places
(drain `:63`, dispatch `:79`, and — once M2 adds it — cancel), and `Runtime->Chunks`
in two (`:27`, `:69`). The `:65-70` unload loop already has the fragile shape:
`auto& C = Runtime->Chunks[Key]` at `:66`, work that can allocate (TArray growth in
`C.Instances`) at `:67`, then `Runtime->Chunks.Remove(Key)` at `:69`.

Rule: **any loop that holds a reference into a `TMap` and later mutates the map must
either do all throwing work first, or move the element into a local before touching
the map.** `:65-70` should take `FWoodResident Resident = MoveTemp(Runtime->Chunks[Key]);`
and then `Remove(Key)` before destroying components.

---

## 3. Where error isolation belongs

Three candidate placements. The recommendation is layered, because each layer
covers a different class of failure.

### 3.1 Layer 1 — the task body is total (the real isolation point)

The generator throws by design; that is a legitimate contract and the standalone
suites rely on it (`Tests/GenerationTests.cpp:52`, `Tests/StreamingTests.cpp:35,38,41`).
The defect is not that `World::generate` throws. The defect is that an exception
crosses a thread-pool boundary into code with no contract for one.

So contain it at the boundary where the chunk's fate is still knowable:

```cpp
struct FWoodJobResult {
  bool bOk = false;
  FWoodPreparedChunk Chunk;
  std::string Error;   // plain std::string; no FString work on a worker thread
};
```

and the lambda at `WoodWorldStreaming.cpp:79` returns `FWoodJobResult`, catching
`...` around the `WoodPrepareChunk` call. `FWoodRuntime::Jobs`
(`WoodRuntime.h:9`) becomes `TMap<FIntPoint, TFuture<FWoodJobResult>>`.

This makes `Get()` non-throwing **by construction**, for every present and future
consumer, including code that has no `try` block. It is the only placement that can
honestly claim *"a single bad chunk cannot kill Tick"*, because the exception never
leaves the worker.

Layer 1 does not subsume §2: `Get()` is documented to rethrow, and `bad_alloc` or a
future refactor can still deliver one. Both layers are cheap; land §2 first as a
self-contained three-line change that needs no type change, then Layer 1.

### 3.2 Layer 2 — the drain site

The `try`/`catch` in §2.1. Its job is to attribute a failure to a coordinate, log
it once, and keep the rest of the frame alive.

### 3.3 Layer 3 — deliberately *not* a blanket `catch` in `Tick`

A `try` around `AWoodWorld::Tick` would be wrong for three reasons:

1. **It protects the wrong frame.** `AWoodCharacter::Tick` calls
   `Environment->EnsureTerrainAround(P)` at `WoodCharacter.cpp:44` and
   `Environment->DepthAt(...)` at `:45`. Both reach `validatePoint`
   (`WoodGeneration.cpp:26`) through `AWoodWorld::EnsureTerrainAround`
   (`WoodWorldStreaming.cpp:22`) and `AWoodWorld::DepthAt` (`WoodWorld.cpp:160`).
   A catch in the world's `Tick` covers none of that.
2. **It hides unrelated faults.** `AWoodWorld::Tick` throws from
   `Generator.sample` at `WoodWorld.cpp:133`, from `wood::atmosphere` at `:134`
   (`WoodAtmosphere.cpp:13`, which rejects a `forest` weight outside `[0,1]` — an
   open item from `.clanker/CLAUDE_REVIEW.md:344`, not a coordinate problem at all),
   and from `EnsureTerrainAround` at `WoodWorldStreaming.cpp:60`. One blanket catch
   would collapse three unrelated diagnoses into one log line.
3. **It is a symptom treatment.** `WoodWorld.cpp:133` and `:134` are per-frame
   hot-path calls. Catching an exception in a per-frame hot path, potentially 60
   times a second, is worse than the throw.

The correct treatment for the position-side sites is to **bound the input**, not to
catch the output. See §5.4.

### 3.4 A synchronous throw site that outranks all of the above

`AWoodWorld::EnsureTerrainAround` (`WoodWorldStreaming.cpp:20-23`) calls
`WoodPrepareChunk` **synchronously on the game thread**, guarded only by
`!Runtime->Chunks.Contains(Key)`. It is called from `Stream` at `:60` *and* from
`AWoodCharacter::Tick` at `WoodCharacter.cpp:44`.

For a player beyond the support boundary, this is the **first** thing that throws —
before any future is examined, and on both tick paths. Fixing only the `:63` drain
would therefore leave the most reachable fatal path untouched.

It must go through the same total entry point as the async body. That argues for a
single `WoodPrepareChunkSafe(...) -> FWoodJobResult` wrapper used by all three call
sites: `EnsureTerrainAround` (`:22`), the async lambda (`:79`), and the `BeginPlay`
warm-up loop (`WoodWorld.cpp:123`).

---

## 4. The retry storm, which is why §5 is not cosmetic

Removing the key fixes the leak but creates a new permanent failure:

- `plan()` builds `needed` from coordinates that are neither loaded nor pending
  (`WoodStreaming.cpp:24-27`).
- A failed chunk is not in `Runtime->Chunks` and, once removed, not in
  `Runtime->Jobs`.
- On the next tick it satisfies neither exclusion, so it re-enters `needed`.
- `needed` is sorted nearest-first (`WoodStreaming.cpp:33-35`), so the doomed
  coordinate is dispatched **first**, every tick, consuming one of the two slots
  permanently (the `Runtime->Jobs.Num() >= 2` guard at `:76` counts it).

So remove-before-`Get` alone converts a fatal crash into a slow permanent
degradation: one of two job slots burned on work guaranteed to throw, and it will
be re-attempted indefinitely.

**Therefore §2 and §5 are one change, not two.** The catch handler in §2.1 must
record the coordinate in a refusal set, and that set must be fed back into `plan()`
so it is not re-requested. `Runtime->Refused` in `FWoodRuntime` is the natural home,
and it is game-thread-only state (no locking needed), which also keeps the
worker-capture rule intact.

---

## 5. One coordinate contract

### 5.1 The root cause is five constants, not two layers

H4 is usually described as "the streaming layer and the generator disagree". The
disagreement is worse than two parties; there are five independent coordinate guards
with five different values in the engine-free core plus its adapter:

| Constant | Location | Value | Enforced during chunk streaming? |
| --- | --- | --- | --- |
| Point sample limit | `WoodGeneration.cpp:25` (`validatePoint`) | 1,000,000 m | Yes — reached via `WoodPreparedChunk.cpp:15` |
| Hex coordinate limit | `WoodHex.h:15` (`hex::owner`) | 2,000,000 m | Yes — reached via `cellWeights` → `hex::warp` → `hex::weights` |
| Region lattice limit | `WoodGeneration.cpp:128` (`World::region`) | \|lattice\| ≤ 835 | **No** — `generate` calls `describe` directly (`:178`), bypassing `region()` |
| Chunk origin limit | `WoodGeneration.cpp:151` (`World::generate`) | 999,000 m | **Yes — this is the one that throws** |
| Streaming window limit | `WoodStreaming.cpp:18-19` (`plan`) | `INT_MAX − retainRadius` | Yes — the only guard the scheduler has |

The streaming guard is not merely a different number. It is **275,000× looser**: for
`chunkSize = 128` it admits chunk indices up to ~2.1 × 10⁹ where the generator
accepts at most 7804. The scheduler's guard exists to prevent undefined behaviour in
`static_cast<int>(cx)` at `WoodStreaming.cpp:21`; it is a *type-safety* guard being
mistaken for a *domain* guard. Both are needed, and they have different jobs.

### 5.2 Also duplicated: the chunk size itself

The literal `128` (and its cm form `12800`) appears in at least nine places:
`WoodGeneration.h:9`, `WoodStreaming.h:12`, `WoodWorld.cpp:38`, `WoodWorld.cpp:122`,
`WoodWorldStreaming.cpp:21`, `:39`, `:40`, `:74`. `WoodWorldStreaming.cpp:74` passes a
literal `128` to `plan()` while the generator's `chunkSize` comes from
`WoodWorld.cpp:38`. Change one and the layers desync — **the same anti-pattern that
produced H4**, one level down. This belongs in the same change.

### 5.3 Proposed contract

**One exported constant and one predicate, defined next to the guard that enforces
them, in `Source/TheWood/Public/Generation/WoodGeneration.h`:**

```cpp
// Metres from the origin. World::generate refuses a chunk whose origin corner is
// further from the origin than this. A deliberate milestone bound, not a numeric
// range limit.
constexpr double SupportedExtentMetres = 999000.0;

// The one predicate both layers must call. Deliberately the same expression as the
// guard in World::generate -- do NOT re-derive it as a floor division, which can
// disagree by one chunk at the boundary and would recreate H4.
inline bool supportsChunk(const Settings& s, int chunkX, int chunkY) {
  const double size = s.chunkSize;
  return std::abs(static_cast<double>(chunkX) * size) <= SupportedExtentMetres
      && std::abs(static_cast<double>(chunkY) * size) <= SupportedExtentMetres;
}
```

A floor-based `maxSupportedChunkIndex()` is equivalent for positive indices, but
floating-point rounding of `SupportedExtentMetres / chunkSize` can land one chunk
high. Use the multiplication form — the exact expression the generator tests — and
use a floor only for log text.

**Make `WoodGeneration.cpp:151` call it**, so the guard and the predicate cannot
diverge:

```cpp
if (!supportsChunk(config, x, y)) throw std::invalid_argument("Chunk outside supported milestone coordinates");
```

**Propagate to the scheduler.** `wood::streaming` must stay engine-free
(`WoodStreaming.h:23` promises no world generation or asset access — a promise about
runtime behaviour, not about includes, so including the constants header is
compatible). Two options:

- **(a) Recommended.** `WoodStreaming.h` includes `WoodGeneration.h` and `plan()`
  filters. Strongest single source of truth: it is impossible for the two layers to
  disagree because there is only one number.
- **(b)** `Settings` carries `double maxExtentMetres` and the adapter supplies it
  from the generator at `WoodWorldStreaming.cpp:74`. Keeps the include graph flat,
  but reintroduces a value that can be set wrongly.

**Report, do not silently drop.** Add `std::vector<Coord> refused;` to `Plan`
(`WoodStreaming.h:17-21`). Coordinates failing `supportsChunk` go to `refused`
instead of `needed`. Silently dropping them means a player at the boundary sees
chunks vanish with no explanation and `LoadedChunkCount()`
(`WoodWorldStreaming.cpp:19`) looks wrong with no diagnostic — which this repository
treats as a defect in its own right (`Docs/clanker/WorkerBrief.md:21-23`).

**Adapter must use the planner's own budget.** Replace the hard-coded
`Runtime->Jobs.Num() >= 2` at `:76` with `Plan.availableJobs`
(`WoodStreaming.cpp:23`), which the caller currently ignores. This is already
`.clanker/CLAUDE_REVIEW.md:74-78` (`streaming-2`); landing it here costs nothing extra
and makes the refusal path observable.

**Signature interaction — do not land twice.** `save-resume-design.md:441` proposes
`plan(playerX, playerY, loaded, pending, visible, settings)`. This document needs a
`blocked` parameter for the refusal set. Landing them as two separate signature
changes means two rounds of churn in `WoodStreaming.h` and `Tests/StreamingTests.cpp`.
Merge them into one change, with the existing four-argument form kept as a defaulted
delegate so current assertions keep compiling.

### 5.4 The position-side guards are a separate, also-required change

§5.3 stops the *scheduler* from requesting impossible chunks. It does not make `Tick`
survivable, because two per-frame call sites throw on position alone:

- `WoodWorld.cpp:133` — `Generator.sample(Position.X/100, Position.Y/100)` → `validatePoint` (`WoodGeneration.cpp:25`) throws beyond 1,000,000 m.
- `WoodCharacter.cpp:45` — `Environment->DepthAt(...)` → the same path via `WoodWorld.cpp:160`.

These have a **looser** bound (1,000,000 m) than chunk generation (999,040 m), so
there is a real window where only the chunk path fails — see §7.2. Beyond 1,000 km
the frame dies regardless of anything done in §2 or §5.3.

Recommended treatment: derive `validatePoint`'s bound from
`SupportedExtentMetres` instead of repeating `1e6`, and clamp the position in the
adapter before it reaches any generator call, logging the clamp once. Clamping is a
better fit than catching because it removes the failure entirely and is cheap in a
per-frame path. Note that `World::lighting` (`WoodGeneration.cpp:278-289`) performs
**no** coordinate validation — only a `seconds` finiteness check at `:279` — so
`WoodWorld.cpp:135` and `:153` will silently produce garbage rather than throw at
absurd coordinates. An asymmetry, not an accident, but worth knowing.

---

## 6. M2 — there is no cancellation path for queued work

`2026-10-06-biomes-and-streaming.md:19` promises "cancellation-safe task lifetime".
Today the *lifetime* is safe and the *cancellation* is absent. Distinguish them.

### 6.1 What is already correct

The lambda at `WoodWorldStreaming.cpp:79` captures `Snapshot` (a `wood::World` **by
value**), `Key`, `Kinds`, `Profiles`, `Available` **by value**. It touches no
`UObject` and does not capture `this`. An in-flight task therefore cannot dereference
a destroyed actor, which was the actual concern in
`.clanker/CLAUDE_REVIEW.md:86-90` (`streaming-5`). `FWoodRuntime` is a
`TSharedPtr` member (`WoodWorld.h:51`) and `~AWoodWorld() = default`
(`WoodWorld.cpp:28`), so teardown drops the futures cleanly.

**Do not regress this.** Keep value captures. Adding a cancel flag must be a
`TSharedPtr<TAtomic<bool>>` captured by value — not a raw pointer into `FWoodRuntime`,
which would reintroduce exactly the lifetime bug `streaming-5` describes.

### 6.2 What is missing, and its two separable halves

There is no token, no `Cancel`, and no early-out. A chunk enqueued for a coordinate
the player has since left runs to completion — through `World::generate`
(`WoodGeneration.cpp:155-266`, including the three scatter layers at `:268-270`) and
the per-vertex sampling loop at `WoodPreparedChunk.cpp:14-22` — and is then silently
discarded by the distance gate at `WoodWorldStreaming.cpp:63`.

That splits into two problems with different fixes:

**(a) Discarding the result is free — do this first.** A completed future for a
coordinate outside the desired window needs no `Get()`. Remove the entry and let the
future destruct; the value is discarded and no mesh work happens. This saves the
integration cost only.

**(b) Stopping the generation is not free, and cannot be done without touching the
tested core.** `World::generate` is a single monolithic loop with no cancellation
hook, and `Tests/GenerationTests.cpp` pins its signature and its determinism
properties. Two candidate granularities:

- Check the flag between the phases inside `WoodPreparedChunk` — specifically inside
  the per-vertex loop at `WoodPreparedChunk.cpp:14-22`. Requires **no** change to
  `World::generate`'s signature, which is the property the tests depend on.
- Check inside `World::generate`. Cheaper per check, but changes a pure function's
  contract and its tests.

**Which phase dominates is unmeasured.** I cannot run the suites to attribute cost
between `generate()` and the per-vertex loop, and `CLAUDE_REVIEW.md:18` reports
~25 ms per 64-cell chunk for the whole pipeline without a split. Recommend
implementing the `WoodPreparedChunk.cpp:14-22` check first because it is the
lower-risk placement, and measuring the split before claiming any cancellation
figure.

### 6.3 M2 and H4 are the same code path

Whatever the mechanism, a cancel is a *removal from `Runtime->Jobs`*. It inherits
every hazard in §2: it must not hold a reference into the map across the removal,
and it must not leave an entry behind. Concretely:

- Every mutation site of `Runtime->Jobs` — drain (`:63`), cancel (new), dispatch
  (`:79`) — takes ownership of the future into a local first, then removes.
- The enqueue side needs a duplicate guard. `:77-79` computes `Key` from
  `Plan.needed`, which is deduplicated against `loaded`/`pending` inside `plan()`, so
  the key is currently unique by construction. Adding a cancel list to `plan()` keeps
  that property **only if** the cancelled coordinate is removed from `pending` in the
  same call that returns it as stale. A stale entry that is neither pending nor
  blocked would be re-dispatched — the §4 storm again, this time for a legitimate
  coordinate.
- `Plan::stale` (`.clanker/CLAUDE_REVIEW.md:59` proposes exactly this) should be
  computed with `retained(coord, center, retainRadius)` — i.e. only coords outside
  the retain radius are stale — so a cancel never races the retention rule at
  `WoodWorldStreaming.cpp:64`.

### 6.4 Ordering against the save/resume journal

If `save-resume-design.md` §6.2 lands, its dispatch rule flushes a `JOBR` record to
disk *before* the future exists (`save-resume-design.md:335-336`). A cancel must then
also be durable, or a resume resurrects a job nobody wanted and the journal's
`saved pending ∪ live pending` cap (`save-resume-design.md:342-344`) is violated
across the seam. Land cancellation with the awareness that the journal is coming;
do not build a cancel path that would need rewriting.

---

## 7. Reachability, precisely

`chunkSize = 128` (`WoodWorld.cpp:38`; default at `WoodGeneration.h:9`). The runtime
converts cm→metres by `/100` and cm→chunk by `/12800` (`WoodWorldStreaming.cpp:21`,
`:61`).

### 7.1 The numbers

| Quantity | Value |
| --- | --- |
| Largest legal chunk index | 7804 (7805 × 128 = 999,040 > 999,000) |
| Chunk 7804 far edge | 999,040 m |
| Player cm entering chunk 7805 | 99,904,000 cm = **999.04 km** |
| Chunk-level throw window | 999.04 km → 1,000 km, about **960 m** wide |
| `validatePoint` throw point | 1,000,000 m = **1,000 km** (chunk index 7812.5) |
| `plan`'s effective bound | ~274,877,906,048 m — **275,000× looser** than the generator |

Note the guard at `WoodGeneration.cpp:151` tests the chunk's **origin corner**, so
the true supported extent is 999,040 m per axis, not the 999,000 m the code implies.
Minor, but it should be documented rather than left as a discrepancy.

### 7.2 Which throw fires first

Between 999.04 km and 1,000 km the player position is still inside `validatePoint`,
so `WoodWorld.cpp:133` succeeds and the **chunk** path is the only failure — this is
exactly the window H4 describes. Beyond 1,000 km, `WoodWorld.cpp:133` throws first,
every frame, and no change confined to `WoodWorldStreaming.cpp` helps.

### 7.3 Not reachable by walking; reachable four other ways

At 420 cm/s (`Status.md:17`), 99,904,000 cm is 237,867 s ≈ **2.8 days** of
continuous walking in a straight line, and 8.3 days if every step were the 280 cm/s
wading speed. Seated time dilation cannot help: `rate()`
requires seated (`WoodGeneration.cpp:292`) and `WoodCharacter.cpp:42` sets
`MaxWalkSpeed = 0` when seated. **Ordinary play cannot trigger H4**, consistent with
`.clanker/CLAUDE_REVIEW.md:37`.

The reachable triggers are:

1. **Launch argument.** `-WoodStartX=999040` → `ExplorerStart` returns
   `FVector(X*100, ...)` (`WoodWorldStreaming.cpp:17`) = 99,904,000 cm →
   `CX = 7805` → the `BeginPlay` warm-up loop at `WoodWorld.cpp:123` calls
   `WoodPrepareChunk`, which throws at `WoodGeneration.cpp:152`. The exception
   escapes `Generate()` → `BeginPlay` and is fatal **before `Tick` ever runs**. This
   is the cheapest reproducer and needs no code change. [unverified — cannot run]
2. **Teleport or debug move.** Any future fast-travel, respawn-at-waypoint, or
   physics blow-out to a saved coordinate.
3. **Save/resume.** `save-resume-design.md:302-303` already validates against
   `validatePoint`'s 1e6 bound — but not against the 999,000 m chunk bound, so a save
   validated under the looser rule resumes into the chunk-level throw.
4. **Developer console.** `AWoodCharacter::WoodView` (`WoodCharacter.cpp:75`) calls
   `GroundAt` at `:106` and `EnsureTerrainAround` at `:107`, both of which throw.

Trigger 3 is the one worth fixing alongside this defect: it turns a code path
nobody exercises into one that a future save feature exercises by construction.

---

## 8. Implementation surface

Nothing below has been applied.

| File:line | Change | Layer |
| --- | --- | --- |
| `WoodGeneration.h` (~`:9`) | Add `SupportedExtentMetres` + `supportsChunk` | §5.3 |
| `WoodGeneration.cpp:151` | Replace the inline guard with `supportsChunk` | §5.3 |
| `WoodGeneration.cpp:25` | Derive the point bound from the same constant | §5.4 |
| `WoodStreaming.h:17-21` | Add `Plan::refused`, `plan` parameter for blocked coords | §5.3 |
| `WoodStreaming.cpp:24-27` | Filter unsupported coords into `refused` | §5.3 |
| `WoodStreaming.cpp:18-19` | Keep, but document as a type-safety guard, not a domain guard | §5.1 |
| `WoodWorldStreaming.cpp:63` | Move ownership out, `Remove`, then `Get()` in `try` | §2 |
| `WoodWorldStreaming.cpp:66-69` | Apply the same ownership discipline to `Runtime->Chunks` | §2.3 |
| `WoodWorldStreaming.cpp:22` | Route through the total prepare entry point | §3.4 |
| `WoodWorldStreaming.cpp:79` | Task body returns `FWoodJobResult`; capture a cancel token by value | §3.1, §6 |
| `WoodWorldStreaming.cpp:74` | Pass `Generator.settings().chunkSize`, not a literal `128` | §5.2 |
| `WoodWorldStreaming.cpp:76` | Use `Plan.availableJobs` | §5.3 |
| `WoodRuntime.h:9` | `Jobs` value type → `FWoodJobResult`; add `Refused`, `Stale` | §3.1, §4 |
| `WoodWorld.cpp:133`, `WoodCharacter.cpp:45` | Clamp position before the generator call | §5.4 |

Suggested landing order, smallest reviewable unit first: §2 alone (3 lines, no type
change) → §5.3 (the contract) → §3.4 + §3.1 (total prepare) → §5.4 (position clamp)
→ §6 (cancellation). §4's refusal set must land with §2 or with §5.3; it cannot be
deferred past either.

---

## 9. Acceptance evidence

**Cannot be produced on this machine.** `Docs/clanker/WorkerBrief.md:30-33`: no
Unreal, no Visual Studio Build Tools, no MSVC/clang/gcc. `Tools/Test-Streaming.cmd:4-5`
calls `VsDevCmd.bat` from a path the brief records as absent. Nothing below has been
run. What follows is what a worker with a compiler should write.

1. **`Tests/StreamingTests.cpp` — refusal.** `plan()` centred so the window crosses
   the support boundary asserts `refused` is non-empty and that **no** coord in
   `needed` fails `supportsChunk`. This is the direct regression for H4's enqueue arm.
2. **`Tests/StreamingTests.cpp` — no drift in existing assertions.** Every existing
   assertion (`StreamingTests.cpp:12-42`) uses centres `0,0`, `-1,-2`, `1,0`, `20,-20`
   with radii ≤ 5. The largest coord any of them reaches is 25, far inside 7804, so
   **no existing assertion should change meaning**. A test that proves this is worth
   more than a claim that it is true.
3. **`Tests/GenerationTests.cpp` — the anti-drift test, and the important one.**
   Assert `supportsChunk(Settings{seed,128,64}, 7804, y)` is true **and** that
   `generate(7804, y)` does not throw, and that `supportsChunk(..., 7805, y)` is false
   **and** that `generate(7805, y)` throws `std::invalid_argument`. Predicate and
   behaviour asserted together, in both directions. If only the predicate is tested,
   the two layers can drift apart again — which is how H4 arose.
4. **`Tests/StreamingTests.cpp` — retry does not recur.** With one coord blocked, two
   consecutive `plan()` calls return it in `refused` both times and never in `needed`.
   This is the §4 regression.
5. **A runtime test, once the engine is back.** Launch with `-WoodStartX=999040` and
   assert no fatal error and a loaded chunk count > 0. Note
   `.clanker/CLAUDE_REVIEW.md:179-190` (`harness-1`, `harness-2`): the Unreal gate
   currently passes when only 1 of N tests ran and can read a stale report. **Fix the
   gate before trusting any new runtime test result**, or a green run proves nothing.

`.clanker/CLAUDE_REVIEW.md:343` also records that the UE module builds C++20 with
exceptions while every standalone suite uses `/std:c++17`, and that no `try` wraps
generator throws. The fix introduces the first `try` in this area; whether the
standalone and module exception settings agree is worth checking at the same time.

---

## 10. Unresolved questions — human authority

These change player-facing behaviour or scope, so they are not decided here.

1. **What happens when the player leaves the supported extent?** Refuse and let them
   walk into empty void with a logged explanation; hard-clamp the pawn to the
   boundary; or refuse and surface a message. **Recommendation: clamp.** It is the
   only option that removes `WoodWorld.cpp:133` and `WoodCharacter.cpp:45` as
   reachable faults rather than merely making them survivable, and the boundary is
   ~999 km from origin — far enough that no player will meet it by accident.
2. **Should the 999,000 m bound be widened?** It reads as a milestone limit
   (`WoodGeneration.cpp:152` says "milestone coordinates"), not a mathematical one —
   the noise and warp functions are smooth everywhere and the core uses `double`.
   The real ceiling is precision, not throwing: `WoodWorldStreaming.cpp:31` converts
   to cm and `FProcMeshVertex` positions are `float`, so at 10¹³ cm the float32
   spacing is ~10⁶ cm ≈ 10 km — visible quantisation long before any throw. **If the
   extent is ever widened, the mesh precision must be widened with it.**
3. **How much of the five-constant problem is in scope?** Fix the
   streaming/generator pair (H4) and record `WoodHex.h:15` (2,000,000 m),
   `WoodGeneration.cpp:128` (lattice 835, currently unenforced during generation),
   and `validatePoint` (1,000,000 m) as a follow-up? **Recommendation: fix the pair
   plus `validatePoint` now**, since §5.4 needs its bound anyway, and record the
   other two.
4. **Should `plan()` gain one parameter or two?** §5.3 needs `blocked`;
   `save-resume-design.md:441` needs `visible`. Merging them is a single signature
   change but couples two independent designs. Merging is cheaper and avoids two
   rounds of churn in the same header; splitting keeps each design reviewable alone.
   **Recommendation: merge**, but this is a scheduling decision for the human, not
   a technical one.
5. **Is a refusal set the right durable state, or should failed coordinates be
   persisted?** If save/resume lands, a refused coordinate should not be re-attempted
   on resume. That is a journal-schema question for `save-resume-design.md` §5, not
   for this defect.
