# Save, Resume, and Irreversible Forgetting — Design

Status: design only. This document adds no source changes. It specifies the on-disk
save format, the fresh-identity scheme for forgotten cells, the pending-generation
journal, and the seam-free resume guarantee required by Milestone 2 of
[Specification.md](../../Specification.md) §11 and §7.

Date: 2026-10-06. Companion to [2026-10-06-ruins-and-discoveries-design.md](2026-10-06-ruins-and-discoveries-design.md),
which owns landmark grammar but assumes a world seed that reproduces forever. This
document is what makes that assumption stop being true.

## 1. Scope

Milestone 2 requires four things this design delivers:

1. Generate ahead asynchronously, retaining nearby geography.
2. Discard distant regions beyond the backtracking buffer, with **fresh identities**.
3. Save retained state and pending identities.
4. Resume an interrupted generation task without creating a different seam.

Out of scope here, named so nobody assumes otherwise: the occluded passage and the
fixed trailhead (Milestone 3), photo album browsing UI, weather, wildlife, and any
change to terrain or landmark grammar itself. Photographs keep persisting
independently in `Saved/Photos`; this save format only records that they exist.

## 2. What the code does today (evidence)

Facts below are read from source, with citations. The design is built on them, not on
the prose summaries in `Docs/Status.md`, which are deliberately vaguer.

| Fact | Location |
| --- | --- |
| Chunks are 128 m; desired radius 4, retain radius 5 by default, max 2 concurrent jobs | `Source/TheWood/Public/Generation/WoodStreaming.h:11-16` |
| All randomness derives from `hash(seed, x, y, salt)` | `Source/TheWood/Private/Generation/WoodGeneration.cpp:12-16` |
| A region's identity is `hash(seed, gx, gy, 701)` | `WoodGeneration.cpp:30` |
| Region lattice is axial hex cells of radius 950 m; `extent` is the 1900 m influence diameter | `WoodGeneration.cpp:32`, `WoodHex.h:6` |
| Six cell coordinates have hard-coded biome families, and `(0,0)` is forced Temperate Forest | `WoodGeneration.cpp:33-40` |
| Chunk vertices are evaluated from absolute metre coordinates, never from neighbours | `WoodGeneration.cpp:151-160` |
| A chunk queries cells within 2 hex rings of the warped centre's owner cell | `WoodGeneration.cpp:172-176` |
| Discovery allocation is `hashCell(seed,q,r) % 3 == 0` | `WoodDiscovery.cpp:504-507` |
| Discovery grammar RNG is seeded from the **world seed** (`seed ^ 0x5D0EU` etc.), not from the cell | `WoodDiscovery.cpp:83, 200, 321, 402` |
| `(0,0)` and `(1,1)` have hard-coded guaranteed landmarks | `WoodDiscovery.cpp:477-487` |
| Jobs are `TMap<FIntPoint,TFuture<FWoodPreparedChunk>>` — futures, not serialisable state | `Source/TheWood/Private/WoodRuntime.h:9` |
| A job is dispatched with a full copy of the `wood::World` snapshot | `WoodWorldStreaming.cpp:77-79` |
| Removal is purely `abs(dx)>ChunkRadius+2 \|\| abs(dy)>ChunkRadius+2`; no visibility term | `WoodWorldStreaming.cpp:64` |
| The adapter converts cm→m exactly once per frame, `Position.X/100` | `WoodWorldStreaming.cpp:74`, `WoodWorld.cpp:118-125` |
| `Observation::sit/accelerate/advance/rate` enforce the 20× and standing rules | `WoodGeneration.cpp:290-296` |
| `RestartPlayer` forces `ExplorerStart()` unconditionally | `WoodGameMode.cpp:14-19` |

Three consequences drive the whole design:

- **Everything is a pure function of `(worldSeed, q, r, absolute metres)`.** Nothing
  depends on generation order or on task completion order, which is the property
  §9 of the Specification already relies on for shared edges.
- **Therefore identity is the only thing that is not re-derivable.** If a forgotten
  cell can be regenerated from the same seed, it will be — automatically, correctly,
  and irreversibly wrong. Fresh identity must be a *value that is not a function of
  the seed and coordinates alone*.
