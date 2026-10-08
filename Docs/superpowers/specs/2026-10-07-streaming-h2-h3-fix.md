# Streaming H2 / H3: off-thread value production and the ground under the player

Status: **design only.** No source file was modified. No compile, no editor launch,
no automation run was performed — `Docs/clanker/WorkerBrief.md:30-33` records that
Unreal 5.8 is reinstalling, Visual Studio Build Tools are absent, and no
MSVC/clang/gcc exists on this machine. Every claim below is derived by reading
source; every quantity is arithmetic over the code and is labelled as such. Nothing
here may be reported as meeting or failing the `Docs/Specification.md` §12 frame-time
gate, because no frame time can be measured here.

Subjects:

- `Source/TheWood/Private/WoodWorldStreaming.cpp` (the Unreal adapter, 93 lines)
- `Source/TheWood/Private/WoodPreparedChunk.cpp` / `.h` (the prepare boundary)
- `Source/TheWood/Private/WoodRuntime.h`, `Source/TheWood/Private/WoodWorld.cpp`
- `Source/TheWood/Private/Generation/WoodStreaming.cpp` (the pure planner)

Prior work this builds on and does not supersede:

- `Docs/superpowers/specs/2026-10-07-streaming-defect-triage.md` — the finding
  verification. This document implements triage §6 **Group B** and §7 step 3.
- `Docs/superpowers/specs/2026-10-07-streaming-h4-fix.md` — exception safety and the
  coordinate contract. **Interaction is specified in §11; two of its proposals are
  affected by this design and the overlap must be resolved before either lands.**

---

## 1. The defect, restated from the code

`AWoodWorld::EnsureTerrainAround` (`WoodWorldStreaming.cpp:20-23`) is three lines:

```cpp
void AWoodWorld::EnsureTerrainAround(FVector Position) {
 FIntPoint Key(FMath::FloorToInt(Position.X/12800),FMath::FloorToInt(Position.Y/12800));
 if(!Runtime->Chunks.Contains(Key)) Realize(WoodPrepareChunk(Generator,Key.X,Key.Y,Runtime->Kinds,Runtime->Profiles,Runtime->Available,false),false);
}
```

`:22` calls `WoodPrepareChunk` **inline, on the game thread**, and then `Realize`
runs component creation and a synchronous collision cook on the same thread in the
same frame.

The cost is exact and countable:

- A chunk is `(cells+1)² = 65×65 = 4,225` vertices at `cells = 64`
  (`WoodGeneration.cpp:154-158`, `WoodGeneration.h:9`, `WoodWorld.cpp:38`).
- `WoodPrepareChunk` makes **five `World::sample()` calls per vertex** —
  `WoodPreparedChunk.cpp:15-17` — one for the surface, four for the finite-difference
  normal. `4,225 × 5 = 21,125` samples.
- `generate()` itself has already called `ground()` once per vertex
  (`WoodGeneration.cpp:157`), so the prepare actually performs
  `4,225 + 21,125` ground evaluations, not 21,125.

Each `sample()` (`WoodGeneration.cpp:116-125`) runs one `climate()` and five
`ground()` calls (`:118-120`), and `ground()` is ≈9 `noise()` evaluations. So the
H2 path is on the order of **10⁵ noise evaluations and 10² milliseconds** of
game-thread work — arithmetic, not measurement. The only measured figure in this
repository is ".about 25 ms per 64-cell chunk" for the whole pipeline
(`.clanker/CLAUDE_REVIEW.md:18`), which is an aggregate from a different harness and
does not separate terrain-only from detailed work.

`Realize` adds two more synchronous costs on the same path:

- `WoodWorldStreaming.cpp:41` calls `Generator.sample()` **65 times** inside the
  water-ribbon loop, and `:39` calls `streamX`/`streamHalfWidth` 65 times
  (`streamHalfWidth` runs `validatePoint`, `WoodGeneration.cpp:114`). Another 65
  full samples per realisation, on the game thread.
- `CreateMeshSection_LinearColor(..., true)` at `:34` requests a **synchronous
  collision cook** of an 8,192-triangle trimesh. This is `.clanker/CLAUDE_REVIEW.md`
  `streaming-4`, already an open finding.

And `Docs/Status.md:9` — "Runtime object realization stays separate from background
value generation" — is contradicted by `WoodWorldStreaming.cpp:22` and by
`WoodWorld.cpp:123`, which realises **nine** chunks with `Details=true`
synchronously inside `BeginPlay`. That sentence is a documentation defect
(`WorkerBrief.md:21-23`: a claim no file supports is a defect) and must be corrected
by whoever lands this change, in the same commit.

### 1.1 A correction to the trigger description

`t-0011`'s brief says the cost is paid "on every chunk-boundary crossing and once at
BeginPlay". Triage §3/H2 and §5(c) show the boundary-crossing half is wrong, and this
design is built against the corrected trigger set:

- The planner requests `desiredRadius = ChunkRadius = 4` (`WoodWorldStreaming.cpp:74`),
  i.e. **512 m of lookahead**. At 420 cm/s (`WoodCharacter.cpp:26`, `Status.md:17`)
  the player's own chunk is therefore normally already resident and the `:21` guard
  does **not** fire on an ordinary crossing.
- The fallback *does* fire on: teleports and debug moves (the path both runtime
  tests exercise, `WoodRuntimeTests.cpp:56`, `WoodInstanceRetentionTests.cpp:77`),
  outrunning the queue, every null-pawn frame (H1, `WoodWorld.cpp:129-131`), and
  **nine times at `BeginPlay`** (`WoodWorld.cpp:123`) with the *expensive* detailed
  path.

Designing against "every boundary crossing" would aim the fix at the wrong path. The
fix below is aimed at all five triggers, because one change removes all of them.

---

## 2. The design in one paragraph

