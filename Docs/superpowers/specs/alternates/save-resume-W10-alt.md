# Save, resume, and irreversible forgetting — design

Authored 2026-10-06 · status: design only, nothing implemented by this document

## Overview

Milestone 2 in [Specification.md](../Specification.md) §11 asks for four things at once: generate ahead
asynchronously, retain nearby geography, discard distant regions beyond the backtracking buffer, and
save enough state that an interrupted generation task resumes without creating a different seam.
§7 and [BiomeGeneration.md](../BiomeGeneration.md) §8 add the constraint that makes this hard: during
ordinary play a forgotten cell address receives a **fresh generation identity**, and a coordinate hash
alone cannot implement that.

This document specifies the on-disk format, the meaning of a fresh identity, the pending-job journal,
and the resume guarantee, in terms of the code that exists today:

- `Source/TheWood/Public/Generation/WoodHex.h` — axial `(q,r)` ownership, canonical `Edge`, bounded warp, 19-cell normalized weights.
- `Source/TheWood/Public/Generation/WoodGeneration.h` / `WoodGeneration.cpp` — `World::region/regions/sample/streamX/streamHalfWidth/generate/terrainHeight`, `Region::identity`, `Settings{seed,chunkSize,cells}`.
- `Source/TheWood/Public/Generation/WoodStreaming.h` / `WoodStreaming.cpp` — `streaming::Settings/Plan/Coord`, `plan()` scheduling, `retained()` window test.
- `Source/TheWood/Private/WoodRuntime.h` — `TMap<FIntPoint,FWoodResident> Chunks`, `TMap<FIntPoint,TFuture<FWoodPreparedChunk>> Jobs`.
- `Source/TheWood/Private/WoodWorldStreaming.cpp` — the adapter: job dispatch, `Realize()`, unload, `wood::streaming::plan(Position.X/100, Position.Y/100, …)`.

No source file is modified here. Names in backticks are the ones proposed for the implementation.

## 1. Unit boundary

The engine-independent core is **metres**; Unreal is **centimetres**. This is already the rule stated in
`WoodGeneration.h` ("Engine-independent generation coordinates are metres; the Unreal adapter converts to cm")
and enforced at exactly two places today: `AWoodWorld::ForestAt` divides by 100, and `WoodWorldStreaming.cpp`
divides `Position.X/100` before calling `plan()` and multiplies prepared vertices by 100.

The save file obeys the same boundary:

| Quantity | Stored as | Notes |
| --- | --- | --- |
| Chunk coordinates | integer chunk indices | `chunkSize` = 128 m; index = `floor(metres/128)` |
| Player position, region origins, feature positions, water elevation | metres, `double`, fixed 4 decimals | Never centimetres. A save file must not be readable only by one engine scale |
| Yaw | degrees in `[0,360)` | Matches `random(...)*360` feature yaw |
| Cell address | axial integers `q,r` | Hexes stay independent of chunk squares |
| Yaw of the player camera | degrees, `double` | Restored as `FRotator` on the game thread |

`#include` boundaries follow the existing convention: the save/identity/journal types live in
`Source/TheWood/Public/Generation/` and use only `<cstdint> <string> <vector> <stdexcept> <cmath>`,
so `Tests/` can compile them with the isolated compiler used by `Tools/Test-Streaming.cmd`.
`IWritableFileIO`/UObject work stays in the adapter.

## 2. What must and must not be saved

**Must be saved** — everything that is not a pure function of `(seed, retained identity map, recipe version)`:

- journey identity: `seed`, `recipe` version, monotonically increasing `epoch` and the incarnation table;
- tombstones for retired `(q,r)` addresses, so a fresh identity is never the old one again;
- retained cell incarnations: `(q,r) -> identity`, plus per-cell derived commitments (family, unreal flag, ruin eligibility, and any committed edge contract);
- the retained chunk set with its `Detailed` flag, so a resumed world rebuilds the same neighbourhood in the same realization order;
- pending generation jobs (§4) and the player's position, yaw, seated/accelerated state and observation clock;
- the streaming window actually used (`chunkSize`, `desiredRadius`, `retainRadius`, `maxConcurrentJobs`).

