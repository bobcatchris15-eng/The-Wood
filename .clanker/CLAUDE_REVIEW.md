# External review (Claude) — 2026-10-06

This review was read-only. It ran against a source snapshot taken 2026-10-06 10:11, while the streaming and biome work was still in progress, so all line numbers refer to that snapshot. Items marked "already changed in live tree" had been changed by the builder after the snapshot. The reviewer modified no code. The human owner asked for this review to help the builder.

## Act on first

1. **harness-1 / harness-2** (verify): `Tools/Test-Unreal.ps1:10-11`. The gate passes when only 1 of N tests runs, and it reads a stale `index.json` left by an earlier run. Unreal PASS results cannot be trusted until this is fixed.
2. **spec-gap-3** (runtime streaming / verify): `Source/TheWood/Private/Tests/WoodStreamingRuntimeTests.cpp:28`. ContinuousExploration passes even if the player falls through the terrain, and it never walks.
3. **gen-core-1** (regional generation): `Source/TheWood/Private/Generation/WoodGeneration.cpp:138`. Slopes reach about 74° 10-40 m from the stream. The traversability tests sample only at 7 m.
4. **ue-runtime-1** (verify): `Source/TheWood/Private/WoodGameMode.cpp:12`. Spawn Z uses the default-seed terrain, so any `-WoodSeed` or placed Seed puts the player at the wrong height.
5. **ue-runtime-3** (root-contact regression): `Source/TheWood/Private/Tests/WoodGroundingTests.cpp:60`. The root-contact test cannot detect floating downhill root flare.
6. **visual-1** (lighting/visibility): `Source/TheWood/Private/WoodWorld.cpp:49`. The only key lights are rect lights pointing straight down. The live tree also disables their shadows.
7. **streaming-4** (runtime streaming): `Source/TheWood/Private/WoodWorld.cpp:132`. Collision is cooked synchronously on the game thread for every streamed chunk.
8. **streaming-1** (runtime streaming): `Source/TheWood/Private/Generation/WoodStreaming.cpp:23`. Stale pending jobs hold every job slot after a teleport, and the planner returns no cancel list.

## Generation and biome core

The deterministic core holds up: no seam mismatches at chunk ±7700, and about 25 ms per 64-cell chunk. The problems are terrain shape near the stream, the global tilt against fixed-Z fog, and tests that check less than their names say.
Tests run: GenerationTests, BiomeTests and AtmosphereTests with MSVC `/std:c++17 /W4 /WX` all PASS. BiomeTests and GenerationTests under `/fsanitize=address` PASS with no reports. A `/O2` probe covered seeds 0/42/98765 for slope, water height, generate() timing and seams.

### [HIGH] gen-core-1 — Terrain walls up to ~74° line the stream corridor; traversability tests sample only inside the analytic terrace
- Where: `Source/TheWood/Private/Generation/WoodGeneration.cpp:138` (bank at L138, 25 m smoothstep blend at L146). Tests: `Tests/BiomeTests.cpp:98-100`, `Tests/GenerationTests.cpp:63`.
- Problem: Between 10 and 40 m from the stream the maximum slope is 3.22-3.53, and 11-17% of samples are above 0.7. A player who leaves the 10 m terrace meets a 25 m blend wall. The route checks sample at streamX-7, which always hits the bank formula, so they pass no matter what the biome or ridge code does. The comment at L143, "walkable approaches", is false.
- Fix: Limit the climb so `|base-bank| <= ~0.6*(distance-10)`, or blend over 60-100 m (wider in highlands). A wider smoothstep alone is not enough: its peak gradient is 1.5*(base-bank)/width, which is still too steep when ridge plus noise exceeds about 40 m. In the new test, assert `sample().slope < tan(38°)` for every distance from 10 to 80 m on both sides, for each seed and family. The live valleyWall term (L89) does not change the 25 m blend at L101.
- Verified: confirmed. From 40 to 200 m the max slope is 0.65, so the blend alone causes the walls. Correction: 20-29% of y rows are walled on both sides, so the trap is local, and a player can usually walk along the stream to a gap.

### [MEDIUM] gen-core-2 — Global 1.8% north-south tilt puts the ground hundreds of metres below the fixed-Z height fog and sky
- Where: `waterLevel(y)=8-0.018*y`, at snapshot L73 and live L65 of `WoodGeneration.cpp`. Fog: `WoodWorld.cpp:69`, which only ever calls SetFogDensity (L206).
- Problem: Ground sits at -892 m at y=50 km and +9008 m at y=-500 km. With the default falloff, fog density doubles for every 50 m drop, which is about every 2.8 km of travel along the stream: roughly 12x at 10 km and about 2^18 at 50 km. Any future SkyAtmosphere anchored at Z=0 would end up above or below the camera.
- Fix: Do not set the fog Z from the height under the player. Each tick, or when the streaming centre changes, call `SetActorLocation(FVector(PlayerX, PlayerY, waterLevel(PlayerY/100)*100 + offset))` on the fog. Expose waterLevel through the World API. Keep the gradient. Optionally add a test that `height - waterHeight` stays within a fixed band at y=±500 km.
- Verified: partial. This only becomes real once streaming lands (today ChunkRadius≤4 gives about ±9 m), the effect is not "none at all" at 5-10 km, and no SkyAtmosphere exists yet.

