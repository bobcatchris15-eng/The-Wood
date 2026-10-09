# Catalog gap list and Milestone 1 ranking

Reader: W09, 7 October 2026. Scope: `Docs/BiomeCatalog.md` (54 variants + 12 unreal
motifs) and `Docs/DiscoveryCatalog.md` (72 constructed assemblies, 40 natural
discoveries, 13 prop kits) against what the code actually decides.

**Method note.** No compiler, MSVC/clang or working Unreal install is present on
this machine (`Docs/clanker/WorkerBrief.md`, Toolchain table), so nothing here was
compiled or run. Every status below is from reading source, plus the existing
engine-independent suites in `Tests/`. "Implemented" means a code path exists that
makes the decision; it does not mean the decision has been visually accepted.

Status key: **spec-only** (no deciding code path), **partial** (a path exists but
covers a fraction of the catalog), **implemented** (the deciding path exists).

---

## Biome catalog

| # | Capability | Status | Deciding code |
| --- | --- | --- | --- |
| B1 | 54 named variants across 4 climate groupings | spec-only | `Source/TheWood/Public/Generation/WoodGeneration.h:10` — `enum class Biome { TemperateForest, DryGrassland, RockyHighlands, Taiga }`, four families and nothing else |
| B2 | Weighting families through temperature, moisture, elevation, exposure, substrate | spec-only | `Source/TheWood/Private/Generation/WoodGeneration.cpp:33` — `r.family=static_cast<Biome>(hash(c.seed,gx,gy,704)%4)`; `:34-38` are hardcoded developer overrides. Climate is an *output* of the family, indexed from tables at `:40-46`, never an input to choosing it |
| B3 | Edge transition bands between cells | partial | `Source/TheWood/Public/Generation/WoodHex.h:8` (`halfWidth=100`), `:29-35` core test, `:43` smoothstep product weights. Bands blend geometry and scalars smoothly; there is no neighbor compatibility pass, no rejected-neighbour reroll, no canonical edge contract record beyond `edge()` at `WoodHex.h:50` |
| B4 | Warped cell boundaries / ownership | implemented | `WoodHex.h:22` (`warp`, derivative-bounded), `:13` (`owner`), `:28` (`weights`); consumed at `WoodGeneration.cpp:50` |
| B5 | Twelve unreal regional overlays at ~1/10 of cells | spec-only | no unreal flag, field or test exists in `Source/` or `Tests/`; the only allocation gate in the generator is a 1-in-3 discovery hash (`WoodGeneration.cpp:174-186` calls into `WoodDiscovery.cpp:504-506`) |. `Status.md` "Deferred journey features" agrees |
| B6 | In-family variation: age/size cohorts, canopy openness, local habitats | partial | `WoodGeneration.cpp:205-231` picks young/sub-canopy/mature/ancient scale bands from one noise field and one hash; there is no per-cell variant identity, so two temperate cells share one recipe |
| B7 | Smaller habitats inside every family (fern hollows, streambanks, grass openings, shaded pools) | partial | colony noise and a riparian rock band at `WoodGeneration.cpp:232-248` and `:252-268`; these are density fields, not habitat records with site, extent and ownership |
| B8 | Climate-specific asset kits (shrub, broadleaf, reed, snow, mineral) | spec-only | `WoodGeneration.h:25` — `enum class Kind { Tree, Fern, Grass, Rock }`. Realization picks a mesh by kind only: `Source/TheWood/Private/WoodWorld.cpp:80-81` and `Source/TheWood/Private/WoodPreparedChunk.cpp:38-45`, where the variant index is `static_cast<int32>(Feature.yaw*19)%NumMatches` — position-hash noise, not climate |
| B9 | Ground treatment distinguishing regional families | implemented (four families) | `Source/TheWood/Private/WoodPreparedChunk.cpp:20-21` writes the four normalized biome weights to vertex colour; `Source/TheWood/Private/WoodWorldStreaming.cpp:32-35` feeds them to `Palette->GroundMaterial` |

## Discovery catalog