**Must not be saved** — anything whose value is already implied by the above:

- terrain vertices, normals, UVs, biome vertex colours, instance transforms. They are pure functions of
  `(seed, identity map, recipe version, chunk index)`. `WoodWorldStreaming.cpp` already captures exactly this
  state per job: `const wood::World Snapshot=Generator;` plus the placement profiles and availability vector.
  Re-storing geometry would let a save file and a regenerated chunk disagree, which is the seam this design exists to prevent.
- HISM instance ids (`FPrimitiveInstanceId`). They are runtime bookkeeping; after a load nothing references the
  pre-load ids, and `Realize()` re-adds instances from the same deterministic transforms.
- Photographs. Already independent: `AWoodCharacter::Photograph` writes `Saved/Photos/<utc-guid>.png`.

The general rule: **the save stores commitments, the generator stores consequences.**

## 3. On-disk format

### 3.1 Location, naming, write safety

- `Saved/Wood/journey-<index>.woodsav`, index starting at `0001`, next index = highest existing + 1.
  Photographs stay in `Saved/Photos` and are never moved or deleted by a journey save.
- Write to `journey-<index>.woodsav.tmp`, flush, then replace the destination. A crash mid-write leaves either
  the previous complete file or the `.tmp`; a `.tmp` with no destination is discarded on next load.
- Every file is validated by a trailing `end <crc>` line. CRC is FNV-1a over the exact bytes of all
  preceding lines, matching the integer-hash style already in `WoodGeneration.cpp`.

### 3.2 Line format

ASCII, one record per line, space-separated, `#` starts a comment line (kept for human inspection).
Versioned: `wood-save <version> <recipe>` where `version` is this document's format version (`1`) and
`recipe` is the generator recipe version. An unknown `version`, an unknown record name, a malformed field,
or a CRC mismatch is a **whole-file rejection** — the same discipline `streaming::plan()` uses when it
throws `std::invalid_argument` for out-of-range settings. A rejected save starts a new journey; it never
half-restores. Rejection reasons are logged with `UE_LOG` and surfaced once on screen.

All floats are printed with `%.4f` metres (0.1 mm) and parsed with `std::stod`; all identities are printed
as unsigned 32-bit decimal. Parsing must reject non-finite values, matching `validatePoint()` in
`WoodGeneration.cpp`, which refuses non-finite input and coordinates beyond ±1,000,000 m.

### 3.3 Record grammar

```
wood-save 1 1
seed 12345
epoch 41
settings 128 4 6 2
player -180.0000 -180.0000 0.0000 180.0000 0.0000
time 512.2500 seated=1 accelerated=0
cell 0 0 2741205331 temperateforest unreal=0 ruin=1 phase=1.2043
cell 1 0 918744120 drygrassland unreal=1 ruin=0 phase=4.8817
tomb -1 0 40
edge 0 0 1 0 kind=channel pos=1516.0000,175.0000 width=3.1000 bed=112.4400 water=112.9000
keep 0 0 detailed=1
keep 0 -1 detailed=0
job 9001 4 2 detailed=1 digest=6f21c0a4
job 9002 5 2 detailed=1 digest=6f21c0a4
done 9001
end 3f1c9a2e
```

Record meanings:

- `seed` — the `wood::Settings::seed` the world was built with. On resume the adapter constructs
  `wood::World({Seed,128,64})` from **this** value; a `-WoodSeed=` on the command line applies only when
  starting a journey with no valid save.
- `epoch` — the global incarnation counter (§4). Monotonic within a file; a file whose `epoch` is lower than
  the highest tombstone generation is rejected.
- `settings` — `chunkSize desiredRadius retainRadius maxConcurrentJobs`, re-validated on load against the
  same limits `plan()` enforces (`desiredRadius` 0..32, `retainRadius` ≤64 and ≥ `desiredRadius`,
  `maxConcurrentJobs` > 0). A saved window that fails validation is clamped and logged, not fatal.