### [LOW] gen-core-3 — Generator throws at 1000 km with no catch anywhere
- Where: `WoodGeneration.cpp`. validatePoint is at L22-24, and generate() throws at L146-147 (live L150). The cited L200 is wrong. `WoodStreaming.cpp:16` throws on non-finite input.
- Problem: An out-of-range or NaN position (a teleport, or a bad Position) throws `std::invalid_argument`. That throw can escape an async task or the per-frame Tick sample()/lighting() calls, and the process dies.
- Fix: Add noexcept `World::supportsChunk/supportsPoint`. Have `streaming::plan` drop coords that fail it. Check that the pawn position is finite and in range before calling sample/lighting/plan, and clamp or skip that frame if not. If a task body can still throw, wrap only that body and post a failed result.
- Verified: partial. Reaching the edge by walking is unrealistic, so a NaN or teleported position is the real trigger.

### [LOW] gen-core-4 — Biome continuity and coverage assertions are far weaker than their names
- Where: `Tests/BiomeTests.cpp:49-59`.
- Problem: The tests cover 36 fixed points, each with one 0.05 m step. A future hard edge or coverage gap would pass unless it lands within 7 cm of one of those points.
- Fix: For several seeds, walk the corners and edge midpoints of lattice cells -3..3 plus far cells near ±800, and assert the cell's own origin is within `influenceRadius*0.95`. Run a 2 m transect over about 5 km in x and y, asserting per-step delta < ~0.01, sum == 1 and every weight finite. Do not add a per-metre gradient bound.
- Verified: partial. Nothing is wrong today: the geometry rules out gaps and lattice misses. This is only weak regression coverage.

### [LOW] gen-core-5 — "Terrain-only produces identical geometry" test is tautological
- Where: `Tests/BiomeTests.cpp:75-79`, against `WoodGeneration.cpp:144-158`.
- Problem: Geometry is built before `if(!includeFeatures) return chunk;`, so the test cannot fail. It will miss any divergence if streaming adds a separate terrain-only path.
- Fix: Keep the test. Once the runtime producer exists, compare its terrain-only chunk against World::generate and against terrainHeight at random interior points.
- Verified: partial. The citation was wrong. Only the features.empty() check does real work.

## Streaming core and planned runtime streaming

The pure planner is correct on floor rounding, nearest-first order, dedup and hysteresis. Its gaps: stale pending jobs, a dispatch contract the caller ignores, synchronous collision cooking, and a weak runtime test.
Tests run: StreamingTests (MSVC) PASS. Probe: plan(-128,-0.0) gives center (-1,0), correct. A teleport to x=6400 with two stale pending jobs gives availableJobs=0, needed=81, removed=0. A boundary crossing gives needed=9, removed=0.

### [MEDIUM] streaming-1 — Stale pending jobs after teleport/fast move starve near-first generation; plan has no cancel output
- Where: `Source/TheWood/Private/Generation/WoodStreaming.cpp:23` (availableJobs) and L28 (removed); `WoodStreaming.h:17-21`.
- Problem: availableJobs counts in-flight jobs outside retainRadius. After a teleport, both slots stay busy until the far jobs finish, which delays near vegetation and detail by one job lifetime. The live code also drains only one ready job per frame.
- Fix: Compute availableJobs only from in-flight coords that pass `retained(coord,center,retainRadius)`, and return the rest in a new `Plan::stale`. Test: a teleport with 2 stale coords gives availableJobs==maxConcurrentJobs and stale.size()==2. In `WoodWorldStreaming.cpp` Stream(), move stale entries to an orphan list and keep them owned until IsReady. Share a `TAtomic<bool>` cancel flag that WoodPrepareChunk checks between phases. Replace the hard-coded `Runtime->Jobs.Num()>=2` with Plan.availableJobs.
- Verified: partial. The line was wrong. The live code synchronously realizes the player chunk with collision and drops out-of-range results without realizing them, so the "uncollided ground" and churn impacts do not happen.

### [MEDIUM] streaming-4 — Synchronous collision cooking on the game thread blocks bounded per-frame integration
- Where: `Source/TheWood/Private/WoodWorld.cpp:132` (`bUseAsyncCooking=false`) and L148. Live: Realize() in `WoodWorldStreaming.cpp:34` never sets it.
- Problem: Every chunk realized from Stream() cooks its trimesh inline, so the frame hitches for the cook time.
- Fix: In Realize(), keep sync cooking for the EnsureTerrainAround player chunk and use `bUseAsyncCooking=true` for neighbours. Count a chunk as collidable only once `GetBodyInstance()->IsValidBodyInstance()` is true. Size the load radius so neighbours finish cooking first. Keep the one-job-per-frame cap or a time budget. Keep water NoCollision.
- Verified: confirmed. Async cooking only happens in game worlds with the flag set (ProceduralMeshComponent.cpp:1039).