- **Futures cannot be saved.** So the journal must record intent, not partial output.

## 3. Terminology

| Term | Meaning | Unit |
| --- | --- | --- |
| World seed | `wood::Settings::seed`, from `AWoodWorld::Seed` / `-WoodSeed=` | u32 |
| Cell | axial hex cell `(q, r)` on the 950 m lattice | integers |
| Chunk | 128 m tile `(x, y)`, covers `[x·128,(x+1)·128) × [y·128,(y+1)·128)` | integers |
| Epoch | 0 for a cell never forgotten in this journey; ≥1 after each later visit | u32 |
| Cell seed | the u32 actually handed to `hash()` and `hashCell()` | u32 |
| Forget nonce | per-journey 64-bit value from the platform RNG; 0 until the first forget | u64 |
| Forget counter | highest epoch issued in this journey; monotonically increasing | u32 |
| Live cell | a cell with epoch > 0 that is still retained or pending | — |
| Retired cell | a cell whose epoch was superseded and whose chunks are all gone | — |
| Tombstone | audit record of a retired cell, in the retired ledger | — |

The identity unit is the **cell**, not the chunk: chunk generation consults up to 25
cells (`WoodGeneration.cpp:172-176`), and `hashCell` is keyed on `(q, r)`. Chunk
coordinates appear in the save only as retention bookkeeping.

## 4. Fresh identity for a forgotten region

### 4.1 The requirement, stated precisely

A forgotten cell must satisfy: given the world seed and the cell coordinates, the
generator **cannot** reproduce the identity it had while forgotten, and it cannot
reproduce any identity it has ever had in this journey. Reproducing the *first* visit
(epoch 0) is desirable and must be preserved: Specification §7 requires
"reproducible seeds for debugging".

Both requirements are satisfied by giving each cell an epoch and mixing two
non-coordinate values into every epoch ≥ 1.

### 4.2 `wood::Identities`

New engine-independent value type, proposed in
`Source/TheWood/Public/Generation/WoodSave.h`:

```cpp
// Cell identity resolution. Epoch 0 uses the world seed verbatim, so a journey
// with no forgetting generates byte-for-byte what it generates today.
struct Identities {
 struct Cell { int q=0, r=0; std::uint32_t epoch=0; };
 std::uint64_t nonce=0;          // per-journey; 0 means nothing has been forgotten yet
 std::uint32_t counter=0;        // highest epoch issued
 std::vector<Cell> live;          // epoch != 0 cells still retained or pending, sorted by (q,r)
 std::vector<Cell> retired;       // audit ledger, oldest first, capped
 std::uint32_t epochFor(int q, int r) const;   // 0 when unlisted
 std::uint32_t seedFor(int q, int r) const;    // the u32 handed to hash() and hashCell()
 void retire(int q, int r, double x, double y, double z); // metres
};
std::uint32_t cellSeed(std::uint32_t world, std::uint64_t nonce, int q, int r,
                       std::uint32_t epoch);
```

`World` gains `World(Settings settings, Identities identities)` and keeps
`explicit World(Settings settings)` as a delegate with an empty table. Because
`WoodWorldStreaming.cpp:77` already snapshots the whole `wood::World` into each job,
the identity table rides along with no change to the job plumbing.

### 4.3 The derivation

```
cellSeed(world, nonce, q, r, epoch) =
    epoch == 0 ? world
               : fold32(mix64( (u64)world        << 32 | (u64)world
                             ^ 0x5F0A9E377F4A7C15ull * (epoch + 1)
                             ^ nonce
                             ^ (u64)(u32)q * 0x9E3779B97F4A7C15ull
                             ^ (u64)(u32)r * 0xC2B2AE3D27D4EB4Full ))
```

`mix64` is the 64-bit widening of the existing `hash` body
(`WoodGeneration.cpp:12-16`): xor-shift, multiply by the same two constants, final
xor-shift. `fold32` is `h ^ (h >> 32)`. No new constant family is introduced, and the
existing per-layer salts (701 for identity, 704 for family, 1–2 for noise) are reused
underneath, so cell seeds change *all* layers together — a forgotten cell gets new
terrain, new climate, new flora, and a new landmark class, not a recoloured version of
itself.