- `player x y z yaw pitch` — metres, degrees. Restored as `FVector(x*100,y*100,z*100)` and
  `FRotator(pitch,yaw,0)`. Also used to recompute `streaming::center` so the retained window matches.
- `time seconds seated=<0|1> accelerated=<0|1>` — the `wood::Observation` clock. `accelerated` is forced to
  `0` if `seated` is `0`, because acceleration only exists while seated.
- `cell q r identity family unreal=<0|1> ruin=<0|1> phase=<radians>` — one **live incarnation** of a retained
  hex cell. `identity` is the authoritative value; `family`, `unreal`, `ruin` and `phase` are cached so a
  reader (and a diff) can see the place's character without re-running generation, and so a recipe change can
  be detected. `phase` is radians because `Region::phase` is radians (`random(...)*2*pi`).
- `tomb q r generation` — a retired address and the epoch generation that retired it.
- `edge q1 r1 q2 r2 kind=… <payload>` — a committed boundary contract for the canonical undirected
  `wood::hex::edge({q1,r1},{q2,r2})`, always written with `(a,b)` in the ordering `Edge::a < Edge::b`
  produces. This is where the channel record from `BiomeGeneration.md` §4 lives: position, tangent, width,
  bed elevation, water elevation, flow direction. In this increment the payload is a placeholder record
  with a defined field set; the macro-catchment planner that fills it properly is deferred work, and the
  record must be written even when empty so later versions can add fields without breaking reads.
- `keep x y detailed=<0|1>` — a retained terrain chunk index. Only `Detailed` distinguishes a full chunk from
  a coarse terrain-only chunk (`Realize(Prepared, Detailed=false)`), so that flag is what has to survive.
- `job seq x y detailed=<0|1> digest=<u32>` — a pending generation job (§4.2). `seq` is a monotonic `uint64`.
- `done seq` — a job that completed before the snapshot was taken.
- `end crc` — end of file and integrity check.

Records may appear in any order except that `wood-save` must be first and `end` must be last; readers build
in-memory maps and must tolerate a trailing incomplete line only by rejecting the file (§3.2).

### 3.4 In-memory shape

Parsing yields a plain value struct with no engine types, so it can be unit tested with the isolated
compiler:

```
struct FWoodSavedCell { wood::hex::Coord cell; std::uint32_t identity; wood::Biome family; bool unreal, ruin; double phase; };
struct FWoodSavedJob { std::uint64_t seq; int x, y; bool detailed; std::uint32_t digest; };
struct FWoodSave {
  std::uint32_t seed, epoch, recipe;
  wood::streaming::Settings settings;
  double x, y, z, yaw, pitch, seconds; bool seated, accelerated;
  std::vector<FWoodSavedCell> cells;
  std::vector<wood::hex::Coord> tombstones;   // with their retiring generation
  std::vector<FWoodSavedEdge> edges;
  std::vector<FWoodSavedChunk> kept;          // chunk index + Detailed
  std::vector<FWoodSavedJob> jobs;
};
```

Writing must be order-stable (sort by `q,r`, by `x,y`, by `seq`) so two saves of the same state produce
identical bytes — which is what makes the resume landmark test in §6 checkable by hash instead of by eye.

## 4. Fresh identity for a forgotten region

### 4.1 What is wrong today

`describe()` in `WoodGeneration.cpp` sets `r.identity=hash(c.seed,gx,gy,701)` and derives family, phase and all
downstream content from `c.seed` plus the address. `hex::warp` phases on the seed as well. So unloading a
chunk and walking back reproduces the same place exactly — reproducible, and precisely the behaviour
`Docs/Status.md` and `README.md` record as "not irreversible forgetting". `BiomeGeneration.md` §8 states the
rule plainly: a coordinate hash alone cannot implement forgetting.

### 4.2 The rule

**Identity = hash(journeySeed, epoch, q, r, salt)**, where `epoch` is a journey-wide 32-bit counter that
advances every time any cell incarnation is retired. All *content* of a cell — family, unreal flag, ruin
eligibility, phase, discovery composition, feature and terrain seeds — derives from `(seed, identity)`, never
from `(seed, q, r)` alone. The hex lattice itself (ownership, warp, edge weights) stays a function of the seed
and the address, so the *topology* a player navigates is continuous while the *content* of a revisited cell
is new. Topology continuity is what keeps routes and coordinates meaningful; content change is what makes
forgetting irreversible.