### [MEDIUM] streaming-6 — Runtime streaming test can pass without exercising streaming near the player
- Where: `Source/TheWood/Private/Tests/WoodStreamingRuntimeTests.cpp:19`.
- Problem: The character spawns directly at the destination, the test ticks 200x, and then it runs one trace. A generate-on-spawn or never-unload implementation would pass. The test never checks boundary crossings, unloading or per-frame cost.
- Fix: (1) Teleport or walk across 2+ chunk boundaries and back, and assert loaded count ≤ (2*retain+1)^2, that out-of-retain chunks are unloaded, and that the player chunk is loaded and collidable within N ticks. (2) Assert a deterministic per-tick realize count ≤ the cap, not wall-clock time. (3) Make the floor trace hit terrain only, via LineTraceSingleByObjectType or the terrain component's LineTraceComponent.
- Verified: partial. A tree hit makes the test fail falsely; it cannot make it pass falsely.

### [LOW] streaming-2 — Planner returns the full needed list regardless of availableJobs
- Where: `Source/TheWood/Public/Generation/WoodStreaming.h:19`; `StreamingTests.cpp:22,27`.
- Problem: The bound is not enforced by the API or the tests. The live caller hard-codes 2 and ignores Plan.availableJobs.
- Fix: Keep plan() as it is. Launch only `min(needed.size(), availableJobs)` jobs in WoodWorldStreaming.cpp, and drop the `Jobs.Num()>=2` check. Optionally add a `dispatchable(const Plan&)` helper and test it (2 entries in the empty case, 0 in the shifted case).
- Verified: partial. The live caller already caps dispatch at 2, so 81 concurrent jobs do not happen.

### [LOW] streaming-3 — Unloading per-chunk HISM instances by index would corrupt other chunks
- Where: `Source/TheWood/Private/WoodWorld.cpp:172`.
- Problem: HISM removal uses RemoveAtSwap, so stored indices shift and later unloads delete the wrong trees.
- Fix: No new code is needed, because live already uses AddInstancesById/RemoveInstancesById. Add the plan L21 test: load A, B and C, unload A, then assert that B's and C's IDs pass IsValidId and that the transforms at GetInstanceIndexForId are unchanged.
- Verified: partial. Already planned and implemented. Already changed in live tree.

### [LOW] streaming-5 — Async chunk tasks need cancellation-safe lifetime
- Where: `Docs/superpowers/plans/2026-10-06-biomes-and-streaming.md:19`.
- Problem: A task that captures `this` and posts back after EndPlay would dereference a dead actor.
- Fix: Keep the live pattern: value captures and TFuture polled on the game thread. Add `Runtime->Jobs.Empty()` in EndPlay. If prepare cost grows, share an immutable `TSharedPtr<const wood::World>`. Keep WoodPrepareChunk away from UObjects and the static Cache in WoodGrounding.cpp.
- Verified: partial. The live code already avoids the failure. Already changed in live tree.

## Unreal runtime C++ correctness

UObject handling is sound. The spawn height is wrong for non-default seeds, the grounding test is near-tautological, and several tests bypass the real code paths.
Tests run: none. This was a static review plus engine source greps. Saved/Automation/index.json records only GroundAndObservation.

### [HIGH] ue-runtime-1 — Player spawn height uses default-seed terrain
- Where: `Source/TheWood/Private/WoodGameMode.cpp:12` (live L20-21 via ExplorerStart). Seed is applied at `WoodWorld.cpp:30/33` in BeginPlay; `WoodWorld.h:60` default seed is 12345.
- Problem: RestartPlayer runs during SpawnPlayActor (UnrealEngine.cpp:16647), before World->BeginPlay (L16661). With `-WoodSeed=42` or a placed Seed=7, the player spawns metres off the surface and can fall to KillZ. Render-Review hides this because WoodView re-grounds the player.
- Fix: Move the FParse WoodSeed call and the Generator rebuild into `AWoodWorld::PostInitializeComponents`, guarded by `GetWorld() && GetWorld()->IsGameWorld()`, and have BeginPlay only call Generate(). As a backstop, re-ground in `AWoodCharacter::BeginPlay`. Add a test that sets a non-default Seed and asserts `|Z - GroundAt - 100| < 150`.
- Verified: confirmed. Still present in live.

### [MEDIUM] ue-runtime-3 — Root-contact test samples only vertices within 2 cm of the mesh bottom
- Where: `Source/TheWood/Private/Tests/WoodGroundingTests.cpp:60`; helper `WoodGrounding.cpp:21` (+15 cm band) and L52 (min placement).
- Problem: Downhill root flare 5-30 cm above the lowest vertex is never measured, and the test also skips 30 of every 31 vertices. `NewWorst<=2` holds almost by construction. Nothing bounds uphill burial.
- Fix: For lower-band vertices (Z ≤ Bottom+60, outside the trunk radius, no decimation), compute native clearance and assert `(After.Z - Ground) - nativeClearance <= 2 cm`. Assert max burial < ~40 cm × scale. Include a steep site chosen by max terrainHeight gradient. In the helper, take the lowest vertex per XY bin across the lower envelope, or clamp burial. Do not assert an absolute ≤2 cm gap per vertex.
- Verified: confirmed. Whether a real asset floats depends on its root shape. Live is unchanged apart from a GroundHeight overload.

### [MEDIUM] ue-runtime-5 — Feature placement used center-only height; grounding helper not wired into runtime
- Where: `Source/TheWood/Private/WoodWorld.cpp:168`.
- Problem: TreeRootContact could pass while every rendered tree still used the old placement. The mesh overload has `check(IsInGameThread())` and fails if called from a worker.
- Fix: Add a runtime test comparing realized instance transforms, or WoodPrepareChunk Placements, against WoodGroundedTransform for the same features. Make sure the worker only receives FWoodPlacementProfile values, never a UStaticMesh*.
- Verified: confirmed. Live wires in the Profile overload (`WoodWorld.cpp:118`, `WoodPreparedChunk.cpp:44`). Already changed in live tree.