Two properties are asserted, not hoped for:

- `cellSeed(...) != world` for every `epoch ≥ 1`. Retry with the epoch term
  incremented on the (astronomically unlikely) collision; a unit test covers a large
  sample.
- `cellSeed(world, nonceA, ...)` differs from `cellSeed(world, nonceB, ...)` for
  distinct nonces. This is the anti-recovery property: the nonce is not in the seed.

### 4.4 Lifecycle of a cell

1. **First visit.** Cell has no tombstone and no live record. `epoch = 0`,
   `cellSeed = world`. The cell generates exactly as it does today — the reviewed
   blend around `(0,0)`, `(1,0)`, `(1,1)`, `(0,-1)` (`Docs/Status.md`) is unchanged.
2. **Retirement.** When the last chunk depending on a cell leaves the retained set,
   `retire()` runs: it appends `{q, r, epoch}` to `retired`, assigns
   `epoch = ++counter`, writes `{q, r, epoch}` into `live`, and marks the save dirty.
3. **Revisit.** `epochFor` finds the live record, `seedFor` returns the retired-then-
   reissued derived seed, and the cell is generated with a fresh identity. Walking
   back to the coordinates does **not** bring back the old place, because the old
   place's seed was `world` (epoch 0) or an earlier `counter`-derived value, and
   neither is reachable from the coordinates any more.
4. **New journey, same seed.** `nonce` is drawn fresh and `counter` resets, so a
   debug reproduction of a no-forgetting journey is still exact, and a replaying
   player cannot walk a previously forgotten route at all.

`counter` is global and never reused, so two different cells in one journey can never
share an epoch value, and no epoch is ever re-issued. That is what makes the ledger a
diagnostic rather than a correctness requirement — it is capped at 1024 entries
(FIFO, ~32 KB) without affecting correctness.

### 4.5 Retirement must be exact, not radius-based

A chunk within `retainRadius` (6 chunks = 768 m) still consults cells up to two hex
rings away, i.e. up to ~3290 m from the chunk centre (`hex::radius = 950`,
`WoodHex.h:6`). Retiring by a distance rule would therefore retire live cells and
resurrect seams. Retirement is instead derived from the plan itself:

- `Plan.removed` (`WoodStreaming.cpp:33`) is the set of chunks being discarded.
- `cellsOf(chunk)` = `{owner(warp(centre + (180,180)))} ∪ its 2-ring neighbourhood`,
  computed with `hex::owner`/`hex::warp` only — no noise evaluation, cheap enough to
  run for at most 169 removed chunks per streaming step.
- Let `Needed = cellsOf(retained ∪ pending ∪ removed)` and
  `Alive = cellsOf(retained ∪ pending)`. Retire `Needed \ Alive` that is not already
  retired.

This is exact, order-independent, and unit-testable without an engine.

### 4.6 Starter overrides must be gated

`WoodGeneration.cpp:33-40` pins six cell coordinates to fixed biome families and
`WoodDiscovery.cpp:477-487` guarantees landmarks at `(0,0)` and `(1,1)`, all keyed on
**coordinates alone**. Under forgetting these would resurrect the exact home
landscape every time the origin region was re-entered, violating §4.3. Both sets must
become conditional on a persisted `starterArmed` flag (see §5.2) and stop applying
once the flag is cleared. This is the single highest-risk change in the design,
because it touches the exact coordinates used as review reference points; it is
called out again in §11.

## 5. On-disk save format

### 5.1 Two layers, one conversion site

| Layer | Files | Contents |
| --- | --- | --- |
| Engine-independent core | `Public/Generation/WoodSave.h`, `Private/Generation/WoodSave.cpp`, `Tests/SaveTests.cpp` | `encode` / `decode` / `describe` over a byte vector, all values in **metres** |
| Unreal adapter | `Private/WoodWorldSave.cpp` (new), `USaveGame` subclass | slot I/O, actor transform, palette handle, save triggers |

The core is deliberately free of `FArchive`, matching the existing split: the
engine-independent sources compile under `zig c++` and MSVC `/std:c++17 /W4 /WX`
(`Tools/Test-Core.ps1`, `Tools/Test-Streaming.cmd`) with no Unreal headers at all.
The adapter converts **exactly once per field**, at the boundary, using the same
`/100` and `*100` pattern already used in `WoodWorldStreaming.cpp:74` and
`WoodWorld.cpp:118`.