Split chunk preparation into **two independent worker stages** — *ground*
(geometry + per-vertex attributes + water ribbon) and *vegetation* (features +
grounded placements) — and make **every** generator call happen on a worker. Give the
player's own chunk a **reserved job slot** so it never waits behind a neighbour job,
and protect the ~10² ms during which the ground is genuinely not yet there with a
**cheap analytic collision volume** built from `GroundAt` (four `ground()` calls),
not from a chunk generate. Delete the synchronous prepare entirely, which also
deletes H3, because the duplicate attribute pass only exists as the shadow of the
synchronous prepare. Hoist the job snapshots into one immutable shared input built
once per session, which fixes M1 and makes snapshot drift impossible by
construction.

**One invariant carries the whole design:**

> `AWoodWorld::RealizeGround` and `AWoodWorld::RealizeVegetation` contain no call
> into `wood::` and no call on `Generator`. Every generator call lives in a worker
> task body.

Today `Realize` violates this three times (`WoodWorldStreaming.cpp:39`, `:40`,
`:41`). After the change the game thread's per-boundary cost of bringing terrain into
existence is **zero heavy samples**, and the only generator call left in that
neighbourhood is one `GroundAt` — four `ground()` evaluations, a value the frame has
already paid at `WoodWorld.cpp:133` — used to place the collision volume of §6.3.

---

## 3. What moves to the worker

The prepare payload becomes two types. Both are pure value data, both produced by
engine-independent or adapter-value code, and both safe off the game thread.

```cpp
// WoodPreparedChunk.h — replacement for FWoodPreparedChunk

// Stage 1 payload: everything Realize needs to build terrain components.
// All coordinates are metres. Nothing here has been converted to centimetres.
struct FWoodGroundChunk {
  wood::Chunk Chunk;            // vertices + triangles, metres (WoodGeneration.h:27)
  TArray<FVector> Normals;      // unit, dimensionless
  TArray<FVector2D> HabitatUV;
  TArray<FLinearColor> BiomeColors;
  FWoodWaterRibbon Water;       // L/R/Z vertex rows, metres
};

// Stage 2 payload: everything Realize needs to add instances.
struct FWoodVegetationChunk {
  FIntPoint Key;
  TArray<TArray<FTransform>> Placements; // centimetres, per vegetation slot
};
```

```cpp
// Stage 1 — worker only. Roughly today's WoodPrepareChunk(..., Details=false)
// plus the water ribbon that Realize currently computes on the game thread.
FWoodGroundChunk WoodPrepareGround(const wood::World& World, int X, int Y);

// Stage 2 — worker only. Features plus root-fitted placements.
FWoodVegetationChunk WoodPrepareVegetation(const wood::World& World, int X, int Y,
  const TArray<wood::Kind>& Kinds, const FWoodJobInput& Input);
```

### 3.1 The split, itemised by what it moves

| Work | Today | After | Note |
|---|---|---|---|
| `World::generate(x,y,false)` — heightfield + triangles | worker (`:79`) and **game thread** (`:22`) | worker only | `WoodGeneration.cpp:155-162` |
| Per-vertex attributes, 5 samples/vertex | worker (`:79`) and **game thread** (`:22`) | worker only | `WoodPreparedChunk.cpp:14-22` |
| Water ribbon: 65× `sample`, 130× `streamX`/`streamHalfWidth` | **game thread** (`:39`,`:41`) | worker, in stage 1 | this is the cost triage §3/H2 flags as unnamed |
| `generate(x,y,true)` — three feature layers + discovery | worker (`:79`, via `Details` default) and **game thread** (`:123`) | worker, in stage 2 | `WoodGeneration.cpp:163`, `:268-270` |
| Root fitting `WoodGroundedTransform` | worker | worker, stage 2 | `WoodGrounding.cpp:48-63` — pure value math over `Profile.Roots`/`Profile.Bounds`, no UObject, safe off-thread |
| `NewObject`/`RegisterComponent`/`SetupAttachment` | game thread | **stays** game thread | `:29`, `:47` |
| `CreateMeshSection_LinearColor` | game thread | **stays**, `bUseAsyncCooking=true` | `:34`, `:48` |
| `Palette->…LoadSynchronous()` | game thread | **stays** game thread | `:35`, `:49` |
| `AddInstancesById` / `RemoveInstancesById` | game thread | **stays** game thread | `:55`, `:67` |
| `SpawnActor<ARectLight>` | game thread | **stays** game thread | `:89` |
| Chunk coordinate math, unload, component destroy | game thread | **stays** game thread | `:21`, `:61`, `:64-70` |
| `plan()` | game thread | **stays** game thread | `:74` — it reads `Runtime->Chunks` / `Runtime->Jobs`, which are unsynchronised game-thread containers |

### 3.2 Why the game-thread items cannot move

Not as a claim about this repository's structure, but because each is engine
machinery rather than value production:

- **`NewObject` / `RegisterComponent` / `SetupAttachment`** — UObject creation and
  component registration are game-thread-only in UE. Touching a `UObject` from a
  task body is the defect `.clanker/CLAUDE_REVIEW.md` `streaming-5` exists to
  prevent; the fix is to keep the *current* value-capture discipline (`:79`) and
  move nothing that reaches a `UObject`.
- **`CreateMeshSection_LinearColor`** — hands arrays to the component's render
  proxy and, with `bCreateCollision=true`, builds a physics mesh through the
  component's collision scene. Both are component state.
- **`LoadSynchronous`** — asset loading touches the async loading thread and the
  render-thread resource fences. Calling it from a task body risks a deadlock and
  is outside every documented worker-thread contract.
- **`AddInstancesById`** — mutates ISM instance storage and rebuilds the instance
  buffer, then notifies the render thread.
- **`plan()`** — its inputs (`Runtime->Chunks`, `Runtime->Jobs`,
  `Runtime->LightCenter`) are game-thread-owned with no synchronisation. Moving the
  call to a worker would require locking the entire runtime state, which costs more
  than the 81-coordinate scan it avoids.

### 3.3 What the water ribbon move buys, precisely