### [LOW] ue-runtime-2 — Seated 20x uses global time dilation
- Where: `Source/TheWood/Private/WoodWorld.cpp:218`.
- Problem: WoodCapture's Delay timer fires 20x early when accelerated. The test asserts dilation > 1, not that the Clock advanced.
- Fix: Keep global dilation, because material Time nodes depend on it. (1) In WoodCapture, use `SetTimer(..., Delay * GetGlobalTimeDilation(...))` or FPlatformTime. (2) Add a test that the Clock advances about 20x for a known real delta. (3) Tie the 20x rate to MaxGlobalTimeDilation, or set that explicitly in DefaultGame.ini. Real-time timers should use CustomTimeDilation=1/rate or real-time sources.
- Verified: partial. The design is deliberate. 20 sits at the clamp, not above it, and the camera/stand scenario does not occur.

### [LOW] ue-runtime-4 — Trunk collision is written into the shared UStaticMesh asset
- Where: `Source/TheWood/Private/WoodWorld.cpp:96` (live L89-96).
- Problem: In PIE, the editor asset's collision is replaced for the rest of the session.
- Fix: Author the capsule in BootstrapEditor.py (`remove_collisions` + `add_simple_collisions` CAPSULE, CTF_USE_SIMPLE_AS_COMPLEX, save) and remove the runtime mutation. Otherwise add a once-per-asset guard. Using Bounds.Min.Z for the capsule base is optional.
- Verified: partial. Save All does not persist the change (no MarkPackageDirty). The pivot concern is refuted, because Prepare-Art puts pivots at the base.

### [LOW] ue-runtime-6 — Walking test bypasses the real input path and never exercises wading speed
- Where: `Source/TheWood/Private/Tests/WoodRuntimeTests.cpp:58`.
- Problem: The test calls AddMovementInput directly, which skips Forward(), MoveForward and the W mapping. The 280 cm/s wading branch is never driven, and MaxWalkSpeed is never asserted. Status.md L13 and L23 claim more coverage than this.
- Fix: Inject input via `PlayerController->InputKey/InputAxis` on W, or call Forward(1.f). Add a probe at streamX(Y) asserting MaxWalkSpeed==280 after one tick.
- Verified: confirmed. This is a coverage gap, not a wrong result.

## Content bootstrap and art pipeline

Provenance is solid: 65 records, all CC0 with MD5. The weak points are name-cached derived materials, superseded import sets left on disk, and Interchange warnings nobody checks.
Tests run: read-only shell checks of the Tools scripts, bootstrap log greps, a manifest summary, and du/ls of the live Content folders. Nothing was compiled.

### [MEDIUM] art-pipeline-1 — Derived wind/rock materials are cached by name, so code changes are silently ignored unless VERSION is bumped
- Where: `Tools/BootstrapEditor.py:264` (with_wind L262-266, with_instancing L290-292).
- Problem: If the wind HLSL changes but VERSION stays 'CanopyV3', the old graphs are returned and the bootstrap reports success. The only way out is a VERSION bump, which reimports about 250 MB.
- Fix: Move the wind WPO into `/Game/Wood/MF_FoliageWind` and rebuild that function in place every run. Copies call it via MaterialFunctionCall with amplitude and WindStrength. For structural changes, tag each copy with `WoodSource` plus a code hash, then delete, re-duplicate and reassign on mismatch. Relax the FoliageWind/RockMaterials skips at L375/L380 so converted meshes get re-checked. Do not run delete_all_material_expressions on a duplicated Material, because it destroys the shading graph copied from the parent.
- Verified: partial. Needles are rebuilt by fresh(), and versioning is deliberate. Live code is the same.

### [LOW] art-pipeline-2 — About 397 MB of superseded import sets stay on disk
- Where: `Tools/BootstrapEditor.py:396`.
- Problem: ForestV2 (256M) and the unversioned V1 folders (~141M) sit beside CanopyV3, and Content/ is not gitignored.
- Fix: Optional cleanup in dependency order: ForestV2 and unversioned meshes first, then `*_ForestV2*` wind/rock materials, M_Ground, M_Water, M_Ground_ForestV2 and M_Water_ForestV2. Use delete_directory/delete_asset and fix up redirectors. Keep M_Ground_BiomeV2. If old saplings are kept on purpose, drop them from the L396 loop.
- Verified: partial. The save is idempotent, BiomeV2 is in use in live, and the cook-bloat scenario is speculative.

### [LOW] art-pipeline-3 — Interchange duplicates bark textures 3x per tree variant
- Where: `Tools/BootstrapEditor.py:349`; `Tools/Build-Unreal.ps1:16`.
- Problem: The GLB `textures[]` holds 3 entries pointing at one source image, and Interchange creates one texture per entry (`_1k`, `_1k1`, `_1k2`). The "Renamed Assets" warning is never checked.
- Fix: In Prepare-Art wind_uv(), collapse textures[] entries with the same (source, sampler), remap every textureInfo.index, and drop the unused entries. Alternatively, repoint the materials after import and delete `*_1k1/*_1k2`. Make Build-Unreal fail on 'Renamed Assets' or 'LogInterchangeEngine: Error'.
- Verified: partial. The cause is duplicate texture entries, not duplicate images. Cost is about 12 MB per variant.