Concretely:

```
identity(q,r)      = hash(seed, epoch, q, r, 701)      // replaces hash(seed,q,r,701)
family(q,r)        = suitability-weighted pick from hash(seed, identity, 704)
phase(q,r)         = (hash(seed, identity, 705)/2^32) * 2*pi
unreal/ruin flags  = independent rolls on hash(seed, identity, 706/707)
feature/terrain    = all existing `random(config.seed, …)` calls take the cell identity in place of the address
```

The interior `hash` overload and `random`/`noise` helpers in `WoodGeneration.cpp` stay; what changes is the
argument they are called with. Because identity is a pure function of `(seed, epoch, q, r)`, a save only needs
the epoch counter plus the live `(q,r)->identity` map — but the map is still written explicitly, because
(a) it is what a reader inspects, (b) it lets a future recipe version re-derive content without re-rolling
identity, and (c) it is the authority when two saves are compared.

### 4.3 Retiring a cell

A cell may be forgotten only when every protection has expired — outside visibility, outside the
`retainRadius` window from `streaming::Settings`, no live job, no pending discovery referencing it, and no
edge contract still alive. This is `BiomeGeneration.md` §8 and is not relaxed here. Retirement is one
transaction, in this order:

1. Drop its chunks from `FWoodRuntime::Chunks` and destroy ground/water components; remove its HISM instances
   via the recorded `FPrimitiveInstanceId`s.
2. Cancel or invalidate any pending job for that cell (§4.4) — a job holding a retired identity must never
   be realized.
3. Append `tomb <q> <r> <generation>` with `generation = epoch`, then increment `epoch`.
4. Remove the cell from the live map. Its `edge` records stay until the other incident incarnation or a
   visible shared feature no longer needs them.

Because `epoch` is journey-global and monotonic, a coordinate can never be handed the identity it had before.
`identity` collisions between a live cell and a retired one are astronomically unlikely for the same address
(each address sees a distinct `epoch`), and two different addresses colliding is a 1-in-2^32 event per pair;
the loader detects duplicates within a file and rejects them.

### 4.4 Invariants

- No live cell and no tombstone shares an address with a different identity.
- Identity never decreases in epoch for a given address.
- A retired cell's chunks are destroyed before its tombstone is written, so a crash cannot leave a live
  chunk whose identity is gone.
- A cell that is adjacent to a retained cell with a committed `edge` record is generated against that record
  plus a guard strip; retained terrain is never re-rolled to accommodate the newcomer.

## 5. Journal of pending generation jobs

### 5.1 Why a journal at all

`plan()` already takes `pending` and returns `needed`, and `AWoodWorld::Stream` drains one ready future per
tick. What it does not have is any durable record of *which identity a dispatched job was building*. Without
it, a resume cannot distinguish "job not yet started" from "job that was halfway through the cell I just
retired", and re-dispatching the latter would put an old landmark back into the world — a different seam.

### 5.2 Journal records

```
job <seq> <x> <y> detailed=<0|1> digest=<u32>
done <seq>
```

- `seq` — monotonic `uint64` per journey, incremented at dispatch. It orders the journal and identifies a job
  across restarts; it is not a generation input and never affects output.
- `digest` — FNV-1a over the job's dependency closure, sorted for stability: the chunk's own covering cell
  `(q,r,identity)`, every retained cell with non-zero `hex::weights` inside the chunk footprint, every live
  `edge` record incident to those cells, and `recipe`. This is the identity snapshot the job was dispatched
  with, in one comparable number.
- Write order: the `job` record is appended **before** the future is created. A crash between the two loses at
  most one job, which is then re-dispatched on load — safe, because generation is pure.
- Completion order: `done <seq>` is appended after `Realize()` succeeds on the game thread. A job that was
  dispatched but whose result is discarded (outside the retention window by the time it completed) also gets a
  `done` record, because it will never be realized.
