# Save, Resume, and Irreversible Forgetting Design

## Overview

This design covers the Milestone 2 requirements in [Specification.md](../../Specification.md) §11 and §7: generate ahead asynchronously, retain nearby and visible geography, discard distant regions beyond the backtracking buffer, save retained state and pending identities, and resume an interrupted generation task without producing a different seam or a different landmark.

It also covers the §7 rule that a forgotten region receives a **fresh identity** and cannot be re-derived from the location seed by walking back to old coordinates.

Scope is design only. This document proposes headers, records, and call sites; it changes no source file.

Key existing facts this design builds on (verified in source):

| Fact | Location |
| --- | --- |
| Generation-domain coordinates are **metres**; the Unreal adapter converts with `*100` | `WoodGeneration.h` header comment; `WoodWorldStreaming.cpp` |
| Chunk grid is `chunkSize = 128` m = `12800` cm | `WoodStreaming.h`, `WoodWorldStreaming.cpp` (`Position.X/12800`) |
| Streaming planning is pure scheduling, no generation or assets | `WoodStreaming.h` `plan()` |
| Regional identity is `hash(seed, q, r, 701)`; biome family `704`; light phase `705` | `WoodGeneration.cpp` `describe()` |
| Discovery allocation is `hashCell(seed, cellQ, cellR) % 3 == 0` | `WoodDiscovery.cpp` `planDiscovery()` |
| Hex warp is seed-only and fold-free; influence is a 19-cell smooth blend that decays to zero two cells out | `WoodHex.h` `warp()`, `weights()` |
| Async jobs are `Async(EAsyncExecution::ThreadPool, ...)` returning `FWoodPreparedChunk` from a **snapshot** of `wood::World` | `WoodWorldStreaming.cpp` |
| Retention today is `ChunkRadius + 2`; jobs at most 2 in flight | `WoodWorldStreaming.cpp` |

## 1. Units boundary (normative)

The existing boundary is preserved and extended, not crossed.

- Everything inside `Source/TheWood/Public/Generation` and its `Private/Generation` implementations stays in **metres**, as `double`.
- Everything Unreal-side stays in **centimetres**, as `FVector`/`double` (`GroundAt(Xcm, Ycm)`).
- The save format stores **both**, in a way that cannot be confused. Two explicit families:
  - generation records: metres, field names suffixed `M` (`OriginXM`, `OriginYM`, `RadiusM`);
  - runtime records: centimetres, field names suffixed `Cm` (`PlayerXCm`).
- A value is converted exactly once, at the adapter boundary: `Position/100` going in, `*100` coming out. No save-loading code may divide or multiply by 100.
- Rationale: a 100× unit error is silent and destroys the world. A field suffix is not.

Consequence: the save format is engine-independent and readable by the Zig/MSVC test toolchain, exactly like the rest of `Tests/` — no `CoreMinimal.h` in the persistence layer.

## 2. Fresh identity for a forgotten region

### 2.1 Why the current identity cannot express forgetting

`describe()` derives every regional property from `hash(config.seed, gx, gy, salt)`. `World::sample`, `terrainHeight`, `generate`, and `planDiscovery` are therefore pure functions of `(seed, position)`. Revisiting a forgotten region regenerates it byte for byte. That is correct for a reproducible-seed debugging mode and wrong for endless play.

### 2.2 Epoch-based identity

Add a per-region **epoch** that participates in the identity hash:

```cpp
// Public/Generation/WoodGeneration.h
// Epoch 0 is the authored seeded world; n>0 are successive regenerations of a forgotten region.
using Epoch = std::uint32_t;

std::uint32_t regionIdentity(std::uint32_t seed, int q, int r, Epoch epoch);
```

with the mixing rule fixed as:

```cpp
std::uint32_t mixEpoch(Epoch epoch) { return epoch * 0x9e3779b9u; }
std::uint32_t regionIdentity(std::uint32_t seed, int q, int r, Epoch epoch) {
  return hash(seed, q, r, 701u ^ mixEpoch(epoch));
}
```

and every other salt in `describe()` (`704` family, `705` phase, and the moisture/roughness/canopy/exposure lookups) derives from `regionIdentity(...)` instead of `hash(seed, gx, gy, salt)`.