`Realize`'s ribbon loop (`WoodWorldStreaming.cpp:38-43`) runs 65 iterations, each
calling `Generator.sample` once (`:41`) and `streamX`/`streamHalfWidth` once each
(`:39`). That is **65 more full `sample()` evaluations on the game thread per
realised chunk** — about 3% of H2's count, but paid on *every* chunk, not only on
fallback frames, and it is pure value with no UObject dependency. Moving it into
stage 1 costs the worker nothing and removes the last `Generator` call from
`Realize`, which is what makes the §2 invariant achievable.

`streamHalfWidth` calls `validatePoint` (`WoodGeneration.cpp:114`) and can throw.
Moving it into the worker puts that throw inside the task body, which is exactly
where the H4 design's Layer 1 (`2026-10-07-streaming-h4-fix.md` §3.1) can contain
it. **This is a synergy, not a conflict** — but it means the ribbon move must land
after, or with, the `noexcept` task body.

---

## 4. H3: why it disappears, and what survives

### 4.1 The mechanism

H3 is not an independent defect. It is the arithmetic shadow of H2:

1. `Realize` builds the ground mesh **once**, inside `if(!Resident.Ground)`
   (`WoodWorldStreaming.cpp:28-51`), consuming `Prepared.Normals`,
   `Prepared.HabitatUV` and `Prepared.BiomeColors` at `:32`.
2. On a later detailed realise of the same chunk, `Ground` is non-null, `:28` is
   skipped, `:52` returns after adding vegetation, and the detailed job's attribute
   arrays are dropped.
3. The only chunks that take that path are the chunks that were first realised
   terrain-only by `:22` — the H2 path.

Delete step 3's cause and step 2 has nothing left to discard. **Fixing H2 fixes H3.**
Trying to fix H3 alone — by caching the attribute pass, as triage §6 Group B
suggests — would preserve the synchronous generate and pay a cache lookup to keep
feeding it. That is the wrong direction and this design rejects it.

### 4.2 The waste that does survive, and its fix

Splitting the work by stage (§3) removes the duplication *structurally* rather than
by cache: stage 1 computes the attributes once and stage 2 does not compute them at
all.

There is a residual cost this design accepts rather than eliminates. Stage 2 needs
the chunk's vertices for its triangle-based height sampler
(`WoodPreparedChunk.cpp:26-34`), so it re-runs `generate(x,y,true)`, which rebuilds
the whole 4,225-vertex heightfield (`WoodGeneration.cpp:155-162`). That is
**4,225 `ground()` evaluations**, versus 25,350 (`4,225 + 21,125`) today — the
attribute pass, 80% of the per-vertex work, is gone. Sharing the heightfield between
the two stages would need a keyed cache with lifetime and invalidation rules, and
would put a mutable cache in front of a determinism guarantee (§9). **Rejected:**
not worth the complexity for a worker-side saving that no player can observe.

### 4.3 A second, smaller waste in the same function

`WoodPrepareChunk` computes the full attribute set unconditionally
(`WoodPreparedChunk.cpp:14-22`; the `!Details` early-out is at `:24`, *after* the
loop). All three arrays are consumed by the ground mesh, so today this is necessary —
but it is the reason stage 1 is expensive and it is why the split is worth doing
separately from the threading change. Recorded for measurement, not for this change.

### 4.4 A third waste that is a real defect after this change

The `loaded` vector passed to `plan()` (`WoodWorldStreaming.cpp:71-72`) filters on
`Entry.Value.Detailed`. After the split, **terrain-only residents become the normal
case rather than the exception**, so this filter would hide most resident chunks
from the planner and dispatch a redundant ground job for each.

Minimal fix in this change: build `Loaded` from **every resident** (any chunk with a
ground component), and pass detail state separately so the adapter can ask for
"vegetation only, no re-geometry". Concretely, replace the boolean
`FWoodResident::Detailed` (`WoodRuntime.h:6`) with a stage enum:

```cpp
enum class EWoodChunkStage : uint8 { None, GroundQueued, GroundRealizing, Ground, VegetationQueued, Vegetated };
```

`Loaded` is then "stage ≥ `Ground`", `Pending` is "stage is a `*Queued`", and
`Plan.removed` becomes correct for terrain-only chunks — which *retires triage M5's
latent trap* rather than triggering it. Note carefully: **the adapter must still not
wire `Plan::removed` in** (triage §5(b), M4/M5 are one unit in the pure core, Group E,
last). This change only makes the `loaded` set complete, which is safe whether or not
`removed` is ever consumed.

It also gives `LoadedChunkCount` (`WoodWorldStreaming.cpp:19`) an unambiguous
definition. Triage L3 found it has **no caller at all**, so renaming it costs
nothing: `ResidentChunkCount()` and `VegetatedChunkCount()`.

---

## 5. M1: one immutable job input

Today `Stream` copies four values **inside the per-coordinate loop**
(`WoodWorldStreaming.cpp:78`), and the lambda copies three of them again by value
(`:79`):

```cpp
const wood::World Snapshot=Generator;const auto Kinds=Runtime->Kinds;
const auto Profiles=Runtime->Profiles;const auto Available=Runtime->Available;
```

`FWoodPlacementProfile` holds `TArray<FVector> Roots` (`WoodGrounding.h:8-12`), so
this is a genuine deep copy of every imported tree's root-contact list. The
`wood::World` copy is three scalars (`Settings`, `WoodGeneration.h:9`) and is free;
it is `Profiles` that costs.

The comment at `WoodGrounding.h:7` states the intended discipline: *"Immutable value
snapshot: create on the game thread, then copy into jobs."* The defect is that the
snapshot is created per dispatch rather than once, so the design is followed
literally and expensively.

**Fix.** One input, built once on the game thread at the end of `Generate()`
(`WoodWorld.cpp:119`, after the vegetation components are appended in lockstep), held
as `TSharedPtr<const FWoodJobInput>` in `FWoodRuntime`, captured **by value** by every
task body:

```cpp
struct FWoodJobInput {
  wood::World Generator;
  TArray<wood::Kind> Kinds;
  TArray<FWoodPlacementProfile> Profiles;
  TArray<bool> Available;
  uint32 Revision = 0;              // bumped if the palette is ever reloaded
};
```

This satisfies three constraints at once:

- **No `this` capture, no UObject access, no raw pointer into `FWoodRuntime`.**
  Exactly what `streaming-5` requires. The worker's only shared state is an immutable
  `const` pointee.
- **No per-tick and no per-job copy.** One copy per session.
- **Snapshot drift becomes impossible**, which is a determinism argument, not a
  performance one (§9).

While building it, assert the coupling triage L1.1 found is unasserted and real:
`Kinds.Num() == Profiles.Num() == Available.Num() == Vegetation.Num()`.
`WoodPreparedChunk.cpp:6` `check`s the first three; nothing checks the fourth, which
is what `:54` (`Placements[I]` for `I < Vegetation.Num()`) actually indexes.

---

## 6. Terrain under the player without a synchronous generate

This is the part of the fix that changes player-visible behaviour, so it is treated
as the primary design question rather than an afterthought.

### 6.1 What the protection is actually for

Today `:22` guarantees that a collidable ground mesh exists **before** the player
crosses into a new chunk. Removing it means there is a window of one ground-stage job
duration in which the player is over a not-yet-built chunk. What must survive that
window, per `Docs/Specification.md` §7 ("immediate surroundings must remain
stable") is not "no hole is visible" — it is:

1. the player **cannot fall through the world** or fall forever;
2. the player does not **drop to an obviously wrong height**;
3. the ground that appears **agrees** with what the player was standing on.

Points 1 and 2 are what physics delivers. Point 3 is a correctness property of the
generator and is unaffected.

### 6.2 The reserved slot: bounding the window itself

The first half of the answer is to make the window as short as the pipeline allows.

`plan()` sorts `needed` nearest-first (`WoodStreaming.cpp:33-35`), so the centre
chunk is already first in `Plan.needed`. But dispatch is gated by
`Runtime->Jobs.Num() >= 2` (`WoodWorldStreaming.cpp:76`), and `plan()` counts
**all** in-flight coordinates toward `availableJobs` regardless of distance
(`WoodStreaming.cpp:23`). After a teleport both slots are busy with far-away work, so
the centre chunk waits up to **two** job durations: one waiting, one running. That
latency is precisely the reason `:22` exists.

**Fix — a reservation for the ground-under-player chunk.** Before the planner runs,
dispatch the centre chunk's ground job if it is neither resident nor pending,
*exempt from the concurrency cap*:

```cpp
// Runs first in Stream, replacing the EnsureTerrainAround(Position) call at :60.
RequestGroundAround(Position);   // cheap; dispatches at most one priority job

// The planner loop then skips any coordinate whose ground is already queued.
for (const auto& Coordinate : Plan.needed) {
  if (Runtime->HasStage(Coordinate, EWoodChunkStage::GroundQueued)) continue;
  if (CountNonPriorityJobs() >= MaxConcurrentJobs) break;   // priority jobs excluded
  Dispatch(Coordinate, /*bPriority*/ false);
}
```

Properties:

- **Bounded.** At most one job exceeds the cap, and only when the player's chunk has
  no ground. Worst case in flight is 3, not unbounded.
- **Halves the worst-case latency.** Centre-chunk latency goes from "wait for a slot
  + run" to "run", i.e. from ≤2T to ≈T.
- **Never bypasses the unload rules.** A resident chunk is not re-dispatched
  (`:21`'s guard survives, moved into `RequestGroundAround`).
- **No change to the pure planner.** `plan()` is untouched; the reservation is an
  adapter-level addition. This matters because triage §5(b) warns that changing the
  adapter and `plan()`'s contract in the same change destroys attributability, and
  because Group E is scheduled last.

**Known consequence to record:** this deliberately breaks the literal
"max 2 concurrent jobs" reading at `:76` and conflicts with triage M4's/H4 §5.3's
"replace the hard-coded cap with `Plan.availableJobs`", because `availableJobs` counts
every in-flight job including the priority one and would block the reservation it is
supposed to enable. `Plan.availableJobs` cannot be the sole gate until the
reservation lands. Decide with triage Group C, not here.

### 6.3 The collision volume: the part that replaces the synchronous guarantee

The second half is to make the window survivable at negligible cost, using a fact the
code already relies on: **the player's exact ground height is cheap and analytic.**

`GroundAt` (`WoodWorld.cpp:159`) calls `Generator.terrainHeight`, which is
`validatePoint` plus **four `ground()` evaluations** (`WoodGeneration.cpp:137-148`) —
about 1/5,000 of a chunk prepare, and already executed every frame by the world's
`Tick` (`WoodWorld.cpp:133`) and by the character's walk-speed test
(`WoodCharacter.cpp:45` → `WoodWorld.cpp:160`).

So while the ground component is absent for the chunk the player occupies, keep a
**small invisible collision box under the pawn**:

```cpp
// Realised in RequestGroundAround, destroyed the frame the chunk's ground exists.
Box->SetBoxExtent(FVector(300.f, 300.f, 50.f));          // 6 m x 6 m, centimetres
Box->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
Box->SetCollisionResponseToAllChannels(ECR_Block);
Box->SetWorldLocation(FVector(X, Y, GroundAt(X, Y)));   // top face exactly at ground
```

Why a box rather than a patch mesh:

- **A box needs no collision cook.** Its shape is a primitive; the body instance is
  valid on the next frame. `CreateMeshSection_LinearColor`'s cook
  (`WoodWorldStreaming.cpp:34`) is exactly the thing that cannot be made instant.
  `UBoxComponent` sidesteps it entirely.
- **It is invisible**, so there is no pop, no z-fighting with the arriving mesh, and
  no seam to hide. The mesh arriving beneath it is the only visible event.
- **Its height is exact**, because it is placed by the same `terrainHeight` function
  the real mesh is sampled from — point 3 of §6.1 holds by construction.
- **Its footprint is 6 m**, comfortably wider than the 60 cm capsule
  (`WoodCharacter.cpp:17`, `InitCapsuleSize(30,88)`) and under the camera, and it is
  bounded by construction to the case where the chunk has no ground at all.

Game-thread cost: one `GroundAt` per frame in the window (≈4 `ground()` evaluations,
already paid at `WoodWorld.cpp:133` in the same frame — the box can reuse that
value) plus one `SetWorldLocation`. **Heavy samples during the window: 0.**

The box is also a partial mask for H1: a null-pawn frame unloads the player's
terrain and requests it again (`WoodWorld.cpp:129-131` → `:60`); with the box, the
player keeps a floor for the duration rather than falling.

### 6.4 The remaining honest gap, and the alternatives

The box is invisible. For one job duration the player is looking at whatever is
underneath — sky, haze, or the previous frame's cleared depth. Three ways to close
that, none of which this design decides unilaterally, because each trades a
different felt quality and `Specification.md` §12 requires packaged frame times on a
recorded PC that cannot be produced here:

1. **Visible patch mesh** — a 4×4 patch of 6 m, sampled with `terrainHeight` (16
   samples ≈ 64 `ground()` evaluations, still trivial), rendered with the same
   material. Pop is visible where it meets the real mesh edge, 6 m from the player.
2. **Hold movement** — `GetCharacterMovement()->DisableMovement()` while the centre
   chunk has no ground. Costs no frame time and guarantees no visible hole, at the
   price of an input-latency hitch every boundary crossing and an awkward
   interaction with `SetSeated`/time dilation (`WoodCharacter.cpp:42`, `WoodWorld.cpp:162`).
3. **Accept the hole** — treat one job duration of sky-below-the-feet as acceptable,
   on the reasoning that the ground job is short and the alternative costs either a
   pop or a stutter.

**Recommendation: ship 1 (box) plus 3 (accept the hole) first, measure, then
evaluate 2.** A box is strictly better than nothing and has no downside; the visible
patch's pop is a new artefact that would need its own review, and freezing movement
every 128 m — 30.5 s at walk speed — is a felt regression that must be judged in a
packaged build, not here. **This is a human decision** (§12).

### 6.5 `WoodView`, and the one place a blocking wait is correct

`AWoodCharacter::WoodView` (`WoodCharacter.cpp:75-111`) calls `EnsureTerrainAround`
at `:107` and *then* `SetActorLocation` at `:108`. Its purpose is to frame a
screenshot; teleporting the pawn into an unbuilt chunk defeats the command.

Under this design `:107` becomes a blocking completion request:

```cpp
Environment->EnsureTerrainAroundBlocking(Position, /*TimeoutSeconds*/ 2.0);
SetActorLocation(Position);
```

This is a deliberate, bounded, once-per-command wait — not a per-frame stall — and it
replaces a synchronous generate that already happens on this line today. It does not
contradict `2026-10-07-streaming-h4-fix.md` §2.2 ("do not add `Wait()` anywhere"),
which is scoped to the per-frame drain loop; the rule there is *no blocking wait
inside `Tick`*, and this call site is not in `Tick`.

Reject the alternative (teleport first, fill in after): the operator presses a
console key to compose a photograph and gets a pawn in free-fall.

**This is also why `EnsureTerrainAround` must be renamed rather than kept.** Its name
promises a postcondition it will no longer have. The three call sites become:

| Call site | New call | Behaviour |
|---|---|---|
| `WoodWorldStreaming.cpp:60` (in `Stream`) | `RequestTerrainAround(Position)` | enqueue only |
| `WoodCharacter.cpp:44` (per character tick) | `RequestTerrainAround(P)` | enqueue only; the `:21` guard makes this a coordinate test in the common case |
| `WoodCharacter.cpp:107` (console) | `EnsureTerrainAroundBlocking(Position, 2.0)` | enqueue and wait, then realize |

Note that `WoodCharacter.cpp:44` runs **every character tick**, so the rename is not
cosmetic: a reader of that line must be able to tell from the name that it no longer
blocks.

---

## 7. `BeginPlay`: nine synchronous detailed chunks

`Generate()` ends with (`WoodWorld.cpp:121-124`):

```cpp
for(int32 Y=CY-1;Y<=CY+1;++Y) for(int32 X=CX-1;X<=CX+1;++X)
  Realize(WoodPrepareChunk(Generator,X,Y,Runtime->Kinds,Runtime->Profiles,Runtime->Available));
Stream(Start);
```

That is **nine chunks with `Details=true`** — the full attribute pass, three feature
layers and discovery planning each — plus nine component creations and nine
synchronous collision cooks, before the first frame. Under this design it becomes:

1. Build the shared `FWoodJobInput` (§5).
2. Enqueue the centre chunk's **ground** job as priority; enqueue the other eight
   ground jobs in nearest-first order through the normal path.
3. Enqueue the nine **vegetation** jobs through the normal path.
4. Call `Stream(Start)` as today.
5. Expose `bool IsGroundReady() const` so anything that needs ground can ask.

**The consequence is honest and lands in the tests:** ground is no longer present at
the end of `BeginPlay`. §6.3's collision box covers the interval. Two existing
runtime tests will need to pump rather than assume (§10).

`Generate()` is also the synchronous throw face identified in
`2026-10-07-streaming-h4-fix.md` §7.3(1) — `-WoodStartX=999040` throws inside this
loop, before `Tick` ever runs, and no task-body `try` can catch it. **This change
does not fix that** and does not attempt to: the throw site moves from
`WoodWorld.cpp:123` to the task body only for the async half, and the BeginPlay half
is replaced by an *enqueue* that no longer calls the generator at all — which does
in fact remove the throw face as a side effect. Say so precisely: **enqueueing removes
the synchronous `generate` call from `BeginPlay`, so the H4 §7.3(1) reproducer now
throws on a worker instead of at start-up, where Layer 1 catches it.** The bounds
guard of H4 §5.3 is still required for the `plan()` and `Tick` paths.

---

## 8. Determinism

`Docs/Specification.md` requires reproducible seeded geography, and
`WoodGeneration.h:40-41` already promises the property this design depends on:

> *"Terrain-only generation skips ecological work but produces identical geometry."*

Invariants this change must hold, each of which is testable:

1. **Stage 1 and stage 2 see the same heightfield.** Both call the same
   `World::generate(x, y, …)`; the vertex array is a pure function of
   `(seed, x, y)`. Placements fitted against stage 2's vertices therefore agree with
   the mesh built from stage 1's vertices — which is exactly the property
   `WoodInstanceRetentionTests.cpp:26-29` asserts today via a line trace against
   `GroundAt`.
2. **No worker reads mutable game-thread state.** The only shared object is
   `TSharedPtr<const FWoodJobInput>`, built once (§5). This is why the snapshot is
   built once and not per dispatch: per-dispatch copies *can* differ within a frame
   if the palette were reloaded mid-frame, and a diverging snapshot would produce a
   mesh and placements from two different worlds.
3. **Realization order does not affect content.** Stage 1 and stage 2 for the same
   chunk may complete in either order. `RealizeGround` must be a no-op when
   `Resident.Ground` exists; `RealizeVegetation` must be a no-op when
   `Resident.Vegetated`. Neither may depend on the other having run. (This is already
   true of `:28` and `:52`; the stage enum makes it explicit.)
4. **Which chunk drains first is not content determinism.** `Runtime->Jobs` is a
   `TMap` (`WoodRuntime.h:9`) and iteration order is arbitrary (triage M3). That is a
   *scheduling* nondeterminism and affects only the order components appear in, never
   what they contain. **Do not attempt to fix it here** — triage §7 step 4 gates the
   drain change behind this one, and the drain cap at `:62` stays as-is.
5. **No cache is introduced.** If a cache is ever added, key it on
   `(Input.Revision, x, y, stage)` and hold it as `TSharedPtr<const …>`. A cache
   keyed on anything weaker reintroduces the drift that §5 removes.

---

## 9. The metres-core / centimetres-adapter boundary

`WoodGeneration.h:6` states the boundary: *"Engine-independent generation
coordinates are metres; the Unreal adapter converts to cm."* This design keeps it
intact and does not move a single boundary:

- **Everything in `wood::` is unchanged.** No signature in
  `WoodGeneration.h`, `WoodStreaming.h`, `WoodHex.h`, or
  `Generation/WoodStreaming.cpp` is modified. `plan()` is untouched (§6.2).
- **Stage payloads are metres** except `FWoodVegetationChunk::Placements`, which is
  already centimetres today — `WoodGroundedTransform` converts at
  `WoodGrounding.cpp:49` and `:51`, and that conversion stays where it is, on the
  worker.
- **The single `*100` for mesh construction** stays in the adapter at
  `WoodWorldStreaming.cpp:31`, and the water ribbon gains the same one conversion
  where it is realized.
- **Chunk size must not be re-hardcoded.** The fix must use
  `Generator.settings().chunkSize` (metres) and
  `Runtime->Input->Generator.settings().chunkSize * 100` (cm), never the literal
  `12800`. This is triage M4 / H4 §5.2, and this change touches
  `WoodWorldStreaming.cpp:21`, `:39`, `:40`, `:61`, all of which currently carry it.
  **If the literals cannot be replaced in this change, do not add new ones.**
- **Distance maths for the reservation** is integer chunk arithmetic
  (`FloorToInt(Position.X / ChunkCm)`), matching `:21` and `:61`. `plan()` receives
  metres (`Position.X/100`, `:74`). Both forms already exist; do not unify them in
  this change.

---

## 10. Tests

**Nothing below has been run.** `WorkerBrief.md:30-33`; `Tools/Test-Streaming.cmd:4-5`
calls a `VsDevCmd.bat` from a path the brief records as absent.

### 10.1 Existing tests that will fail, and how to change them

| Test | Line | Why it fails | Required change |
|---|---|---|---|
| `Wood.Runtime.GroundAndObservation` | `WoodRuntimeTests.cpp:26`, `:29` | ticks **once** after `BeginPlay` then line-traces at `(-17920,-17920)` for a collidable floor. Ground is no longer present at end of `BeginPlay`. | pump with a frame budget and a real yield, mirroring `WoodInstanceRetentionTests.cpp:78-85` (`FPlatformProcess::Sleep(.005f)` — its comment at `:83` already notes that ticking simulated time cannot await worker jobs). Assert the floor within that budget. |
| `Wood.Runtime.ContinuousExploration` | `WoodStreamingRuntimeTests.cpp:24-29` | 200 frames at 0.01 then a line trace; probably sufficient, but not guaranteed with a background ground job and a priority reservation. | pump until `IsGroundReady()` rather than a fixed 200 frames, keeping a hard frame cap so a failure still fails. |
| `Wood.Runtime.RetainedVegetation` | `WoodInstanceRetentionTests.cpp:75-90` | teleports 3–4 chunks, which is H2's "outrunning the queue" trigger; already pumps and sleeps, so it should survive — but `Snapshot()` at `:57` reads instances **after** `BeginPlay` with no pump, and `:58` asserts `Count(Original)>0`. | add a pump-and-yield after `BeginPlayInTestWorld()` at `:50` before `:57`. |
| Any test asserting `LoadedChunkCount` | — | triage L3: **no caller exists**, so nothing breaks. | rename and leave uncalled until L3's contract is written. |

### 10.2 Tests to add

1. **No synchronous prepare (the direct H2 regression).** A runtime test that
   counts generator work is not possible without instrumentation, so assert the
   observable: after one `Tick` with the player's chunk unbuilt, the pawn has a
   collidable floor (§6.3) and no generator call appears on the game thread between
   the tick's start and end. A cheap and honest form: a `FScopedSlowTask`/
   `SCOPE_CYCLE_COUNTER` around `RequestTerrainAround` alone, since it becomes
   trivially cheap.
2. **Stage independence (H3's regression).** A unit test on the pure side: assert
   `generate(x,y,false).vertices == generate(x,y,true).vertices` element-wise, for
   several seeds and coordinates including negative ones. This is the invariant §8.1
   rests on and it is currently only promised by a comment
   (`WoodGeneration.h:40`), never asserted. **This test can run in the standalone
   suite the day a compiler exists.**
3. **One prepare, one realise (H3 at the adapter).** With the stage split, assert
   that a chunk realised from a ground stage and then a vegetation stage builds
   exactly one ground component and one set of instances — i.e. `RealizeGround` is
   idempotent. `StreamingRuntimeTests` has no seam for this today; it needs a
   counter exposed for the test build, or an internal-access test.
4. **Determinism across the seam.** Assert that a chunk's placements obtained via the
   priority path equal those obtained via the normal path for the same coordinate —
   identical because the input is one immutable object (§8.2). Cheap, and it fails
   loudly if someone reintroduces per-dispatch snapshots.
5. **The job-input coupling assertion (§5).** `Kinds.Num() == Vegetation.Num() ==
   Profiles.Num() == Available.Num()` asserted once in `Generate()`. Trivial, and it
   closes triage L1.1.
6. **Collision box lifetime.** A runtime test that forces the centre chunk to be
   absent (teleport far), ticks, asserts a `QueryAndPhysics` body exists under the
   pawn, then waits for the ground and asserts the box is destroyed and the real
   mesh's line trace agrees with `GroundAt` within 2 cm.

Do **not** add, in this change: a drain-count/time-budget test (M3, gated behind
this), a `Plan::removed` test (Group E, pure-core), or any test asserting frame time
(§12 requires a packaged build on a recorded PC).

---

## 11. Interaction with the parallel H4 / L4 / H1 designs

This is Group B from triage §6 and it shares lines with Group D. Two overlaps are
real and must be resolved by the orchestrator, not by whichever worker lands second.

| Overlap | H4 design says | This design says | Resolution |
|---|---|---|---|
| H4 §3.4 — "`EnsureTerrainAround` must go through the same total entry point as the async body" | route `:22` through `WoodPrepareChunkSafe` | there is no longer a synchronous prepare at `:22`; the entry points are the two stage functions, each called only from a task body | **H4 §3.4 is superseded for this call site.** Its "total entry point" requirement moves to the two new stage functions: they must be `noexcept`-wrapped where they are called from a task body. Everything else in H4 (remove-before-`Get`, refusal set, coordinate contract) is unaffected. |
| H4 §5.3 — "replace the hard-coded `Runtime->Jobs.Num() >= 2` with `Plan.availableJobs`" | cap must come from the planner | §6.2's reservation deliberately exceeds the cap by one | **Blocked.** `availableJobs` counts all in-flight jobs and would suppress the reservation. Decide with triage Group C; do not land H4 §5.3's cap change before this lands. |
| H4 §1.1 / §3.1 — `FWoodRuntime::Jobs` becomes `TMap<FIntPoint, TFuture<FWoodJobResult>>` | one job type | this design has **two** job types (ground, vegetation) | **Both must be applied together.** `FWoodJobResult` needs a stage discriminator, or `Jobs` becomes two maps. Sequencing hazard: this change is triage step 3, H4's is steps 1–2, so H4 lands first and this change must adapt to whatever it produced. Land the stage tag as a separate field on H4's result rather than changing the result type again. |
| L4 — bounds guard at `Tick`/`BeginPlay` | prune the position before coordinate math | unchanged; §9 forbids adding chunk-size literals | Compatible. Note that `BeginPlay` no longer calls the generator at all (§7), which removes H4 §7.3(1)'s start-up throw face. |
| H1 — null-pawn guard (`WoodWorld.cpp:129-131`) | one branch, lands first | §6.3's box masks its worst symptom for one chunk | Independent. **H1 still lands first** — fixing it removes a large share of H2's triggers for the cost of one branch. |
| M3 — drain cap / time budget | after this | explicitly not touched (§8.4) | Unchanged. |

**Merge hazard to state plainly:** both designs edit `WoodPreparedChunk.h`, the task
lambda at `WoodWorldStreaming.cpp:79`, and `FWoodRuntime.h`'s `Jobs` map. They cannot
both land independently. The orchestrator should sequence H4 steps 1–2 (which triage
§7 already places first) and then this design adapting to H4's `FWoodJobResult`.

---

## 12. Implementation surface

Nothing below has been applied.

| File:line | Change |
|---|---|
| `WoodPreparedChunk.h:8-14` | Replace `FWoodPreparedChunk` with `FWoodGroundChunk` + `FWoodVegetationChunk`; add `FWoodWaterRibbon` |
| `WoodPreparedChunk.cpp:3-49` | Split into `WoodPrepareGround` (attribute loop + ribbon, `:14-22`) and `WoodPrepareVegetation` (`:25-47`, no attribute loop) |
| `WoodPreparedChunk.cpp:8` | Stage 2 reuses `World::generate(x,y,true)`; the `Details` boolean parameter disappears from both new entry points |
| `WoodRuntime.h:6` | `bool Detailed` → `EWoodChunkStage Stage` |
| `WoodRuntime.h:9` | `Jobs` value type gains a stage tag (and `FWoodJobResult` if H4 landed); add `TSharedPtr<const FWoodJobInput> Input` |
| `WoodRuntime.h` | add `UBoxComponent* GroundFloor` to `FWoodResident`, plus `ResidentChunkCount()`/`VegetatedChunkCount()` |
| `WoodWorldStreaming.cpp:20-23` | `EnsureTerrainAround` → `RequestTerrainAround` (enqueue only) + `EnsureTerrainAroundBlocking` (console only, §6.5) |
| `WoodWorldStreaming.cpp:24-57` | split `Realize` into `RealizeGround` and `RealizeVegetation`; **remove all `Generator` calls** (`:39`, `:40`, `:41`) — the §2 invariant |
| `WoodWorldStreaming.cpp:34` | `bUseAsyncCooking = true` (`.clanker/CLAUDE_REVIEW.md` `streaming-4`); gate the *player's* chunk on `IsValidBodyInstance()` if the §6.3 box is ever retired |
| `WoodWorldStreaming.cpp:60` | `RequestTerrainAround(Position)` |
| `WoodWorldStreaming.cpp:62` | **unchanged** — the one-per-tick drain cap stays (M3, triage step 4) |
| `WoodWorldStreaming.cpp:71-72` | build `Loaded` from every resident; detail state passed separately (§4.4) |
| `WoodWorldStreaming.cpp:74` | pass `Generator.settings().chunkSize`, not the literal `128` |
| `WoodWorldStreaming.cpp:76` | replace the literal `2` with `CountNonPriorityJobs()` so the reservation can exceed it (§6.2); **do not** use `Plan.availableJobs` (§11) |
| `WoodWorldStreaming.cpp:78-79` | delete the per-loop copies; capture `Runtime->Input` (a `TSharedPtr<const …>`) by value; dispatch ground and vegetation as separate jobs |
| `WoodWorld.cpp:119` | build `Runtime->Input` once; assert the four-array coupling (§5) |
| `WoodWorld.cpp:123` | replace the nine synchronous prepares with enqueues (§7) |
| `WoodCharacter.cpp:44` | `RequestTerrainAround(P)` |
| `WoodCharacter.cpp:107` | `EnsureTerrainAroundBlocking(Position, 2.0)` |
| `WoodWorld.h:24-25` | rename `EnsureTerrainAround`, add `RequestTerrainAround`, `EnsureTerrainAroundBlocking`, `IsGroundReady` |
| `Docs/Status.md:9` | **delete or rewrite** "Runtime object realization stays separate from background value generation" — it is true only after this change lands, and it is the sentence H2 falsifies today |

**Suggested landing order**, smallest reviewable unit first, so the change is
reviewable and revertible in pieces:

1. §7 `BeginPlay` enqueues + §10.1 test pumps (removes the 9× start-up stall; proves
   the async path works end to end before anything depends on it).
2. §5 shared job input + the coupling assertion (no behaviour change; pure hygiene
   with a determinism payoff).
3. §3 water ribbon into stage 1 (removes 65 game-thread samples per realisation).
4. §3.1/§4 stage split + `RealizeGround`/`RealizeVegetation` + `EWoodChunkStage`
   (**this is H3; it is worthless without 5, which removes the synchronous prepare**).
5. §6.2 reservation + §6.3 collision box + `WoodView` blocking variant.

Steps 4 and 5 must land together: splitting without removing the synchronous prepare
leaves the duplicate attribute pass alive and H3 unfixed.

---

## 13. What this change does **not** fix

Stated so nothing here is over-read:

- **M3** — one ready job drained per tick (`:62`), arbitrary `TMap` order. Gated
  behind this change by triage §7 step 4, and it becomes the next bottleneck *because*
  this change raises throughput.
- **M2** — no cancellation. After a teleport both slots stay busy with far work;
  the reservation (§6.2) mitigates the player-facing symptom but does not cancel.
- **H4 / L4** — exception safety and the coordinate contract, except where §11 says
  this design supersedes H4 §3.4.
- **H1** — the null-pawn window relabelling. Lands first, independently.
- **M4** — the dead `retained()`/`Plan::removed` surface and the duplicated chunk
  size. §9 forbids *adding* literals; it does not remove the existing ones.
- **M5** — retired as a latent trap by §4.4, but `Plan::removed` still has no
  runtime caller and must not gain one until Group E.
- **`streaming-4`'s async-cook half** — `bUseAsyncCooking` moves the cook off the
  frame's critical path but does not remove the main-thread cost of
  `CreateMeshSection_LinearColor` itself.
- **Any frame-time claim.** No frame was measured. `Specification.md` §12 requires
  packaged frame times on a recorded PC; `Docs/Hardware.md` records this machine, and
  `WorkerBrief.md:30-33` records that it cannot produce them.

---

## 14. Unresolved questions — human authority

1. **The visible gap (§6.4).** Invisible collision box only (recommended first step),
   or also a visible patch mesh? This is a felt-quality judgement that needs a
   packaged build. **Recommendation: box only, measure, then decide.**
2. **Freezing movement during the window?** Cheapest guarantee of no visible hole, at
   the cost of an input hitch every 128 m. **Recommendation: no, unless §1 in
   §6.4's measurement shows the hole is a problem.**
3. **The reservation's cap semantics (§6.2, §11).** Is "at most one job beyond
   `maxConcurrentJobs`, and only for the player's own ground" acceptable as a
   permanent rule, or should it be expressed in the pure planner? **Recommendation:
   adapter-level now; revisit in Group E when `plan()` gains a proper priority
   concept.** This blocks H4 §5.3's cap change.
4. **Stage 2 re-running `generate(x,y,true)` (§4.2).** Accept 4,225 redundant
   `ground()` evaluations on the worker for simplicity, or introduce a shared
   immutable heightfield cache keyed on `(Revision, x, y)`? **Recommendation:
   accept.** The cache buys worker time nobody sees and costs a determinism guarantee.
5. **BeginPlay readiness (§7).** Should `Generate()` expose a blocking
   "world ready" gate for a loading screen, or is streaming-in-over-the-title-screen
   acceptable? This depends on the menu/loading work and is not a streaming decision.
6. **H4 sequencing (§11).** The orchestrator should decide whether H4 steps 1–2 land
   first with this design's stage tag grafted onto `FWoodJobResult`, or whether this
   design lands first and H4 adapts. **Recommendation: H4 first**, per triage §7's
   dependency order, since this design's task body needs a non-throwing entry point.
