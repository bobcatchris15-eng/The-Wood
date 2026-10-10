# Implementation status â€” four-biome streaming iteration

Updated 2026-10-08. This iteration is ready for human review. Fresh runtime checks and rendered biome/root inspections from 6 October are recorded below. The photographic acceptance gate remains open. Forgetting and save/resume were added on 8 October; see the section near the end.

## Current implementation scope

The generator now exposes temperate forest, dry grassland, rocky highlands and taiga, with smooth regional weights on packed hex cells (950 m radius, see Hex-cell foundation). Terrain, habitat queries and ground material treatment use those shared influences. This is four environmental families using a limited art library, not a completed collection of distinct climate-specific ecosystems.

The runtime now supports asynchronous traversal streaming beyond the original sixteen-chunk benchmark. The implementation schedules near chunks first, allows two concurrent value-generation jobs, requests a radius-four neighborhood (81 desired chunks), and uses a radius-six retention buffer (at most 169 retained chunks). Terrain chunks remain 128 m across. Runtime object realization stays separate from background value generation.

The old bounded walking clamp is removed. Generated ground under the player is protected while surrounding chunks are prepared. Ordinary instanced static meshes use stable instance identities for chunk lifecycle handling. Roots are fitted to the actual realized terrain footprint. Region lights occupy a fixed regional grid; sky presentation follows the viewer.

Regions left unobserved for the grace period are forgotten and regenerate with a fresh identity. Forgetting and save/resume are described in the section near the end.

## Controls and layout

- WASD/mouse first-person movement; 420 cm/s on land, 280 cm/s wading.
- E sit/stand with free look; T toggles seated 20Ã— environmental time; standing clears acceleration.
- C/right-click takes a UI-free photograph saved locally in `Saved/Photos`.
- No tree growth. Light, mist/cloud, wind and water animation express passing time.
- Start around (-180, -180) m. Developer views follow hex cell origins (see Hex-cell foundation). These are development references, not a player map or guaranteed exclusive-biome sites.

## Verification evidence and its limits

- Unreal 5.8.3 editor target compiled; current content bootstrap completed without Python errors.
- Four engine-independent suites passed on 6 October: generation, biomes, atmosphere and streaming. The suite set has since grown (see the section near the end). Biome coverage includes three seeds, far coordinates, normalized blends, neighboring chunk order, water continuity, walkable routes and actual triangle heights.
- On 6 October all four Unreal runtime tests passed (the suite now has seven): continuous exploration beyond the old boundary, movement/observation, actual imported tree-root contact, and two successive vegetation unloads preserving retained transforms.
- Actual tree-root test compares independently sampled terrain triangles: original worst root gap 7.34 cm; fitted lowest skirt contacts remain below soil across three imported models.
- D3D12 photographs inspected for temperate forest/root close-up, dry grassland, rocky highlands and taiga. Captures are in `Saved/Review/12345-{Roots,Grassland,Highlands,Taiga}-0.png`; material warm-up required a second initial grassland capture.
- Independent review found no definite floating tree or hard terrain seam in these captures. Distinct ground treatment, terrain and density are visible. Still images do not establish long-session temporal stability or packaged performance.

## Art and presentation foundation

The existing library includes three mature pine variants, four ferns, ten meaningful grass variants and fourteen normalized rocks. Explicit masked two-sided needle materials preserve leaf transparency. Rooted wind, conservative distance LODs and trunk-only collision remain part of the foundation. Ground materials now distinguish four regional families using blended shared inputs.

Regional light curves, local sky and ambient fill, mist, cloud cover, drifting cloud wisps, wind strength and game-time water/foliage animation support observation without a visible sun. Climate-specific species, richer litter/moss, less uniform streambanks, convincing water depth and stronger composition still require work. The imported pine bases retain angular brown scanned-soil skirts; root fitting removes the air gap but does not blend that art boundary. Large close-up rock textures can appear soft. Dry grassland currently reads as sparse steppe rather than lush prairie. Haze improves distant depth; streaming-window concealment still needs sustained motion review.