`USaveGame` carries the engine-level mirror (pawn transform in cm, seed, observation)
so the engine's own load path works, but the payload is authoritative: `ReadSave`
rebuilds the `wood::` state from the payload and then overwrites the mirrored UE
fields from it, so a stale or hand-edited mirror cannot reintroduce a different seam.

### 5.2 Container

Little-endian, no implicit padding, every field an explicit width. Written as
`Saved/SaveGames/TheWood.slot0.woodsave`.

**Header — 48 bytes**

| Offset | Size | Field |
| --- | --- | --- |
| 0 | 4 | magic `0x57 0x53 0x41 0x56` (`WSAV`) |
| 4 | 2 | `formatVersion` = 1 |
| 6 | 2 | `sectionCount` |
| 8 | 4 | `worldSeed` (u32) |
| 12 | 8 | `writtenAtUnixSeconds` (i64) |
| 20 | 8 | `forgetNonce` (u64, non-zero once anything is forgotten) |
| 28 | 4 | `forgetCounter` (u32) |
| 32 | 4 | `flags` (u32; bit 0 `starterArmed`, bits 1–31 reserved and must be 0) |
| 36 | 8 | `sequence` (u64, monotonic save counter, for diagnostics) |
| 44 | 4 | `headerCrc32` over bytes `[0,44)` |

**Sections**, each `{ u32 tag, u32 bytes, payload[bytes], u32 crc32 }`, emitted in
ascending tag order:

| Tag | Section | Payload |
| --- | --- | --- |
| `ALBM` | Album | `u32 count`, then per entry `u16 byteLength` + UTF-8 relative path |
| `CELL` | Live cell identities | `u32 count`, then `count × { i32 q, i32 r, u32 epoch, u32 reserved }` sorted by `(q,r)` |
| `JOBR` | Pending job journal | `u32 count`, then `count × JobRecord` (§6) |
| `META` | Player and window | see below |
| `OBSV` | Observation | `u8 seated, u8 accelerated, f64 seconds` |
| `TMBN` | Retired ledger | `u32 count`, then `count × { i32 q, i32 r, u32 epoch, f64 x, f64 y, f64 z }` |

**`META` payload**

| Field | Type | Unit |
| --- | --- | --- |
| `playerX, playerY, playerZ` | 3 × f64 | metres |
| `playerYaw, playerPitch` | 2 × f64 | radians |
| `chunkSize` | f64 | metres (128) |
| `cells` | i32 | grid resolution (64) |
| `chunkRadius`, `desiredRadius`, `retainRadius` | 3 × i32 | chunks |
| `maxConcurrentJobs` | i32 | jobs (2) |
| `seedMirror` | u32 | must equal header `worldSeed`, else reject |

The metre/centimetre boundary is exactly the existing one: the payload stores metres
because `wood::` is metres (`WoodGeneration.h:6`) and the adapter is the only place
that knows Unreal is centimetres.

### 5.3 Size

Typical steady state: `META` 72 B, `OBSV` 10 B, `CELL` 12–48 B, `JOBR` ≤ 2 records,
`TMBN` ≤ 32 KB. **No geometry is stored.** Retained terrain is regenerated from
retained identities, which is sound precisely because chunk geometry is a pure
function of those identities (§2). Storing geometry would add megabytes and buy
nothing.

### 5.4 Write protocol

1. Serialise fully in memory on the game thread. Validation throws
   `std::invalid_argument` for out-of-range fields, mirroring `plan()`
   (`WoodStreaming.cpp:18-21`).
2. Write `<slot>.woodsave.tmp` in the target directory, `FlushFile`, close.
3. Copy the current `<slot>.woodsave` to `<slot>.woodsave.bak` (keep last known good).
4. `IFileManager::Move` the temporary onto `<slot>.woodsave` — same volume, atomic
   rename. A crash at any point leaves either the previous file or the new one.

Triggers: a new chunk centre at most once per 2 s, on quit, on the occluded passage
crossing (Milestone 3), and on any identity retirement (§4.4 step 2), which is the
one case where a stale save actively lies about the world.