### [LOW] art-pipeline-4 — Wind WPO reads UV1 as the mask without checking it exists
- Where: `Tools/BootstrapEditor.py:277`.
- Problem: A mesh without UV1 falls back to UV0, and its roots would sway.
- Fix: In the mesh loop, raise if `get_num_uv_channels(mesh,0) < 2` for any non-rock slot.
- Verified: partial. Prepare-Art always writes UV1, so this only triggers on a hand-built import.

### [LOW] art-pipeline-5 — Docs/Assets.md versioning and disk figure omit the superseded sets
- Where: `Docs/Assets.md:17`.
- Problem: The versioning pattern keeps growing Content/ and the doc has no cleanup step.
- Fix: Once art-pipeline-1 is fixed, import new species into fixed per-asset folders with `replace_existing=True`, and document a cleanup step.
- Verified: partial. The doc never says "must", and the 1.3GB figure is correct for sources.

### [LOW] art-pipeline-6 — set_material_usage is deprecated in 5.8
- Where: `Tools/BootstrapEditor.py:65`.
- Problem: If a future engine removes it, finish() raises and the bootstrap aborts before the palette is migrated.
- Fix: Use `MEL.set_base_material_usage(mat, unreal.MaterialUsage.MATUSAGE_INSTANCED_STATIC_MESHES)`.
- Verified: confirmed. The warning appears in three bootstrap logs.

## Build/validation harness and project hygiene

There is no single entry point, output locations are shared, there is no VCS, and the Unreal gate can report PASS falsely.
Tests run: none. Read-only inspection of the scripts, a parse of index.json, a test-registration grep, and a `.git` check.

### [HIGH] harness-1 — Unreal test gate passes when only 1 of N runtime tests ran
- Where: `Tools/Test-Unreal.ps1:11`.
- Problem: `failed -gt 0 -or succeeded -lt 1` passes as long as one test succeeded. Unregistered or stale-DLL tests are skipped silently, and notRun/inProcess are ignored.
- Fix: Derive the expected names from source (`IMPLEMENT_\w*AUTOMATION_TEST\(\w+,\s*"(Wood\.Runtime\.[^"]+)"`) instead of a hard-coded list, since live already has 4. Delete index.json before launch and throw if it is missing afterwards. Require every expected name with state Success, `notRun==0`, `inProcess==0`, and `succeeded == expected.Count`.
- Verified: confirmed. The live file is unchanged, and live already has a 4th test (Wood.Runtime.RetainedVegetation).

### [HIGH] harness-2 — Test-Unreal reads a stale index.json left by a previous run
- Where: `Tools/Test-Unreal.ps1:10`.
- Problem: When no test matches, the engine writes no report and exits 0 via -TestExit. The script then parses the older passing report and prints PASS. Renaming a test or the prefix triggers this.
- Fix: Use a per-run report directory, or delete index.json first. Fail if it is missing or if `reportCreatedOn` (UTC) is older than the script start. Replace `-TestExit` with `-ExecCmds="Automation RunTests Wood.Runtime;Quit"` so errors give a non-zero exit.
- Verified: confirmed. Traced through AutomationCommandline.cpp and LaunchEngineLoop.

### [MEDIUM] harness-5 — Project is not under version control while an autonomous agent edits it
- Where: `.gitignore:1`.
- Problem: There is no last-known-good state and no way to trace which revision produced a passing report or render. A second agent ("Soundscape", per `.claude/ledger.md`) is editing WoodWorld.h, WoodGameMode.cpp and Build.cs at the same time.
- Fix: `git init` and keep the existing .gitignore. Add `ArtSource/*-preview.jpg` and optionally `.claude/backup/`. Track Source, Tests, Tools, Config, Docs, .clanker, README, the uproject, the manifest/api json and the Prepared metadata. Put Content/ under LFS only if `git lfs version` works; otherwise leave it untracked. Commit path-scoped after each passing run, and record the SHA in Status.md.
- Verified: confirmed. Medium, because this is a process risk and nothing has been lost yet.

### [MEDIUM] harness-6 — No single entry point; README omits Biomes/Streaming tests
- Where: `README.md:32`.
- Problem: Following the README skips BiomeTests and StreamingTests, and in live also Hex and Soundscape. Test-Core covers generation only.
- Fix: Add `Tools/Test-All.cmd` (or Validate.ps1) that runs every `Tools/Test-*.cmd`, stops on the first nonzero exit and prints one PASS/FAIL line, with Test-Unreal as an optional tier. Do not hard-code a separate list. The README should name the entry point and each suite, and mark Test-Core as generation-only.
- Verified: partial. The gap has grown in live.

### [LOW] harness-3 — `*>` redirect under EAP=Stop aborts in Windows PowerShell 5.1
- Where: `Tools/Test-Unreal.ps1:8`; Render-Review.ps1 L10.
- Problem: Under 5.1, stray stderr output throws NativeCommandError before `$LASTEXITCODE` is read.
- Fix: Add `#Requires -Version 7.2`, or set EAP=Continue around the `&` call. Do not switch to Start-Process -ArgumentList, because it splits arguments containing spaces.
- Verified: partial. Reproduced in 5.1. UE logs go to stdout, so the builder's pwsh 7 runs are unaffected.