Two properties follow, and both are required:

1. **Epoch 0 is bit-identical to today's world.** `mixEpoch(0) == 0`, so existing seeds, tests, and screenshots are unaffected. `Tests/GenerationTests.cpp`, `HexTests.cpp`, and the biome expectations keep passing unchanged.
2. **Epoch n ≠ epoch m for n ≠ m** with overwhelming probability, so a forgotten region gets new biome family, roughness, canopy, exposure, light phase, terrain, and a new discovery allocation — from one changed word.

### 2.3 Discovery identity follows region identity

`planDiscovery` allocates on `hashCell(seed, cellQ, cellR) % 3`. The same epoch must be folded in, otherwise a forgotten cell that keeps its ruin keeps the recognizable landmark and "the old entrance" stays recoverable:

```cpp
// planDiscovery gains an Epoch parameter; allocation becomes
hashCell(seed ^ mixEpoch(epoch), cellQ, cellR) % 3
```

The grammar arms and suitability tests are unchanged. Only the allocator's input changes, so a forgotten region's ruin is a *different* ruin, not the same ruin somewhere else.

### 2.4 Warp stays seed-only, on purpose

`hex::warp` keeps using the base seed with no epoch term. The warp is a smooth, fold-free domain deformation shared by every region; if it changed per epoch, the retained/fresh boundary would shear the terrain field rather than bend it. Continuity across the boundary is instead carried by `hex::weights`, whose smoothstep blend falls to zero two cells from a cell centre — so a cell's climate changes enter the surface field continuously and produce no crease at the epoch seam.

This is also why the epoch boundary must be a whole-cell boundary, never a chunk boundary: half a cell at epoch *n* blending into half at epoch *n+1* would look like weather, not geography. §5.3 forbids exactly that.

### 2.5 The forget ledger

Fresh identity is only irreversible if the epoch survives the process. A ledger entry is written **before** the region is discarded:

| Field | Type | Meaning |
| --- | --- | --- |
| `q`, `r` | `int32` | Hex cell |
| `epoch` | `uint32` | Next epoch to hand out |
| `forgottenAtChunkX/Y` | `int32` | Where the player was when it was dropped, for diagnostics |
| `forgottenObservationSeconds` | `double` | Same, for diagnostics |

- Entry rule: when a hex cell leaves the retention window (§3), its epoch is incremented and the ledger entry is appended to the journal (§4) and flushed before any chunk in that cell is destroyed.
- Re-entry rule: the epoch for `(q, r)` is `ledger.count ? ledger.at(q,r).epoch : 0`.
- Cells with no ledger entry are the untouched authored world. The player can only reach them by travelling somewhere they have never been.
- The ledger is per save slot and per seed. A different seed is a different world and starts with an empty ledger.

**Bounded size.** Ledger entries are 24 bytes packed. At one entry per forgotten hex cell, an hour of continuous travel touches on the order of a few hundred cells; a million entries would be 24 MB. The design therefore keeps the ledger exact and complete rather than compacting it, and records radial compaction as an open decision (§10). An unbounded-but-exact ledger is the honest choice: compaction trades the §7 guarantee ("cannot recover a discarded place merely by walking back") for memory, and that trade is not the design's to make silently.

### 2.6 Debug mode

`Settings` gains `bool reproducibleSeedMode = false`. When true, every lookup returns epoch 0 and the ledger is neither written nor read, so a seed reproduces a place indefinitely. This is the §7 "reproducible seeds for debugging" escape hatch, and it is the only mode in which a forgotten region can come back.

## 3. Retention: what stays, what goes

The §7 rule is that a region may be removed only after it is beyond **both** relevant visibility and the local backtracking buffer. Today only the buffer exists (`ChunkRadius + 2`).

Two radii, both expressed in chunk units and both fed to the existing `wood::streaming`:

| Radius | Default | Meaning |
| --- | --- | --- |
| `desiredRadius` | `ChunkRadius` (4) | Generate-ahead window; bounded by 32 |
| `retainRadius` | `desiredRadius + 2` | Backtracking buffer; bounded by 64 |

The visibility term is a hard floor and cannot be configured below the buffer:

```
retainRadius >= max(desiredRadius + 2, visibleChunkRadius + 1)
```