### 5.5 Load protocol

1. Try `<slot>.woodsave`; on any failure try `<slot>.woodsave.bak`; if both fail,
   log the file, the failing tag, and the offset, then start a **new** journey. A
   partially decoded save is never applied.
2. `decode` returns `bool` plus an error string; it does not throw. Torn tails are an
   expected outcome of crash-during-write, not an exceptional condition.
3. Unknown section tags are skipped with a warning (forward compatibility). A section
   whose declared length overruns the buffer, or whose CRC mismatches, ends the load
   at that point — the header has already been validated, so the identity state is at
   worst one checkpoint old, never corrupt.
4. Validate: `formatVersion` known; `worldSeed` matches `-WoodSeed=` when both are
   present (mismatch logs a warning and honours the save; `-WoodForceLoad` overrides);
   `forgetNonce != 0` implies `forgetCounter != 0`; all coordinates within
   `validatePoint`'s 1e6 m bound (`WoodGeneration.cpp:23-26`); all radii within the
   authoring limits in `WoodStreaming.h:13`.
5. Reject and fall through to `.bak` if `seedMirror != worldSeed`.

## 6. Pending generation journal

### 6.1 Journal intent, never output

`TFuture<FWoodPreparedChunk>` cannot be serialised and its partial work is worthless
without the identity context that produced it. So the journal records the identity
context of each in-flight chunk, not its geometry. Each record:

| Field | Type | Meaning |
| --- | --- | --- |
| `token` | u64 | monotonic job id within the journey; makes duplicate records detectable |
| `chunkX, chunkY` | i32 × 2 | chunk coordinate |
| `stage` | u8 | 0 Queued, 1 Running, 2 Ready, 3 Realized |
| `detail` | u8 | 0 = terrain-only (`WoodPreparedChunk.h:12` `Details=false`), 1 = full placement |
| `reserved` | u16 | 0 |
| `cellCount` | u32 | number of cell records that follow |
| cells | `count × { i32 q, i32 r, u32 epoch }` | every cell the job may consult whose epoch is ≠ 0 |

Cells with epoch 0 are omitted: they are implied by the world seed, and writing them
would triple the size of every job record for no information. In practice a job
touches 0–2 non-zero-epoch cells, so a record is 20–44 bytes.

### 6.2 Dispatch order (the durability rule)

1. Adapter picks a chunk from `Plan.needed` and honours `Plan.availableJobs`
   (`WoodStreaming.cpp:29`).
2. Compute `cellsOf(chunk)`; for each cell resolve `epochFor`, allocating a new epoch
   if the cell is present in the retired ledger.
3. **Append the `JOBR` record with `stage = Queued` and flush to disk before the
   future exists.** This is the only synchronous disk write on the streaming path.
4. Dispatch `Async(EAsyncExecution::ThreadPool, ...)` with a `wood::World` snapshot
   built from the resolved table, exactly as `WoodWorldStreaming.cpp:77-79` does today.
5. `IsReady()` → mark `stage = Ready` in memory.
6. `Realize()` → drop the record, mark the save dirty.

Concurrency: outstanding jobs are `saved pending ∪ live pending`, capped at
`Settings::maxConcurrentJobs`. Resumed jobs are dispatched **before** `plan()` may
schedule anything new, so the cap is honoured across the seam rather than doubled.

### 6.3 Recovery

On load, for each `JOBR` record in ascending `token`:

- Chunk already in the retained table → drop the record (it is already realised).
- `detail == 0` → drop the record. Terrain-only work is not journalled; the chunk
  re-enters the normal `plan()` path and gets a detailed job when it is scheduled.
  `EnsureTerrainAround` (`WoodWorldStreaming.cpp:19-22`) already guards the ground
  under the player synchronously, so nothing is left uncovered.
- Otherwise → re-dispatch with the recorded cell identities.

### 6.4 Why this cannot create a seam

A pending chunk is re-derived, not resumed, and that is sound because:

- Chunk vertices are evaluated from absolute metre coordinates
  (`WoodGeneration.cpp:151-160`). No neighbour read, so generation order is
  irrelevant — this is the shared-edge property §9 of the Specification already
  depends on.