### [LOW] harness-4 — MSVC test scripts share the .cache/tests object directory
- Where: `Tools/Test-Biomes.cmd:8`, `Test-MSVC.cmd:8`, and live `Test-Hex.cmd`.
- Problem: Concurrent runs race on `WoodGeneration.obj`.
- Fix: In each script, `set "OUT=%TASK_ROOT%\.cache\tests\%~n0"`, mkdir it, and use `/Fo"%OUT%\\" /Fe"%OUT%\<name>.exe"`. Leave Test-Core.ps1 as it is.
- Verified: partial. The Atmosphere/Streaming and zig claims were wrong. This only matters when scripts run concurrently.

### [LOW] harness-7 — Render-Review grabs the newest PNG from shared Saved/Photos
- Where: `Tools/Render-Review.ps1:12` (live L15).
- Problem: A concurrent run, or pressing C in Play.cmd, can attach the wrong photo to a seed/view.
- Fix: Add an OutPath argument, `WoodCapture(View, Delay=1, OutPath="")`, and assert that exact file exists after exit. Alternatively, require exactly one new file. Take `-EngineRoot` as a parameter.
- Verified: partial. The "2 frames" claim was wrong (2 is a delay), and the trigger is hypothetical.

### [LOW] harness-8 — `succeeded` ignores succeededWithWarnings
- Where: `Tools/Test-Unreal.ps1:11`.
- Problem: If every test passes with warnings, succeeded is 0 and the script throws while printing no errors.
- Fix: Use the per-test state check from harness-1 (Success or SuccessWithWarnings), and print the warnings.
- Verified: confirmed. Every test must warn for this to trigger.

## Spec, plan and status conformance

The docs and the active plan disagree about whether expansion is gated. Several verification claims rest on tests that check less than they say. The control and speed claims do match the code.
Tests run: none. Static read of the docs, source and index.json.

### [HIGH] spec-gap-3 — ContinuousExploration can pass when the player falls through unstreamed terrain
- Where: `Source/TheWood/Private/Tests/WoodStreamingRuntimeTests.cpp:28`.
- Problem: If collision arrives after the spawn, the character falls with X unchanged. When the chunk lands, the trace hits and the X check passes. The test never walks and never checks for terrain ahead.
- Fix: After settling, assert `IsMovingOnGround()` and `|Z - (GroundAt + 88)| < ~5`. Add a walking leg near the coverage edge with `AddMovementInput(+X,1)` every tick, asserting each frame that Z never drops more than ~MaxStepHeight below GroundAt+88. Trace a probe about N chunks ahead and require a hit before the player reaches it.
- Verified: confirmed. Live is identical, and there is no snap-to-ground fallback.

### [MEDIUM] spec-gap-1 — Docs say biome/streaming is deferred behind the visual gate; the user's waiver is not recorded
- Where: `Docs/superpowers/plans/2026-10-06-biomes-and-streaming.md:8`; Spec L162/L194 (live L164); `Design.md:17`.
- Problem: A later agent could treat the streaming work as a spec violation and revert it, or assume the gate has passed.
- Fix: Leave Status, HUMAN_HANDOFF, README and CURRENT_WORK as they are. Add a dated line to Status.md: "2026-10-06: user approved the current look and authorized biome/streaming expansion before the photographic gate; the gate stays open for photographic quality." Update Spec §11, the "Expansion should wait" sentence and Design.md L17 to match.
- Verified: partial. The other docs are already updated in live. Spec L164 and Design L17 still contradict the plan.

### [MEDIUM] spec-gap-5 — Removing the clamp must also update spawn, water and light extents
- Where: `Source/TheWood/Private/WoodCharacter.cpp:40`; `WoodGameMode.cpp:18`; `WoodWorld.cpp:179`, L49 and L209.
- Problem: Removing only the clamp leaves the stream ending at ±256 m, lights fixed at ±160 m and an exposure drop.
- Fix: Make ChunkRadius mean retained radius, and remove every use of it as a world bound in the same change. Keep a recentred clamp until the collision-ahead test passes. Land the light grid with the clamp removal.
- Verified: confirmed. All of this has landed in live. Already changed in live tree.

### [LOW] spec-gap-2 — "Grounded placement" test checks only pivot Z
- Where: `Tests/GenerationTests.cpp:29`; `README.md:44` (live L46).
- Problem: The README says tests cover grounded placement, but the check is pivot-only.
- Fix: Change the README to "feature pivots sit on the analytic terrain height" and rename the check label to match. Leave Status L12. Cite TreeRootContact as grounding proof only once runtime placement uses WoodGroundedTransform.
- Verified: partial. The test correctly tests pivots; the problem is ambiguous wording.

### [LOW] spec-gap-4 — "Unreal runtime automation passes" rested on 1 of 3 tests
- Where: `Docs/Status.md:13`.
- Problem: The Status claim was older than the newly added tests.
- Fix: Have Status lines cite the count and timestamp, e.g. "Wood.Runtime: 4/4 passed (2026.10.06-19.43)". Tighten the gate (harness-1).
- Verified: partial. Live now has a 4/4 report and a rewritten Status. Already changed in live tree.