## Remaining visual and performance work

- Walk beyond the former boundary in several directions, turn back, cross chunk edges, wade, sit and photograph while streaming.
- Inspect lighting transitions and accelerated wind/water motion interactively.
- Measure scheduling, realization and photograph stalls; profile packaged 1080p builds on a recorded mainstream gaming reference.

The Ryzen AI 7 PRO 350 / integrated Radeon 860M development machine is not a certified 1080p60 reference. There is no packaged standalone release or performance certification. The photographic visual gate remains open. Rain, natural audio, album browsing and finished settings are unfinished.

## Deferred journey features

Fixed parking-lot opening and occluded entrance threshold; additional climate families and species; visual or generation use of the unreal flag (computed, not yet read); and occasional nonattacking wildlife remain deferred. Streaming implementation does not mean the full endless journey is complete.

## Follow-up: camera and plant maturity

Motion blur is disabled in project defaults and explicitly on the first-person camera. The palette includes three actual pine sapling meshes, selected as a separate young cohort in loose regeneration patches. Established trees span intermediate to mature sizes; ferns and grass now span a wider range with mature fern colonies retained. These are generation-time choices, with no growth simulation.

Fresh editor build/content bootstrap, generation and biome suites, and all four Unreal runtime tests pass after this change. The new hex-cell and discovery documents specify future architecture and content; no hex migration or ruin placement has been implemented in this follow-up.

## Hex-cell foundation — 6 October 2026

The regional layout now uses packed pointy-top hex cells (950 m corner radius), with smooth bounded coordinate warping and 200 m-wide edge transition bands. Normalized product weights preserve distinct cell interiors and three-cell corner blends. Terrain climate, habitat and lighting consume those same weights. Square 128 m rendering chunks and existing asynchronous streaming remain separate. Canonical undirected edge keys and axial ownership are available in WoodHex.h; adjacent region origins now come from hex centers.

This is the geometric foundation, not the full generation specification. Family assignment uses climate fields, fixed origin overrides and a hard DryGrassland-Taiga adjacency rule. The weighted compatibility pass, complete edge contracts, macro-catchments and expanded catalog assets remain future work. Forgetting is implemented (see below). Existing discovery placement uses the new axial neighborhood, preserving current prototype compositions.

Developer views follow cell origins: Grassland (1,0), Taiga (0,-1), Highlands (1,1). Previous hardcoded development coordinates are obsolete. Fresh verification: hex geometry, biome and general generation suites pass; Unreal editor target builds successfully; all four Unreal runtime tests pass. Rendered motion across the new hex boundaries and packaged performance remain unverified in this quota-limited pass.


## Forgetting and save/resume — 8 October 2026

- Forgetting is implemented. A region with no retained chunk for the grace period (90 s by default, on the shared observation clock) gets a new epoch. Its generation identity is then reseeded. Terrain shape near it can change too, because per-cell ground amplitude follows the region's family and roughness. Seeded base noise and the stream centreline do not change. Details are in BiomeGeneration.md section 10.
- Save/resume is implemented. The file is `<ProjectSavedDir>/Wood/resume.json`, written atomically and read back. The schema is version 1. Saves happen on exit, on autosave every 60 s of walking, when standing up, and when a region is forgotten. `-WoodFresh` disables loading and saving.
- Known gap: the saved `seed` is not applied on load. The generator seed comes from `Seed` or `-WoodSeed`.
- Unreal flag: computed per region (p = 0.10), with no reader yet. Ruins flag: independent (p = 1/3), used by discovery planning.
- Test coverage present: Memory and Save engine-independent suites, and the Unreal automation tests `Wood.Runtime.Forgetting` and `Wood.Runtime.SaveResume`. This documentation pass did not run them.

## Procedural Ruins and Discoveries Foundation — 6 October 2026