- Every cell the job consults is reconstructed from `CELL` + `JOBR`, so the derived
  seeds are bit-identical to those the original job ran under.
- Water ribbons are built from `Generator.streamX/streamHalfWidth` at the same
  absolute Y (`WoodWorldStreaming.cpp:29-36`), so the water surface on a shared chunk
  edge is a function of position alone.
- Lighting, fog and sky are rebuilt from the saved position and the restored
  `Observation.seconds`, so the first frame after resume matches the last frame
  before.

Claim L5 in §7.3 tests exactly this: generate a chunk directly, then generate the
same chunk after a save/load round trip, and compare vertex `z` for **exact double
equality** plus identical triangles, features, and placements. Any mismatch means the
identity table was not reconstructed correctly. This is the acceptance gate, because
it is the only failure that would be both visible and subtle.

### 6.5 Honest limit on the journal

Step 3 costs a file flush on the dispatch path, at most twice per streaming window
and under 4 KB. If packaged-build profiling shows that flush is visible, the
documented fallback is to defer the flush to the end of the streaming step. That
widens the loss window by at most one dispatch: the identity table is still written
by the following checkpoint, but an in-flight job whose identity was *just* retired
could be lost. It weakens L3 and leaves L1, L2, L4 intact. It is a measured
decision, not a default, and it is recorded here so nobody adopts it silently.

## 7. Resume and the same landmark

### 7.1 What a landmark depends on

`planDiscovery(seed, q, r, cellCentre, cellClimate, heightFn, streamXFn, streamHWFn)`
(`WoodDiscovery.h:79-88`) is a pure function of `(seed, q, r, centre, climate, and the
terrain/hydrology callbacks)`. Its outputs — allocation (`%3`), type selection,
reservation radii, piece transforms — all inherit determinism from the cell seed.
Consequently **a landmark is stable exactly as long as its cell seed is unchanged**,
which reduces the whole question to: which cells are still under their saved seed at
resume?

### 7.2 Resume sequence

In `AWoodWorld::BeginPlay`, after the existing palette and profile bootstrap:

1. Load and validate (§5.5). On failure, fall through to the normal new-journey path.
2. Build `wood::Identities` from header + `CELL` + `TMBN`.
3. `Generator = wood::World({worldSeed, chunkSize, cells}, Identities)`.
4. Restore observation through `sit()` / `accelerate()` and a validated `seconds`
   assignment — never raw field writes, so the standing-clears-acceleration rule
   (`WoodGeneration.cpp:290-291`) and the `advance()` argument checks cannot be
   bypassed by a corrupt save. `GlobalTimeDilation` is re-applied as in
   `WoodWorld.cpp:150-156`.
5. Restore the player from `META` in metres and place the pawn in cm. `RestartPlayer`
   (`WoodGameMode.cpp:14-19`) must prefer the saved transform when a save is present;
   that switch is the Milestone 3 dependency this design unblocks.
6. Skip the unconditional 3×3 warm block (`WoodWorld.cpp:88-89`) when resuming — its
   purpose is to make the opening trailhead instant on a new journey, and on resume it
   would generate chunks the player may already have moved away from.
7. Re-dispatch `JOBR` records (§6.3).
8. Call `Stream(savedPositionMetres)` with the saved loaded and pending sets, so
   `plan()` sees the true state and immediately requests only what is missing.

### 7.3 Guarantees, as testable claims

| # | Claim | Test |
| --- | --- | --- |
| L1 | Every chunk retained at save time is bit-identical after resume | Compare `WoodPrepareChunk` output field-by-field across a save/load round trip |
| L2 | A landmark the player can currently see is never forgotten, so a silhouette being walked toward is never swapped | Frustum-expanded chunk set asserted disjoint from `Plan.removed` |
| L3 | A landmark inside a journalled pending cell resolves to the same type, yaw, pieces, and reservation after resume | Compare `planDiscovery` output per `JOBR` record |
| L4 | A retired cell's current identity is not derivable from `(worldSeed, q, r)` | For every tombstone, `cellSeed(world, 0, ...)` and `cellSeed(world, probeNonce, ...)` both differ from the recorded seed |
| L5 | A re-derived pending chunk equals the chunk that was in flight | Exact double equality on vertex `z`, identical triangles/features/placements |