### [LOW] spec-gap-6 — Global dilation will also speed up game-time streaming budgets
- Where: `Source/TheWood/Private/WoodWorld.cpp:221`.
- Problem: Budgets or timeouts written in game seconds would run 20x faster while seated.
- Fix: Budget by item count or by FPlatformTime::Seconds per frame. For timeouts use FApp::GetDeltaTime or GetRealTimeSeconds/GetUnpausedTimeSeconds. Feed the Observation clock from undilated real delta × rate(), or read back the effective dilation.
- Verified: partial. Streaming does not use DeltaSeconds or timers yet, and 20 is not clamped.

### [LOW] spec-gap-7 — Lighting-boundary continuity and photo validation are only weakly checked
- Where: `Docs/Specification.md:93`; `Tests/GenerationTests.cpp:43-45`; `Tools/Render-Review.ps1:12-13`; `WoodRuntimeTests.cpp:36`.
- Problem: The lighting check covers kelvin at one point that may not be a real boundary. The photo check skips file size. The fog loop passes vacuously when no fog actor exists.
- Fix: Find a real boundary with world.regions(), sweep it in 0.5 m steps at several times, and bound both brightness and kelvin deltas. Require `$photo.Length -gt 0` (plus a PNG header check). Count fog actors and assert Count>0. A Photograph() automation test is optional.
- Verified: partial. Both checks do exist, but they are weak.

## Performance and scalability (1080p60 with streaming)

This was a static review. Likely bottlenecks are game-thread chunk building and VSM cost from WPO foliage.
Suggested protocol: a packaged Development build with `-csvprofile -trace=default,gpu,cpu,frame,bookmark`, plus `stat unit`, `stat gpu`, `profilegpu`, `r.Shadow.Virtual.ShowStats 1`, `stat virtualshadowmapcache`, `r.Nanite 0/1` and `r.ScreenPercentage 67`.
Tests run: none. Greps of source, config, BootstrapEditor.py and the render log.

### [MEDIUM] perf-4 — Each terrain vertex recomputes the noise stack about 25 times for normals
- Where: `Source/TheWood/Private/WoodWorld.cpp:137` (live `WoodPreparedChunk.cpp:15-18`).
- Problem: Each vertex makes 5 sample() calls, and each of those makes about 5 ground() and climate() calls. The EnsureTerrainAround fallback still runs this synchronously, and collision cooking is synchronous.
- Fix: Compute normals by central differences over Chunk.vertices heights with a 1-vertex skirt, and call sample() once per vertex. Pass the cached climate to the 4 slope ground() calls in World::sample, or compute slope from the grid. Set bUseAsyncCooking=true in Realize. Keep the fallback rare, and never run it while that chunk's job is pending.
- Verified: partial. The main loop now runs on the thread pool in live.

### [LOW] perf-3 — Ferns cast WPO shadows with default invalidation
- Where: `Source/TheWood/Private/WoodWorld.cpp:116`.
- Problem: Fern VSM pages near the camera are invalidated every frame.
- Fix: None needed now. If fern shadows return, set `ShadowCacheInvalidationBehavior=Rigid` and check with `r.Shadow.Virtual.Cache.DrawInvalidatingBounds 1`.
- Verified: confirmed for the snapshot. Already changed in live tree.

### [LOW] perf-5 — World-global HISM per variant does not suit chunk unload
- Where: `Source/TheWood/Private/WoodWorld.cpp:172`.
- Problem: Sync BuildTreeIfOutdated plus shifting indices.
- Fix: Keep the live ISM with AddInstancesById/RemoveInstancesById. If HISM comes back, never call BuildTreeIfOutdated(false,true) while streaming, and never store raw indices.
- Verified: partial. Already changed in live tree.

## Fresh-eyes visual and art direction

The lighting rig is the root problem: downward rect lights and no directional key light, so the ground looks carpet-flat. Water and distant fog come next.
Tests run: none. Inspection of 4 PNGs and greps of WoodWorld.cpp, BootstrapEditor.py and DefaultEngine.ini. Final albedo was not measured, and post-process volumes outside the snapshot were not checked.

### [HIGH] visual-1 — The only key lights are two rect lights pointing straight down
- Where: `Source/TheWood/Private/WoodWorld.cpp:49` (live `WoodWorldStreaming.cpp:89-90`, which also calls SetCastShadows(false)).
- Problem: There are no visible slanted shadows, and the ground under the canopy is as bright as open ground. "Evening" only lowers brightness.
- Fix: (1) Replace the RectLights with one movable ADirectionalLight that is not part of streaming. (2) Derive pitch and yaw from the viewer-local blended region phase (expose phase from World::lighting), add a per-region yaw offset, keep pitch between -15° and -60°, and interpolate rotation every frame. (3) SetLightSourceAngle 0.5-1, rising to 3-5 with cloudCover. Keep shadows on with VSM, and set SetDynamicShadowDistanceMovableLight to about 20000-30000. (4) SetAtmosphereSunLight(false). (5) Keep the SkyLight as fill, optionally from a real-time capture of M_Sky. Keep the kelvin temperature. Re-render Forest-0 and Forest-1650.
- Verified: confirmed. Worse in live, where shadows are disabled.

