# Current work â€” four-biome streaming iteration, 2026-10-06

Authorized autonomous iteration continues beyond the previous bounded forest checkpoint. Current scope: TemperateForest, DryGrassland, RockyHighlands and Taiga regional weights on a 1,200 m lattice; four-family ground material blending; asynchronous chunk traversal with two value-generation jobs, near-first radius-four desired neighborhood (81 chunks), radius-six retention buffer (maximum 169 retained chunks), and protected terrain beneath the player. The old walking clamp is removed. Ordinary ISM identities support chunk lifecycle; roots fit realized terrain footprints. Regional lights use a fixed grid and sky follows the viewer.

Current reproducible unload/backtrack is not irreversible forgetting. Fresh identities for forgotten regions and save/resume remain deferred. Fixed opening, broader climates, ruins and wildlife are also deferred. No tree growth, combat, map, compass or survival mechanics.

Starting position approximately (-180, -180) m; dry grassland blend centers east (930, -120) and north (-80, 1040), rocky highlands northeast (1080, 1130), taiga south (-100, -1410). These are development coordinates, not exclusive biome areas. Controls remain WASD/mouse, E sit, T 20Ã— seated environmental time, C/right-click UI-free photos; movement 420 cm/s land, 280 cm/s wading.

Current increment review-ready. Fresh editor build and all four engine-independent suites pass. All four Unreal runtime tests pass, including continuous exploration and retained-vegetation regression. Current D3D12 captures inspected: Roots (temperate), Grassland, Highlands, Taiga. Root close-up shows seated trunk without definite air gap; angular brown soil skirt remains an art limit. Independent review accepted current increment with shared-pine/soft-rock/temporal limits. See Docs/Status.md and .clanker/REVIEW.md for evidence. No packaged performance certification.

Photographic quality and packaged 1080p60 remain open gates. Integrated Radeon 860M is a development reference, not a certified mainstream gaming baseline. Open visual work includes ground/contact shading, streambanks/bed/depth, species variety, overlook composition and temporal inspection. Rain, natural audio, album browsing and finished settings are unfinished.

Pointers: Docs/Specification.md; Docs/Status.md; README.md; .clanker/HUMAN_HANDOFF.md; .clanker/REVIEW.md; Saved/Review. Detailed spec preserves the full accepted journey and distinguishes current defaults from deferred requirements. Not a Git repository.

Follow-up verified: motion blur disabled at renderer default and camera override; young sapling cohort separated from established tree variants; wider size/maturity distribution and understory sizes. Fresh generation/biome tests, editor/content build and four runtime tests pass. Forest screenshot inspected after update.

New design request documented in Docs/BiomeGeneration.md with a hex ownership diagram and in Docs/DiscoveryCatalog.md (36 ruin assemblies, 40 natural discoveries, reusable kits). Future layout: pointy-top 950 m-radius hexes, edge-local 120–300 m blends, warped natural boundaries. Currentcode retains square regional lattice; no hex or ruin implementation yet. Independent review completed; corner kernel changed to C1 product weights, family choice is a bounded single pass, merged-region adjacency and cross-basin acyclicity requirements clarified.

## Hex foundation update

WoodHex.h now provides axial ownership, six neighbors, canonical edge keys, bounded smooth warp and normalized product edge weights. Core regional descriptions, climate/habitat and lighting use that layout; discovery candidate enumeration uses axial neighborhoods. Terrain chunks remain square128m. New Tests/HexTests.cpp and Tools/Test-Hex.cmd cover geometry. Hex family assignment is still seeded four-family prototype with starter overrides, not final climatecompatibility. Edgecontractpayloads/macrobasingeneration/catalogcontent/forgetting deferred. Prior square-lattice descriptions above are historical. Fresh hex, generation and biome suites pass; editor target builds; all four runtime tests pass. Evidence .cache/hex-*.log. No new rendered hex-transition review or packaged profile this pass.


## Procedural Ruins and Discoveries Update — 6 October 2026

Procedural ruins and discoveries system fully implemented and integrated into terrain generation:
- Standalone core module `WoodDiscovery.h` / `WoodDiscovery.cpp` provides procedural grammars for DryStoneShelter, CottageCorner, StreamFootbridge, and RidgeTor.
- `World::generate` dynamically queries discovery plans and applies reservation masks to exclude trees from ruin interiors and bridge spans.
- Every piece individually grounded to `terrainHeight(x, y)`.
- Fixed negative yaw wrap in `WoodPreparedChunk.cpp` and normalized piece yaws.
- Verification: all standalone test suites pass; `TheWoodEditor` builds in 11.4s; all 4 Unreal runtime automation tests pass with 0 failures.