| # | Capability | Status | Deciding code |
| --- | --- | --- | --- |
| D1 | One primary landmark + 0–2 secondary discoveries per cell | partial | `Source/TheWood/Private/Generation/WoodDiscovery.cpp:490-521` returns exactly one `DiscoveryPlan` per cell. Primary exists; secondary discoveries have no representation at all |
| D2 | ~1/3 of cells eligible for a constructed discovery | implemented | `WoodDiscovery.cpp:504-506` — `(cellHash % 3) != 0` returns an empty plan |
| D3 | Independence of the 1/3 constructed allocation from the 1/10 unreal flag | spec-only | no unreal flag exists to be independent of (see B5); the only coupling is family/slope thresholds at `WoodDiscovery.cpp:475` |
| D4 | Ruin as one composition record (family, footprint, orientation, foundation, scale, construction logic, damage history, access, drainage, overgrowth) | partial | `Source/TheWood/Public/Generation/WoodDiscovery.h:75-84` carries type/position/yaw/reservation/pieces — footprint, orientation and ground contact are decided, but there are no damage-history, access, drainage or overgrowth fields. Damage is a per-segment 30% coin flip at `WoodDiscovery.cpp:152`, not a recorded event that children inherit |
| D5 | Site suitability + recorded candidate rejection | partial | suitability is three coarse thresholds at `WoodDiscovery.cpp:475` (highland) and `:501` (stream crossing); unsuitable sites are never logged or counted anywhere, so occurrence cannot be tuned across seeds as the catalog requires |
| D6 | Reservations that exclude conflicting scatter | implemented | `WoodDiscovery.cpp:10-27` (`isInsideReservation`), applied to trees at `WoodGeneration.cpp:213` and to the density gates at `:216-263` |
| D7 | Per-piece ground contact against realized terrain | implemented | every grammar calls `heightFn` at its own coordinate — e.g. `WoodDiscovery.cpp:139`, `:218-227`, `:348-352`; the callback is `World::terrainHeight` wired at `WoodGeneration.cpp:168-170` |
| D8 | Footbridge abutments matched across the channel | implemented | `WoodDiscovery.cpp:344-357` derives the channel normal from `streamXFn` and samples both bank heights before placing abutments |
| D9 | First natural/geological discovery tranche | partial | only `DiscoveryType::RidgeTor` exists among the 40 natural discoveries (`WoodDiscovery.h:26-32`); ridge overlook, spring seep, mossy rock hollow, windthrow clearing and fallen-log colony — the catalog's suggested tranche — are absent |
| D10 | 72-assembly cross-era / anomalous library | spec-only | no types beyond the four in `WoodDiscovery.h:26-32`. Worse, generated pieces are collapsed to two kinds at `WoodGeneration.cpp:272` (`Fern` if the mesh name says fern, else `Rock`), so walls, piers, abutments and monoliths are all realized out of `Palette->Rocks` via `WoodPreparedChunk.cpp:38-45` |
| D11 | Reusable prop kits and weathering overlays driven by exposure/water/age | spec-only | the only material parameters set at runtime are a global `WindStrength` scalar (`Source/TheWood/Private/WoodWorld.cpp:145`); there is no per-piece material, stain, moss-mask or damage-driven surface logic |
| D12 | "Leave room between discoveries": budget is a ceiling | partial | the 1/3 hash is a probability, not a competing-budget solver; nothing prevents two neighbouring allocated cells from competing for the same sightline, because composition is per-cell and unaware of neighbours |
| D13 | Deferred **F** items (caves, arches, interiors) stay deferred | implemented | no interior/overhang geometry or traversal code exists to accidentally depend on |

## Cross-cutting: macro-catchments

| # | Capability | Status | Deciding code |
| --- | --- | --- | --- |
| H1 | Macro-catchments: basins, divides, tributaries, confluence hierarchy | spec-only | `WoodGeneration.cpp:109-111` — `streamX(y)` is one global sine sum, so there is exactly one channel for the whole world; `:66` — `waterLevel(y) = 8-0.018*y` is a single monotonic plane, which cannot hold a pool or reverse a gradient |

---

## Top five by expected movement of Milestone 1's photographic gate

`Docs/Specification.md:158-168` scopes the gate as multiple seeds, a temperate
forest adjoining rocky highlands, outcrops, a connected stream, an overlook, close
ground detail, convincing banks, sunless lighting, and photographs inspected
walking/sitting/near/distant. It explicitly defers large ruins (`:169`). Ranking
is therefore driven by what a reviewer sees in a still frame, not by catalog size.

1. **Bind discovery pieces to real meshes instead of the rock pool**
   (`WoodGeneration.cpp:272` → `WoodPreparedChunk.cpp:38-45`). Every ruin piece
   currently spawns from `Palette->Rocks`, so any structure in a photograph is a
   cluster of boulders at architectural scale — the single most damaging artifact
   in a M1 still, and it is invisible in any test because shape is not asserted.

2. **Climate-driven family assignment plus a neighbor compatibility pass**
   (`WoodGeneration.cpp:33-38`). "Temperate forest adjoining rocky highlands" is
   currently a hash outcome that specific seeds have been hand-patched for, so
   multi-seed review can produce unrelated neighbors and reviewers are reviewing
   luck rather than design.

3. **Climate- and habitat-driven species selection with more than four kinds**
   (`WoodGeneration.h:25`, `WoodWorld.cpp:80-81`, `WoodPreparedChunk.cpp:38-45`).
   With every tree drawn from one pine library and variant choice made from yaw,
   grassland and taiga photographs read as the same forest at different densities
   — `Status.md` already calls dry grassland "sparse steppe rather than lush prairie".

4. **Streambank and bank believability at close range** (`WoodGeneration.cpp:70-82`,
   `:232-248`). M1 names "convincing banks" and wading explicitly, and `Status.md`
   lists non-uniform streambanks as open; the bank is currently a symmetric analytic
   falloff, so every close photograph of water shows the same profile.

5. **In-family small-habitat and variant identity** (`WoodGeneration.cpp:205-231`,
   `:232-248`). Fern hollows, grass openings and shaded pools are what separate a
   convincing forest from a field of trees, and today they are one noise field with
   no per-cell identity, so seeds repeat.

**Explicitly not ranked:** the unreal overlays (B5), the 72-assembly cross-era
library (D10) and macro-catchments (H1). All three are large, all three are
honestly spec-only, and all three belong to Milestone 4 per
`Docs/Specification.md:170-177` — building them now would spend the milestone on
deferred work.

**Unresolved / needs a human decision.** (a) Whether M1 review viewpoints should
avoid the three discovery sites at all until pieces are mesh-bound — the generator
places one at cell (0,0) unconditionally (`WoodDiscovery.cpp:478-484`), which is
the player start. (b) Whether `halfWidth=100` (`WoodHex.h:8`) is the intended M1
ecotone width or only a prototype value; no document states the target.