### [MEDIUM] visual-3 — Water is opaque and pale and reads as a concrete channel
- Where: `Tools/BootstrapEditor.py:173`; water section at `WoodWorld.cpp:189`.
- Problem: The default-lit opaque material shows no bed, no bank darkening and no tree reflections. It mostly reflects the bright M_Sky sphere at grazing angles.
- Fix: MSM_SINGLE_LAYER_WATER with SingleLayerWaterMaterialOutput: Scattering ~(0.02,0.04,0.03), Absorption ~(0.35,0.12,0.08)/m, PhaseG 0.1. Roughness 0.05-0.1, specular at the default. Lumen is already on, so leave it. Tone down the horizon colour on M_Sky. Darken the banks with the ground 'wet' term. Pass real tangents (+X along the stream) to CreateMeshSection_LinearColor.
- Verified: partial. Lumen was already on. Live has tweaked values but the material is still opaque.

### [MEDIUM] visual-6 — Fog inscattering colour is darker than the sky
- Where: `Source/TheWood/Private/WoodWorld.cpp:73` (live L67).
- Problem: Distant trees form a dark, sharp band against a near-white sky.
- Fix: In Tick, set the inscattering colour to the sky horizon tint × the same factor as SkyBrightness (`4*brightness*(1-0.45*cloudCover)`), computed once in C++. Alternatively use InscatteringColorCubemap. Keep falloff at 0.02 and set StartDistance to about 1500. Skip DirectionalInscattering. Re-render to check the far band.
- Verified: partial. Low density in ridge areas is an equal cause. Live raised the density, but the colour is still dark.

### [LOW] visual-4 — Skylight is a fixed neutral grey cubemap
- Where: `Source/TheWood/Private/WoodWorld.cpp:65` (live L58-59).
- Problem: The fill light has no sky colour and there is no blue hour.
- Fix: Each tick at L204, call `SetLightColor` from kelvin or the M_Sky parameters (cooler at low brightness). For a captured sky, set "Is Sky" on M_Sky, then SLS_CapturedScene, bRealTimeCapture and RecaptureSky(). Keep the ambient floor.
- Verified: partial. Lumen already provides canopy occlusion.

### [LOW] visual-7 — Trees, ferns and grass are spaced too evenly
- Where: actual logic is in `Source/TheWood/Private/Generation/WoodGeneration.cpp` layer() (~L161-209), not `WoodWorld.cpp:78`.
- Problem: The jittered lattice allows at most one item per cell, so the forest reads as planted.
- Fix: Let a cell spawn 0-N children around a jittered parent (2-4 m for trees, 0.3-1 m for grass), with N from a Poisson draw on density or colony. Apply a min-distance reject and keep the chunk-bounds ownership test. Snags and logs belong in a separate task.
- Verified: partial. Scale variety and colony noise already exist. The lattice spacing is unchanged in live.

## Checked and not an issue

- spec-gap-8 — "Unverified assumptions" (CPU access, collision vs render, variant skew): refuted. Root contacts are game-thread only with a fallback, CPU access is set at import, collision is complex-as-simple, and yaw-based selection is uniform. The live GroundAt already uses terrainHeight.
- perf-1 — Benchmark exits before DF/Lumen cards are built: refuted. The "Abandoning" lines are always logged on shutdown, and there is no evidence of pending builds.
- perf-2 — Needle cards are non-Nanite: refuted. Interchange defaults to bBuildNanite=true, and the imported meshes have Nanite enabled.
- perf-6 — 1000 MB texture pool vs 4K PBR sets: refuted. Ground textures are 2K, props are 1K (about 5% of the pool), and 1000 MB is the engine default.
- visual-2 — Ground tints read as desert: refuted. The renders came from the older CanopyV3 material and albedo was never measured. If tuning, check in VisualizeBuffer BaseColor first.
- visual-5 — Sky clips because exposure is unset: refuted. AutoExposure=False pins exposure, and the measured sky maxima are below 250. Dim evening frames are an art-direction choice.

## Not reviewed (coverage critic)
- C++20/exceptions divergence: the UE module builds with Cpp20 + exceptions, but every standalone test uses /std:c++17. No `try` anywhere around generator throws, and those throws will std::terminate on async workers.
- WoodAtmosphere.cpp throws if forestWeight is outside [0,1]. Blended biome weights can round to 1.0000001, so this can crash the game thread. Clamp at the call site.
- Packaged Game target: check that /Game assets loaded by path get cooked (DefaultGame.ini has no cook dirs). PCG plugin is enabled but unused.
- Tools/Inspect-TreeRoots.py vs WoodGrounding.cpp: confirm they use the same LOD and footprint, or the root fix is validated against the wrong number.
- Config/DefaultInput.ini axis/action names vs the BindAxis/BindAction strings in WoodCharacter.cpp.

## Added by Claude on 2026-10-06 (not part of the review) — please preserve
Procedural ambient soundscape, synthesized with no audio assets: `Generation/WoodSoundscape.h/.cpp`, `Tests/SoundscapeTests.cpp`, `Tools/Test-Soundscape.cmd` (output goes to .cache/tests/soundscape), and `AWoodAmbience` (`WoodAmbience.h/.cpp`). Hooks: inline const getters in `WoodWorld.h`, and a spawn in `AWoodGameMode::BeginPlay`. Tests pass and the editor module builds. It has not been listened to in game yet. Volume and mix are untuned.