L2 needs one change to the engine-independent core that does not exist yet.
`WoodWorldStreaming.cpp:64` retains on chunk distance alone, with no visibility term,
while Specification §7 requires removal only *beyond both visibility and the
backtracking buffer*. Proposed addition, keeping the pure-function style:

```cpp
// Source/TheWood/Public/Generation/WoodStreaming.h
Plan plan(double playerX,double playerY,const std::vector<Coord>& loaded,
 const std::vector<Coord>& pending,const std::vector<Coord>& visible,Settings settings={});
```

`visible` is the camera frustum's chunk set, expanded by a margin of two chunks and
snapped to chunk coordinates, computed by the adapter (which owns the camera) and
passed in as data — the core stays engine-free, exactly as its header comment
promises. `removed` excludes any coordinate in `visible`. The existing four-argument
`plan` remains as a delegate passing an empty `visible`, so `Tests/StreamingTests.cpp`
keeps compiling and every existing assertion keeps its meaning. The retain radius of
6 chunks (768 m) already exceeds the fog-limited sightline at density 0.014–0.018
(`WoodWorld.cpp`), so this term closes a correctness gap rather than changing current
behaviour noticeably.

### 7.4 A worked interruption

Player at chunk `(3,-1)`, retain radius 6, two jobs in flight for chunks `(8,0)` and
`(9,1)`. Cell `(1,1)` — the guaranteed `RidgeTor` — was retired two hours ago and
revisited, so it is live with epoch 3.

1. Streaming step retires chunks `(−4,−1)` … `(−1,2)`; `cellsOf` over the removed set
   yields cells around `(-1,1)`; none is needed by retained or pending chunks, so they
   are retired: `epoch = ++counter`, tombstone appended, `CELL` updated, save marked
   dirty and flushed immediately (§5.4 — retirement is the one event where a stale save
   actively lies).
2. Save is written. `JOBR` holds two records; the `(9,1)` record carries cell `(1,1)`
   at epoch 3 because that chunk's 2-ring neighbourhood reaches it.
3. The process is killed before `(9,1)`'s future resolves.
4. On load: `nonce` and `counter` come from the header, `(1,1)` at epoch 3 comes from
   `CELL` and from the job record, and `(9,1)` is re-dispatched with a `wood::World`
   carrying epoch 3.
5. The `RidgeTor` in cell `(1,1)` — and the ground it stands on — are the same rocks,
   the same yaw, the same reservation, and the same tree exclusion. No seam, no second
   mountain.
6. `(-1,1)` and its neighbours are still fresh places. Walking back does not restore
   them.

## 8. Implementation surface

Additive, and deliberately small:

| File | Change |
| --- | --- |
| `Public/Generation/WoodSave.h` (new) | `Identities`, `Cell`, `SaveData`, `encode`/`decode`/`describe`, `cellSeed` |
| `Private/Generation/WoodSave.cpp` (new) | CRC32, LE writers/readers, validation, `describe` text dump |
| `Public/Generation/WoodGeneration.h` | `World(Settings, Identities)` overload; `Observation::restore` |
| `Private/Generation/WoodGeneration.cpp` | pass resolved cell seeds to `hash`/`hashCell`; gate starter overrides on `starterArmed` |
| `Public/Generation/WoodStreaming.h` | `visible` overload of `plan`; `cellsOf` declaration |
| `Private/Generation/WoodStreaming.cpp` | `cellsOf`; `removed` honours `visible` |
| `Private/WoodWorld.h/.cpp` | `WriteSave`/`ReadSave`, retirement hook in `Stream` |
| `Private/WoodWorldSave.cpp` (new) | slot I/O, atomic replace, cm↔m at the single boundary |
| `Private/WoodGameMode.cpp` | prefer the saved transform over `ExplorerStart()` |
| `Private/Generation/WoodDiscovery.cpp` | pass the resolved cell seed; gate `(0,0)`/`(1,1)` guarantees on `starterArmed` |

`hash()` and `hashCell()` keep their signatures. Only the *value* passed to them
changes. That is the whole reason the scheme is small.