The terrain generation pipeline now procedurally synthesizes ruins and natural discoveries on-the-fly during chunk generation, replacing the previous hardcoded prototype altar. Discoveries are generated from mathematical grammars driven by cell seed, topography gradients, and stream hydrology:

1. **Procedural Grammars (First Tranche)**:
   - **Dry-Stone Shelter**: Elliptical contour-following masonry walls with leeward entrance opening and downhill rubble cascades along $-\nabla Z$.
   - **Cottage Corner**: Stepped foundation perimeter with upright corner piers, interior debris distributions, and fern colonization.
   - **Stream Footbridge**: Dynamically placed across the stream function $\text{streamX}(y)$ with abutments anchored to matching bank elevations and traversable stepping stones across the water bed.
   - **Highland Granite Tor**: Prominence monolith cluster with distance-decaying talus rock rings conforming to local ridge strike.

2. **Ground Contact & Dynamic Reservation**:
   - Every individual piece evaluates ground contact at its own coordinate against `terrainHeight(x, y)` (satisfying review finding `ue-runtime-5`).
   - Dynamic reservations exclude trees and large boulders from interior pads and bridge paths, while permitting pioneer ferns and moss rocks along margins.

3. **Verification**:
   - Standalone suites (`Test-Discovery`, `Test-Core`, `Test-Biomes`, `Test-Hex`, `Test-MSVC`, `Test-Streaming`, `Test-Atmosphere`) all pass with zero warnings.
   - Unreal Editor target compiled cleanly (Win64 Development).
   - All 4 Unreal runtime automation tests pass (ContinuousExploration, GroundAndObservation, RetainedVegetation, TreeRootContact) with 0 failures.


## Dev-machine frame-time capture (autopilot) - 9 October 2026

Label: dev machine, editor -game, not packaged - not the acceptance target. The packaged 1080p60 measurement in Docs/Specification.md section 12 is still open.

- Machine: Ryzen AI 7 PRO 350, Radeon 860M iGPU (shared memory), 32 GB RAM, Windows 11 Pro.
- Command: `Tools\Capture-FrameTime.ps1 -Seconds 120` (UnrealEditor -game, 1920x1080 windowed, `-WoodFresh -WoodWild -WoodAutopilot=120`, CsvProfile started and stopped by the autopilot).
- Route: fixed table, 10 legs of 60 m from grid start (-500,-300) (world -680,-480 m). Sprint 10 s, 3 photographs at 30, 60 and 90 s, 10 s seated 20x segment at 95-105 s, then quit at 120 s.
- Region boundaries crossed: 2 (region 0,0 to -1,0 at 31.8 s, to 0,-1 at 78.6 s). Route reached waypoint 8 of 10.
- Frames: 5096 over 120 s.
- Frame ms: avg 23.56, p50 22.70, p95 31.56, p99 44.18. Hitches (frame > 33 ms): 156.
- Game ms: avg 10.45, p95 15.18. Render ms: avg 22.72, p95 30.47. GPU ms: avg 21.70, p95 28.97.
- Result against the 16.7 ms p95 budget: FAIL on this machine. This is a measurement of the dev baseline, not a certification.
- Raw CSV: `Saved/FrameTime/20261009-224303.csv` (not committed).

### Perf tuning pass - before/after

Findings from the baseline CSV (dry weather, 156 hitches):
- Precipitation pools rewrote all 6500 slots (4000 rain + 2500 snow) every frame even when dry. This matches the steady 6500 NumAddedInstances / NumRemovedInstances per frame and NumInstanceTransformUpdates of about 6500.
- Hitch frames are game-thread spikes (game ms avg 24 in hitch frames vs 10 normal). They coincide with chunk realisation: added instances rise to 8k-21k against the 6.5k baseline.
- GPU/render bound at steady state: about 340k primitives drawn per frame, about 255k dynamic GPU scene instances.