- Snapshots are written only at points where the in-memory state matches the on-disk state: after a job
  completes, after a retire transaction, and on request (autosave interval, and on `EndPlay`). Between those
  points the `job`/`done` records in memory are authoritative; the file is a lagging but consistent copy.

### 5.3 Resume of pending jobs

On load:

1. Every `job` seq with a matching `done` is skipped — it already produced its content.
2. Every `job` seq without a matching `done` is re-dispatched with the **same** `(x, y, detailed)` and with a
   `wood::World` snapshot rebuilt from the saved seed and identity map. Because generation is a pure function
   of that snapshot plus the coordinate, the re-dispatched job returns geometry identical to what the
   interrupted job would have returned. Nothing is "completed halfway": a chunk is either realized or not.
3. The recomputed digest must equal the journalled digest. If it does not, the job is **not** dispatched; the
   mismatch is logged and the chunk is left to normal `plan()` scheduling in the current session. This is the
   safety valve against a save file that disagrees with the recipe version — a stale file degrades to
   "regenerate from the live identity map", never to "paste the wrong place in".
4. `Runtime->Jobs` is rebuilt through the same `Async(EAsyncExecution::ThreadPool, …)` path used live, so the
   resumed path exercises the production code rather than a special one. At most `maxConcurrentJobs` run at a
   time, exactly as `plan()`'s `availableJobs` enforces.

A job whose digest mismatches because its cell was tombstoned between dispatch and load is the same case: skip
and let the scheduler allocate a fresh job under the new identity.

## 6. Resume guarantee for landmarks

A landmark in this game is any composition the player can recognize and navigate by: a ridgeline, an old tree
grove, a stream bend, a boulder cleft, a ruin, an overlook. `BiomeGeneration.md` §5 and §7 make the contract:
a landmark stays consistent and reachable, and it is never replaced between seeing it and reaching it.

Three mechanisms together produce that guarantee:

1. **Identity-addressed content.** A landmark's shape derives from `(seed, identity(q,r), kind, index)`.
   With the identity map restored from the save, the landmark that existed at `identity I` is recomputed at
   `identity I`. Nothing is remembered as *geometry*; it is remembered as *which incarnation the address had*.
2. **Order-independent generation.** `BiomeGeneration.md` §7 forbids generation order from affecting output,
   and the current `describe()`/`hash` design already satisfies it. So a chunk completed before the quit and
   one regenerated after the resume are the same bytes.
3. **Stale-identity rejection.** The `digest` check (§5.3, step 3) refuses to realize a result whose
   dependencies changed while it was in flight. This is what makes "interrupted mid-generation" safe: the
   resumed job either agrees with the saved identity closure and is identical, or it is dropped rather than
   pasted in as a new seam.

The seam that must not appear is specifically at chunk boundaries (128 m squares) and cell boundaries (950 m
hexes). Both are functions of `(seed, topology)`, neither of which changes on resume, so shared edges match;
and both sides of a shared edge are either in the retained set (regenerated identically) or in the fresh-identity
set, where the `edge` contract record keeps the shared channel agreeing.

### 6.1 Resume procedure (adapter side)

1. `AWoodWorld::BeginPlay` reads `WoodSeed` from the command line; if the newest valid `Saved/Wood/*.woodsav`
   loads, the saved seed wins (a mismatch between `-WoodSeed` and the file is logged).
2. Build `Generator = wood::World({Saved.seed,128,64})` and install the identity map into the region
   description path before any sampling happens. Region queries for a retired address are answered from
   tombstones as "not live", so `describe()` cannot be called for them.
3. `Generate()` runs as today: the coarse grid, water ribbon, sky, lights, vegetation ISMs.
4. Player transform and `Observation` clock are restored in metres → centimetres.
5. Retained chunks are realized in saved order with their saved `Detailed` flag, using `WoodPrepareChunk` on
   the thread pool exactly as live dispatch does.