## 9. Tests

Engine-independent, matching the `assert`-and-`PASS`-line style of
`Tests/StreamingTests.cpp`, built by a `Tools/Test-Save.cmd` cloned from
`Tools/Test-Streaming.cmd` (`cl /std:c++17 /W4 /WX`, plus the zig path in
`Tools/Test-Core.ps1`):

- encode → decode round trip is byte-identical for canonical state (both `CELL` and
  `TMBN` sorted, so equal state has one encoding);
- epoch 0 produces `world` unchanged, for `(0,0)`, `(1,1)` and negative coordinates;
- `cellSeed` never equals `world` for `epoch ≥ 1` across a large sample;
- distinct nonces give distinct cell seeds (L4);
- torn-tail truncation: flip one byte in the last section, assert `decode` fails
  cleanly and returns the header it had already validated;
- unknown future tag is skipped, not fatal;
- `cellsOf` retirement: retire a synthetic plan and assert no cell needed by retained
  or pending chunks is retired;
- `plan` with a `visible` set never returns a visible coordinate in `removed` (L2).

Unreal, in `Private/Tests/WoodSaveRuntimeTests.cpp`, following
`WoodInstanceRetentionTests.cpp`'s snapshot-and-compare pattern and its
`FPlatformProcess::Sleep` yield for real worker jobs:

- snapshot prepared chunks for the retained ring, save, tear down, reload, compare
  field-by-field (L1);
- save while two jobs are in flight, force-reload, assert the same landmark type, yaw,
  and piece count for each journalled cell (L3);
- walk far enough to retire a cell, save, reload, walk back, assert the landmark
  differs and the old one is gone (L4 end-to-end);
- exact double equality on vertex `z` for a chunk regenerated after resume (L5).

Nothing in this document has been executed; these are the tests that would establish
the claims.

## 10. Documentation corrections found while reading

- `Docs/Status.md` and the ruins design both say the regional lattice is 1,200 m.
  The code uses `hex::radius = 950` (`WoodHex.h:6`) with `extent = radius·2 = 1900`
  described as an influence *diameter* (`WoodGeneration.cpp:32`, `WoodGeneration.h:11`).
  The identity table is keyed on that lattice, so one of the two numbers has to
  become the source of truth before the save format is frozen.
- Specification §13 lists "save format" among unresolved decisions. This document
  proposes one; it needs human approval before implementation, and §5.2 version `1`
  should not be cut until it is approved.

## 11. Risks

| Risk | Mitigation |
| --- | --- |
| Gating the six hard-coded biome families and the two guaranteed landmarks changes the reviewed reference blend around the start | `starterArmed` persists in the save header, so milestone-2 saves are distinguishable from milestone-3 saves; clearing it is a separate, deliberate milestone-3 change |
| A synchronous flush on the dispatch path | Budget 2 writes per window under 4 KB; §6.5 documents the measured fallback and exactly which guarantee it weakens |
| Losing `forgetNonce` would let retired cells revert to epoch 0, i.e. bring the discarded place back | `nonce == 0` with `counter != 0` is a hard load rejection; both are in the header CRC |
| Journal size growth if the identity table ever becomes large | Cells with epoch 0 are never written; only cells a specific job can consult are recorded |
| A torn write after a retirement but before the flush | Retirement flushes immediately, ahead of ordinary checkpoints, precisely because it is the only state that is destructive if lost |
| Save growth tempts someone toward storing geometry | The format has no geometry section by design; §5.3 states why |

## 12. Open questions for the human

1. Approve the section list in §5.2, and 950 m versus 1,200 m in §10, before
   `formatVersion` is cut.
2. Should `AWoodWorld::Seed` widen from `int32` to `uint64` now? The world seed is
   stored as u32 here; the nonce already provides the unguessable component.
3. Is the retired ledger needed at all beyond diagnostics? It is capped at 1024 and
   could be dropped entirely if the per-cell epoch is trusted to be persisted.
4. Should `.bak` be a user-visible restore point, or an implementation detail?
5. Retention currently uses chunk distance only. Confirm that a frustum-derived
   `visible` set is the right visibility term, or whether fog-limited range is
   intended as the bound instead.