where `visibleChunkRadius` is derived from the view distance actually used for rendering (the current 3×3 `RegionLights` grid at `51200` cm tiles implies a `110000` cm light horizon, so `visibleChunkRadius = ceil(110000 / 12800) = 9`). With the defaults that gives `retainRadius = 10`, i.e. a `±1280` m retained square — roughly 1.3 km — instead of today's 6.

Removal order, per frame, on the game thread only:

1. Collect jobs whose future `IsReady()`, realize at most one per tick (existing behaviour, kept — it bounds per-frame mesh cost).
2. Compute removal keys with `wood::streaming::retained(chunk, center, retainRadius)`.
3. For each removal key, resolve the owning hex cells via `hex::owner(hex::warp(centre + 180, seed))` and the 19-cell influence set. If **any** influencing cell still has a resident chunk or an open job, the chunk is kept this frame. This is the no-seam rule (§5.3).
4. Destroy components (`RemoveInstancesById` → `DestroyComponent` → `Chunks.Remove`) for the survivors of step 3.
5. Append `FORGET` records for hex cells that just lost their last resident chunk and lie outside `retainRadius`, then flush the journal.

Landmarks are covered by the same rule for free: a landmark is a feature of a hex cell, and no cell is forgotten while a chunk that touches it is resident.

## 4. On-disk save format

### 4.1 Files

| Path | Role |
| --- | --- |
| `<SavedDir>/Wood/<Slot>.wood` | Snapshot: header + sections |
| `<SavedDir>/Wood/<Slot>.journal` | Append-only event journal (§4.5) |

Both under `FPaths::ProjectSavedDir()`. Photographs stay where §7 puts them — outside world retention — and are referenced by name only.

### 4.2 Encoding rules

- Little-endian, IEEE-754 `float64`/`float32`, packed — no compiler struct padding, no `#pragma pack`, no bitfields.
- Explicit `uint8/u16/u32/u64` integers; `int32` for coordinates; `double` for every metre value.
- Every section carries `{ tag[4], version u16, flags u16, byteLength u64, crc32 u32 }`.
- Every record is length-prefixed so an unknown trailing record can be skipped by a newer reader.
- Strings are `u32` length + UTF-8 bytes, no NUL terminator.
- Readers reject a wrong magic, an unknown section version, or a CRC mismatch, and refuse to load rather than load partially.

### 4.3 File header (32 bytes)

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 8 | magic `WOODSAVE` |
| 8 | 4 | `formatVersion` (initial value 1) |
| 12 | 4 | `headerCrc32` over bytes 0–11 and 16–31 |
| 16 | 4 | `seed` (`uint32`, the same value as `AWoodWorld::Seed`) |
| 20 | 4 | `sectionCount` |
| 24 | 4 | `snapshotSequence` — increments once per successful save |
| 28 | 4 | `snapshotUnixTime` — diagnostics only |

`formatVersion` is bumped on any layout change. `flags` in the header is reserved and must be 0 in version 1; a future reader may use it for compression without a version bump.

### 4.4 Sections

| Tag | Contents |
| --- | --- |
| `WRLD` | Generation config: `seed`, `chunkSizeM` (double), `cells`, plus the streaming settings actually used (`desiredRadius`, `retainRadius`, `maxConcurrentJobs`) so a resumed session streams identically to the saved one |
| `PLAY` | Player state: `PlayerXCm/Ym/ZCm` (centimetres, matching the engine domain), yaw/pitch/roll as degrees, `seated`, `accelerated`, `observationSeconds`, plus the character class name so a rename is detected rather than misread |
| `CELL` | Region epochs: packed `(int32 q, int32 r, uint32 epoch, int32 forgottenChunkX, int32 forgottenChunkY, double forgottenSeconds)` — the §2.5 ledger, sorted by `(r, q)` so the section delta-compresses trivially if compression is added later |
| `CHNK` | Retained chunk set: `(int32 x, int32 y, uint8 detailed)` plus `realizedUnixTime`. Geometry is **not** stored — see §4.6 |
| `LMARK` | Landmarks: see §4.7 |
| `JOBS` | Pending generation jobs: see §6 |
| `OBSV` | Small counters for validation: chunks generated this session, journal records applied, ledger entries, last resume wall-clock |