Changes:
- `WoodPrecipitation`: transform writes limited to the visible prefix, skipped entirely when dry, and the transform buffer is reused across calls.
- `WoodWorldStreaming`: moss and fungus cast no shadow and no contact shadow. Grass and flowers keep the same treatment.
- `WoodWorldStreaming`: `WoodRealize chunk x,y detailed in N ms` log line for hitch correlation.

| Metric (120 s autopilot) | Before (224303) | After (224835) |
|---|---|---|
| Frame avg / p95 / p99 ms | 23.56 / 31.56 / 44.18 | 23.31 / 30.87 / 44.22 |
| Hitches > 33 ms | 156 | 149 |
| Game ms avg / p95 | 10.45 / 15.18 | 10.21 / 13.28 |
| GPU ms avg / p95 | 21.70 / 28.97 | 21.28 / 28.40 |

Still FAIL against the 16.7 ms p95 budget. The gain is small: the GPU and the render thread dominate steady state, and the hitches are chunk realisation spikes. Open: time-slice `Realize` (flora instance adds and fauna/landmark spawns) across frames at about 2 ms per frame; trim foliage cull distances (no lower than 0.75 x role defaults); check the iGPU shadow and translucency cost.

### Packaged Win64 Development build - 10 October 2026

Label: dev machine, packaged, not the acceptance target (still the Radeon 860M iGPU, not the reference PC).

- `Tools\Package.ps1 -Config Development`: BuildCookRun succeeded, archive at `Saved/Package/Windows/TheWood.exe`. Packaging config added to `Config/DefaultGame.ini`: MapsToCook `/Game/Maps/VisualBenchmark`, DirectoriesToAlwaysCook `/Game/Art`, `/Game/Wood`.
- `Tools\Capture-FrameTime.ps1 -Seconds 120 -Exe Saved\Package\Windows\TheWood.exe`: no frame data. The packaged exe crashed during `AWoodWorld::BeginPlay` (Generate, Realize, SpawnFlora), before the route started. Unhandled C++ exception (0xe06d7363) thrown from `wood::validatePoint()` (`Source/TheWood/Private/Generation/WoodGeneration.cpp:32`) via `terrainHeight()` and `WoodGroundedTransform()` (`WoodGrounding.cpp:60`). The editor `-game` run of the same route does not hit this, so the cause is not yet known. Crash log: `Saved/Package/Windows/TheWood/Saved/Crashes/`.
- Packaged results: none. Packaged avg/p95/hitches and the comparison with editor numbers are open until the crash is fixed.
- Shipping not attempted: the Development runtime fails before the route starts.

## Frame-time root-cause pass (dev machine, editor -game, Radeon 860M, 120 s autopilot)

Measured (CsvProfile, r.GPUCsvStatsEnabled): GPU-bound, not game-thread. Top costs:
1. GPU/Translucency about 13 ms of about 21 ms GPU. Cause: flora Leaves/Fronds/Petals MICs carry a BLEND_Translucent base-property override over a MASKED parent (about 660 translucent draws, TranslucencyAfterDOF). `show Translucency` off: avg 23 to 9.7 ms.
2. Chunk realize on the game thread, 10-40 ms per chunk (25 flora ISM components built in one frame, plus synchronous ground collision cook): most hitches.
3. TSR/post/lights about 4 ms (internal 1280x540 already).

| Metric | Before | After |
|---|---|---|
| frame avg / p95 | 23.3 / 30.9 ms | 22.5 / 29.7 ms |
| hitches >33 ms | 149 | 80 |
| Test-Unreal | pass | pass (0 failures) |

Fixes kept: flora ISM components built from a per-frame 2 ms queue (PumpFlora), async ground collision cook, `-Trace`/`-ExtraCmds`/`-ExecAt` in Capture-FrameTime.ps1.
Target (hitches <= 30, p95 <= 25) NOT reached. Gallery Forest/Grassland comparison not done.
Tried: dropping the translucent override at runtime (`-WoodMaskFlora`, off by default): translucency goes to 0 but Basepass +6 ms and RenderVelocities +5 ms (masked overdraw plus WPO velocity), GPU only 21 to 19 ms, hitches rose. Next steps: flora LODs/cull distances and WPO-disable distance for masked leaves, fix the MIC overrides in content and re-measure, cut instance density for the iGPU tier. Captures run alongside another editor process are invalid (contaminated); use a quiet machine.