6. Unresolved `job` records are re-dispatched per §5.3.
7. `Stream()` takes over on the next tick with `Runtime->Jobs` and `Runtime->Chunks` already populated; the
   first `plan()` call therefore sees a consistent `loaded`/`pending` pair and does not re-request work that
   is already resident.

## 7. Files this design implies (not created here)

| File | Contents | Compiles with |
| --- | --- | --- |
| `Source/TheWood/Public/Generation/WoodContinuity.h/.cpp` | incarnation allocation, tombstones, digest, contract records | isolated `cl /std:c++17` suite |
| `Source/TheWood/Public/Generation/WoodSave.h/.cpp` | record grammar, parse/serialize, CRC, atomic replace helper | isolated `cl /std:c++17` suite |
| `Tests/ContinuityTests.cpp`, `Tests/SaveTests.cpp` | format round-trip, order stability, rejection cases, digest sensitivity | new `Tools/Test-Save.cmd` modelled on `Tools/Test-Streaming.cmd` |
| `Source/TheWood/Private/WoodWorldSave.cpp` + `WoodWorld.h` hooks | load in `BeginPlay`, autosave tick, `EndPlay` flush | Unreal editor target |

`Tests/StreamingTests.cpp` is the style model: one `main()`, `assert`-based, a single `PASS:` line naming
what was checked. Save tests must also assert **byte stability** — serialize the same state twice, compare
strings — because §6 depends on inspectable, diffable output.

## 8. Verification

Milestone 2 requires validating "travel in multiple directions, local returns, distant views, repeated
forgetting, interruption, and save/resume". Concretely:

- Retained identity round-trip: save → load → save produces identical bytes.
- Fresh identity: retire `(2,1)`, walk 5 km away, walk back; the loaded cell's identity differs from the
  retired one and the tombstone for `(2,1)` is still present with the earlier generation.
- Digest sensitivity: changing one live cell identity, one `edge` payload, or `recipe` changes the affected
  job digest; a saved digest mismatch is skipped, never realized.
- Interrupted job: dispatch a chunk, snapshot before `done`, load, confirm the re-dispatched job's digest
  matches and the realized vertex buffer equals the pre-interrupt buffer exactly (hash comparison, not visual).
- No-seam: after load, compare `terrainHeight` and vertex normals across the four chunk edges of the restored
  centre and across the shared cell edge of a retained/fresh pair; they must match the pre-quit values.
- Landmark stability: photograph-consistent comparison of a named landmark transform (metres, degrees) before
  and after resume.
- Unit discipline: a static check that the save module never multiplies by or divides by 100, and that the
  adapter performs every `*100`/`/100` at the boundary only.
- Runtime: extend `Source/TheWood/Private/Tests/WoodStreamingRuntimeTests.cpp` with a save-load cycle while the
  player stands still, and one while walking, asserting `LoadedChunkCount()` and the restored clock.

## 9. Deliberately deferred

- Macro-catchment channel planning that fills the `edge` payload beyond the defined placeholder field set.
- Per-discovery payload state (ruin damage progression, photograph anchors) beyond the retained identity map.
- The fixed parking lot, opening forest and occluded entrance (Milestone 3) — the save format has no
  `journeyKind` field yet; adding one later is a version bump with a default, not a format break.
- Save slots and gallery browsing. The format supports many files already; only slot naming and UI are missing.
- Cloud/weather state beyond the observation clock. §6 already stores `seconds`; weather fields follow the
  same `key=value` payload style as `edge` when they exist.

## 10. Open questions

1. Autosave cadence. Autosaving every completed job means many small writes; the photograph-style
   `Saved/` convention tolerates that, but a fixed interval (say every 20 s of wall clock, plus
   `EndPlay`) may be kinder to disk and still leave at most 20 s of re-dispatch.
2. Whether `keep` records should store realized instance ids after all, if a future gallery or a
   "what did I photograph here" feature needs to bind to instances that survive a resume within one process.
3. Whether identity needs a per-cell incarnation *counter* in addition to the global `epoch`, for save files
   that will be merged or for a future "return to a place I saw in an earlier journey" feature. The global
   `epoch` alone is sufficient for the current acceptance gate.