### 4.5 Journal

Append-only, one record per line of intent, written before the action it authorizes:

```
struct JournalHeader { u32 magic 'WDJ1', u32 version, u64 journalId, u64 continuationOfSnapshotSequence }
struct JournalRecord {
  u64 sequence;          // strictly increasing within the journal
  u8  kind;              // 1 FORGET, 2 JOB_OPEN, 3 JOB_CLOSE, 4 SAVE_BEGIN
  u32 payloadLength;
  u8  payload[payloadLength];
  u32 crc32;             // over sequence, kind, length, payload
}
```

- **Write-ahead.** `FORGET` is flushed before chunk destruction (§3 step 5). `JOB_OPEN` is flushed before `Async(...)` is called. If either is skipped, the crash-safe direction is wrong: an unflushed `FORGET` resurrects a discarded region, an unflushed `JOB_OPEN` simply loses a job that will be re-planned.
- **Torn tail.** On load, records are applied in order and a trailing record that is short or fails CRC is dropped, not treated as corruption. A crash mid-`write` is normal, not exceptional.
- **Compaction.** Writing a snapshot truncates the journal to a new header whose `continuationOfSnapshotSequence` names the snapshot it completes. Old journals are deleted only after the snapshot rename succeeds.
- **Flush policy.** `FORGET` and `JOB_OPEN` flush on the game thread. That is one small sequential write per chunk border crossing — a few per minute of walking — and is the price of the irreversibility guarantee. If profiling shows a stall, the fix is a background write queue plus an explicit `FlushForForgetting()` before destruction, never a skipped flush.

### 4.6 Why no geometry is stored

A retained chunk is a pure function of `(seed, chunk coordinate, epoch table)`. Storing vertices, normals, UVs, colours, and instance transforms would:

- multiply the file size by millions,
- introduce a `float` round trip that silently breaks the seam guarantee of §5.1, and
- still be discarded the moment generation changes.

Instead `CHNK` records *which* chunks are resident and *which* influencing cells they used. Resume regenerates them; because regeneration is deterministic and the epoch table is restored first, the result is identical. Geometry is recoverable; identity is not, which is why identity is what gets stored.

### 4.7 Landmark records

```cpp
// Public/Generation/WoodPersistence.h  (proposed)
struct LandmarkRecord {
  int q, r;                    // hex cell
  Epoch epoch;                 // epoch the landmark was generated at
  DiscoveryType type;
  double PositionXM, PositionYM, PositionZM;   // metres, cell-local origin
  double YawDeg;
  double InnerRadiusM, OuterRadiusM;
  u32 PieceCount;
  u64 ContentDigest;           // §7.2
  bool Discovered;             // player has been close enough to notice it
  double DiscoveredObservationSeconds;
};
```

Stored in metres because it is generation-domain data. `ContentDigest` is what makes §7.2 checkable at load time.

### 4.8 Atomicity

1. Write `<Slot>.wood.tmp`, flush, close.
2. `Move` to `<Slot>.wood` (rename within the same directory is atomic on NTFS).
3. Only then compact the journal.

A crash between 2 and 3 leaves a valid snapshot plus a journal that repeats events already in the snapshot. Records are idempotent by construction (`FORGET` sets an absolute epoch, not `epoch += 1`; `JOB_CLOSE` is a no-op for a job already closed), so replay is safe.

## 5. Resume: same seam, same landmark

### 5.1 Why seams cannot appear

`WoodGeneration.cpp` builds a chunk grid with shared edge vertices (`row*(n+1)+col`, stride `n+1`), and `Tests/GenerationTests.cpp` already asserts that the last column of chunk `(0,0)` equals the first column of `(1,0)` in x, y, **and z**. A seam therefore appears only if two neighbouring chunks were generated against *different world state*. There are exactly three ways that can happen, and each is closed:

| Cause | Closure |
| --- | --- |
| One side regenerated after a resume with a different epoch table | §4.4 `CELL` is restored before any generation is dispatched |
| A cell was forgotten while a neighbour chunk was still resident or queued | §3 step 3 / §5.3 |
| A job captured a stale epoch snapshot | §6: `JOB_OPEN` stores the snapshot and the worker receives it |