## Foliage material cost at import (perf-foliage)
Dev machine, editor -game, 120 s autopilot, no other UnrealEditor running.
| | before (D3) | after |
|---|---|---|
| frame avg / p95 | 22.5 / 29.7 ms | 21.7 / 24.6 ms |
| hitches >33 ms | 80 | 35 |
| GPU avg / p95 | 21.3 / 28.4 ms | 20.4 / 23.4 ms |

Target (p95 <= 25, hitches <= 40) reached on this machine; still above the 16.7 ms packaged-target budget.
Changes: (1) the Translucent override sat on an intermediate glTF-copy MIC in the parent chain, not on the leaf MIC; `fix_foliage_mic` now walks the chain and drops it, pins clip 0.35, and repairs already-keyed content on re-run (402 MICs logged, translucency 47 ms -> 0). (2) Masked parents get `dithered_lod_transition`. (3) Flora LOD screen sizes 1.0/0.7/0.24 (`WoodFloraLODSize` tag): removing translucency alone made GPU WORSE (p95 56, masked LOD0 everywhere); distance scale x3 equivalent gave p95 23. ForceLOD 2 floor: 11 ms. (4) DefaultEngine.ini `r.EarlyZPass=2`, `r.Velocity.EnableVertexDeformation=0` (not isolated; reverting both via cvar gave no change before the LOD fix). (5) `StreamingSettled` now requires every resident chunk's flora queue empty and ground collision cooked (`bCreatedPhysicsMeshes`).
Gallery -Seed 42: 22 views, 0 broken; OldGrowth and Creature inspected, leaves cut out correctly. Test-Unreal 0 failures.

## Packaged startup crash (pkg-crash)
Crash: packaged Development exe threw from `wood::validatePoint()` via `terrainHeight()` <- `WoodGroundedTransform()` root-fit loop <- `SpawnFlora` <- `Realize` <- `Generate` <- `BeginPlay`. Editor -game unaffected.
Cause (adapter, not core): `WoodRootContacts` read cooked tree CPU position buffers unguarded. Where those buffers were not usable (cooked tree meshes without `bAllowCPUAccess`), the lower-envelope bins held non-finite or wild positions, so root offsets gave ground probes outside the 1e6 m core limit and `validatePoint` threw.
Fix: contacts filtered for NaN/non-finite and |v| > 1e8 cm; empty contacts fall back to bounds-min Z with a Warning; root-fit skips non-finite/out-of-range roots and only applies the fit if at least one root was used; `SpawnFlora` catches the core exception and skips the placement with a Warning; non-finite placement transforms are skipped. No core change, so no new core test.
Packaged log shows 114 `WoodRootContacts: ... no usable CPU positions; using bounds base` warnings, one per tree asset: the bounds-base fallback is in use for those species. Follow-up: enable CPU access on cooked tree meshes (Content, out of this scope).
Packaged Development, Capture-FrameTime 120 s (ran full 120 s, 4868 frames): frame avg 24.66 / p50 23.71 / p95 31.96 / p99 33.96 ms; hitches >33 ms 93; GPU avg 23.33 / p95 30.31 ms.
Editor -game, same 120 s autopilot (last recorded, D4 commit): frame avg 21.7 / p95 24.6 ms; hitches 35.
Packaged is ~3 ms slower on average and ~7 ms worse at p95, with 2.7x the hitches. Gap not yet analysed.
Validate: Build-Unreal OK; Test-Unreal 11 tests, 0 failures; Package.ps1 Development OK; Capture-FrameTime RESULT FAIL only on the 16.7 ms budget, run completed.