### 5.2 Resume order

Strict order, all on the game thread, before the first `Stream()` call:

1. Read and validate the header; reject on magic/version/CRC failure.
2. Load `CELL`. The epoch table is now complete for every cell the player has ever forgotten.
3. Load `WRLD`, `PLAY`. Rebuild the `wood::World` snapshot with the restored config.
4. Replay the journal in sequence order against `CELL`, `CHNK`, and `LMARK`.
5. Verify `LMARK` digests (§7.2). A mismatch refuses the load.
6. **Discard all in-memory jobs.** There is no attempt to resume a future.
7. Re-dispatch the journalled pending jobs, then run normal `plan()`/`Stream()` as usual.

Step 6 deserves its own note: `TFuture` cannot be serialized, and the work is pure. Re-running a job from its journalled snapshot is not a retry, it is the same computation. So an interrupted generation task costs time, never correctness.

### 5.3 The no-seam forgetting rule

A hex cell may be forgotten only when **all** of the following hold:

1. no resident chunk within `retainRadius` overlaps the cell's 19-cell influence set;
2. no open `JOB_OPEN` job in the journal overlaps that influence set;
3. the cell's centre is outside the visibility horizon;
4. the journal `FORGET` record is flushed (next section's ordering).

Failing any of these defers the forget to a later frame. The deferral is bounded: as the player keeps moving, the window empties and the cell is forgotten then. Under normal travel the player never sees the deferral. Under a teleport it may briefly retain more than the minimum — retaining too much is a memory cost, retaining too little is a visible tear, and the asymmetry justifies the choice.

## 6. Pending generation jobs

### 6.1 Journal record

`JOB_OPEN` payload:

| Field | Type | Meaning |
| --- | --- | --- |
| `jobId` | `u64` | Monotonic within the journal |
| `chunkX`, `chunkY` | `int32` | Chunk coordinate |
| `detail` | `u8` | 0 = terrain-only (`includeFeatures=false`), 1 = full |
| `influenceCount` | `u8` | Always ≤ 19 |
| `influence[]` | `(int32 q, int32 r, u32 epoch)` | The 5×5 hex neighbourhood the worker will consult, with the epoch each cell has *right now* |

`JOB_CLOSE` payload is just `jobId`.

### 6.2 Why the influence snapshot, and not a lookup at dispatch time

`WoodGenerateChunk` walks the 5×5 hex kernel around the chunk's warped owner and calls `describe()` on each cell. If it looked epochs up at execution time, a `FORGET` landing between dispatch and execution would change one cell's climate mid-job and produce a chunk whose interior disagrees with both its neighbours — a seam that no resume test would catch, because it happens live.

Passing the snapshot into the worker makes the job a function of its own record. The worker already receives a `const wood::World Snapshot` copy for exactly this reason; the epoch snapshot rides alongside it.

The snapshot is bounded: 19 cells × 12 bytes ≈ 228 bytes per job, at most `maxConcurrentJobs` (2) open at a time.

### 6.3 Lifecycle

```
plan() → needed[]
  for each needed chunk, while Jobs.Num() < maxConcurrentJobs:
     build influence snapshot from the current CELL table
     append JOB_OPEN (jobId, chunk, detail, snapshot); flush
     Jobs.Add(Key, Async(ThreadPool, [snapshot]{ return WoodPrepareChunk(...); }))
  per frame:
     collect IsReady() jobs; realize at most one per tick
     append JOB_CLOSE (jobId) — may be batched, no flush required
```

`plan()` already excludes chunks that are loaded or in flight, so `availableJobs` accounting stays as-is. The journal is written for bookkeeping and resume, not for scheduling; scheduling still reads live `Runtime->Jobs`.

### 6.4 Resume of pending jobs

After §5.2 step 6, every journalled `JOB_OPEN` without a matching `JOB_CLOSE` is re-dispatched with **its own stored snapshot**, not with the current `CELL` table. A job therefore reproduces its original output even if some neighbouring cell has since been forgotten. It is realized normally if still inside `retainRadius`, and dropped (with a `JOB_CLOSE`) if the player has moved past it — which is also the correct outcome, because §5.3 guarantees no cell in its influence set was forgotten while it was open.

A `JOB_CLOSE` in the journal for a job whose chunk is not resident means the chunk was realized and then forgotten; both are consistent states and neither needs repair.

## 7. Landmark identity across resume

### 7.1 The requirement

"An interrupted generation task must not create a different seam or replace a recognizable landmark on resume." Two halves:

- **Retained landmarks** must come back as themselves — same type, same position, same yaw, same pieces.
- **Forgotten landmarks** must *not* come back as themselves — §2.3 already re-rolls them, and the ledger is what makes that stick.

### 7.2 The check

`ContentDigest` is a 64-bit FNV-1a over, in order: `type` as `u32`, `PositionXM/YM/ZM` reinterpreted as `u64` bit patterns, `YawDeg` as `u64` bits, and each piece's `(name, mesh, position, yaw, pitch, roll, scale)` in plan order with the same encoding. Bits, not rounded decimals — the plan is deterministic, so an exact comparison is available and anything else is a real discrepancy.

On resume, for every `LMARK` record whose cell is inside `retainRadius`, `planDiscovery` is re-run with the recorded `(seed, q, r, epoch)` and the digest recomputed. Outcomes:

| Result | Action |
| --- | --- |
| Match | Cell is retained as-is. The landmark cannot move. |
| Cell outside `retainRadius` | No check needed; the cell will be regenerated from its own epoch later |
| Mismatch | **Refuse the load** with a message naming the cell, epoch, and both digests |

Refusing is the right response. A mismatch means the generator changed between sessions, the file was tampered with, or a write was lost. Silently placing a different tor where the player's remembered tor stood is exactly the failure §7 forbids, and it is also the failure that would be hardest to diagnose later. The player can recover by starting a new journey; the alternative is a world that lies about its own landmarks.

Discovered-but-not-retained landmarks are kept in `LMARK` with `Discovered=true` even after their chunk is dropped, so the album-adjacent record of "places you have seen" survives world retention. That record is not geometry and does not resurrect the region.

## 8. Layering

```
Public/Generation/WoodPersistence.h      // records, section tags, engine-free
Private/Generation/WoodPersistence.cpp   // encode/decode, CRC, atomic rename
Public/Generation/WoodSave.h             // SaveGame/LoadGame orchestration (engine types)
Private/WoodSave.cpp                     // file paths, snapshot + journal, section fill
Private/Tests/WoodResumeTests.cpp        // automation test
Tests/PersistenceTests.cpp               // engine-free, run by Tools/Test-Persistence.ps1
```

`WoodPersistence.cpp` includes only `<cstdint>`, `<cstring>`, `<vector>`, `<string>`, `<stdexcept>`, and the generation headers — no `CoreMinimal.h`, no `Async.h`. That keeps it under the Zig and MSVC `/std:c++17 /W4 /WX` toolchain already used by `Tools/Test-Core.ps1` and `Tools/Test-Hex.cmd`, matching how `WoodStreaming.cpp` is tested.

`wood::streaming` keeps its single responsibility — bounded scheduling, no generation, no asset access, no persistence. Persisting its inputs is a separate concern and does not change its contract.

## 9. Verification

### 9.1 Engine-free (`Tools/Test-Persistence.ps1`, Zig c++ and MSVC)

Mirroring `Tests/StreamingTests.cpp` style — `assert`, plain `main`, a closing `PASS:` line:

1. **Round trip.** Write a snapshot with all sections populated; read it back; every field equals what was written, doubles bit-exact.
2. **Epoch 0 identity is unchanged.** `regionIdentity(seed, q, r, 0) == hash(seed, q, r, 701)` for a set of `(seed, q, r)`; the existing `Tests/GenerationTests.cpp` expectations still hold with the epoch parameter defaulted to 0.
3. **Fresh identity is not seed-reachable.** `regionIdentity(s,q,r,1) != regionIdentity(s,q,r,0)`, and for 32 seeds × 64 cells there is no collision between epoch *n* and epoch *n+1*.
4. **Epoch changes the world, warp does not.** `sample()` differs across epochs at a cell centre; the warped `hex::owner()` map is identical for both epochs.
5. **Continuity across the epoch boundary.** Sample a line crossing from an epoch-1 cell into an epoch-0 cell at 0.5 m steps; maximum step in height stays under the same bound the existing seam test uses.
6. **Discovery allocation is re-rolled.** `hashCell(seed ^ mixEpoch(1), q, r) % 3 != 0` for a cell that was allocated at epoch 0 — chosen fixtures, plus a statistic over 10 000 cells showing a ~1/3 re-allocation rate.
7. **CRC and torn tail.** Flip one byte → the reader refuses. Append a truncated record → the reader drops exactly that record and applies the rest.
8. **Write-ahead ordering.** With the journal unwritten, the reader reports the cell as still retained; after a `FORGET` flush it reports the new epoch. Both are asserted, and the second is asserted *before* any eviction is allowed — the ordering of §3 step 5 is the property, not the code that implements it.
9. **No geometry in the file.** A snapshot with 81 retained chunks is under a fixed size bound; the file does not grow when `cells` or feature count grows.

### 9.2 Unreal (`Source/TheWood/Private/Tests/WoodResumeTests.cpp`)

Following `WoodInstanceRetentionTests.cpp`: snapshot vegetation by `FIntVector(RoundToInt(P*10))`, not by array index.

1. **Seam after resume.** Walk, save, reload, then re-walk the same route. Terrain heights at every visited vertex agree with the pre-save run to 1e-6.
2. **Vegetation after resume.** Instance snapshot before save equals after resume for every retained chunk.
3. **Same landmark.** Identify a discovery cell before save; after resume, type, position, yaw, and digest match.
4. **Pending job resume.** Force `maxConcurrentJobs=1` with 8 chunks needed, save mid-window, resume, and confirm the final resident set is identical to an uninterrupted run of the same route — this is the direct test of §5.1's third cause.
5. **Interruption.** Kill the process mid-window (task manager or a debug command), relaunch, load, and repeat test 4. This is the §11 "interruption" gate and the only test that exercises the torn-tail path in anger.
6. **Repeated forgetting.** Travel in four directions with `retainRadius = 4`, returning to origin each time; assert the origin cell's epoch increased and that no `LMARK` digest from a forgotten cell ever reappears.
7. **Irreversibility.** Walk far enough to forget cell A, walk back, and assert `regionIdentity` at A differs from the pre-forgetting value and that a reload (new process) still shows the new epoch. The second half is the part a session-only implementation would miss.
8. **Debug mode.** With `reproducibleSeedMode=true`, epoch stays 0 across forget and reload, and the same seed reproduces the same place.

### 9.3 Visual

Render before/after pairs at the same viewpoint and seed across a save/resume and across repeated forgetting, and check for creases at the epoch boundary, shifted ridgelines, doubled ruins, and any water discontinuity. §12's stance applies — the tests above prove the invariants, not that the result looks like a wood.

## 10. Open decisions

- **Ledger compaction.** §2.5 keeps the forget ledger exact. Radial compaction is possible and would bound memory, but it weakens §7 for cells outside the horizon. Needs a product decision, not an engineering one.
- **Visibility radius source.** §3 derives `visibleChunkRadius` from the light grid. Once real view distance is authored, this should come from the rendering settings instead, with the light grid following it.
- **Compression.** The section layout is designed for it (`sort by key`, `byteLength`, `flags`) but version 1 is uncompressed. Decide from measured file sizes before adding it.
- **Save frequency and quota.** Not designed here. `SAVE_BEGIN` exists so a future autosave can be journalled; the policy needs playtest evidence.
- **Multiple journeys per save.** One slot, one journey, one ledger. Whether a slot should hold several journeys with separate ledgers is unresolved.
- **Save during accelerated observation.** `observationSeconds` advances while seated and accelerated. It is stored as an absolute value, so resume restores the clock; whether time may be spent between saves is a rules question for §1, not a format question.

## 11. Explicit non-goals

- The occluded irreversible passage, the fixed parking lot, and the entrance forest. Milestone 3 (§11) depends on this design but is not part of it. §2 gives it the mechanism it needs — a threshold crossing is a `FORGET` on the return side.
- Ruin architectural families, weather, wildlife. Milestones 4 and 5.
- Photograph persistence. §7 keeps it independent of world retention; the format stores no image data.
- Reclaiming a forgotten region. §7 forbids it and this design implements it rather than working around it.