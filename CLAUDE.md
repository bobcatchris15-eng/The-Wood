# The-Wood — project notes

Unreal Engine 5.8.3 C++ project (`TheWood.uproject`), pinned to UE 5.8.

## Layout
- Core logic (engine-independent, in metres): `Source/TheWood/Public` and `Source/TheWood/Private`, under `*/Generation`.
- Unreal adapter (engine-side, in cm): the UE-facing classes in `Source/TheWood`, which convert core metres to UE centimetres.
- Tests: `Tests/*.cpp` (core, compiled standalone with zig) and Unreal runtime automation (`Wood.Runtime`).
- Test entry points: `Tools/Test-*.cmd` and `Tools/Test-Core.ps1`.
- Randomness: only via `random(seed, gx, gy, salt)`. Do not use other RNG sources.

## VALIDATE
Fast: `bash Tools/Test-All.sh` (run from repo root). Runs 16 suites: Core (`Tools/Test-Core.ps1`) plus Hex, Biomes, Flora, Discovery, Streaming, Atmosphere, Soundscape, Memory, Save, Entrance, Overlay, Ground, Fauna, Weather and Landmarks via `Tools/Test-<X>.cmd`. Prints PASS/FAIL with wall seconds per suite, exits non-zero if any fails. Measured on the 720 m hex build (all suites /O2): about 3 min total; per suite Core 30 s, Biomes 43 s, Flora 65 s, Landmarks 70 s, Entrance 7 s, the rest 1-3 s. Requires `.cache/toolchain/ziglang` (see Seed). Test-Core only covers GenerationTests. New suites add a `Tools/Test-<X>.cmd` and must be added to the loop in `Tools/Test-All.sh`.
Full: `powershell -NoProfile -File Tools\Build-Unreal.ps1 -EngineRoot 'C:/Program Files/Epic Games/UE_5.8'` then `powershell -NoProfile -File Tools\Test-Unreal.ps1`. Build with `-InitializeContent`: Succeeded, about 50 s wall; incremental without it about 5 s. Test-Unreal: about 36 s wall; runs the 8 `Wood.Runtime.*` automation tests (ContinuousExploration, GroundAndObservation, SpecMovement, RetainedVegetation, TreeRootContact, Forgetting, SaveResume, Threshold) and prints `PASS: <n> Unreal runtime test, <m> failures`; verify all Success in `Saved/Automation/index.json` (read with utf-8-sig, it has a BOM). `Test-Unreal.ps1` defaults `-EngineRoot` to `C:/Program Files/Epic Games/UE_5.8`. `Build-Unreal.ps1` requires `-EngineRoot`. Add `-InitializeContent` to Build-Unreal only when rebuilding Content (runs BootstrapEditor.py).
Golden fingerprints in `Tests/GenerationTests.cpp`: update only for intentional generation changes.
Probe: `Tools\Render-Review.ps1 [-Seed <int>] [-View Forest|Stream|Ridge|Grassland|Taiga|Highlands|Roots|Ruins] [-Time <double>]` (human review). Not run during this measurement. Produces renders for a person to inspect; no automated pass/fail.
Seed: `.cache/toolchain/ziglang` (zig 0.13.0, 323 MB; install with `python -m pip install --target .cache/toolchain ziglang==0.13.0`). `Content/` is 704 MB and is required for Unreal Full. Measured with `du -sh`.
Cost: Disk per tree is about 1.0 GB (324 MB toolchain + 704 MB Content), not counting Saved/ and Intermediate/. Provisioning time not measured.
Notes:
- Render-Review after -InitializeContent can show grey checker or crash (ShaderCompiler NumPendingJobs assert) on a cold shader cache; re-run once before diagnosing.
- Nanite (species trees) requires D3D12 SM6 (`+D3D12TargetedShaderFormats=PCD3D_SM6` in DefaultEngine.ini); on SM5 the Nanite fallback renders. First SM6 run compiles shaders cold: expect slowness and the NumPendingJobs assert, so re-run before judging.
- Test-Core compiles `WoodGeneration.cpp`, `WoodDiscovery.cpp`, and `Tests/GenerationTests.cpp` with `-Werror` and runs the generation executable. Output in `.cache/tests`.
- Startup: valid resume → as saved; else new journey at trailhead lot. `-WoodWild` = wilderness start (dev/test; Render non-Trailhead, Test-Unreal). `-WoodFresh` = no resume (Render Trailhead, Test-Unreal). `-WoodEntrance` = accepted no-op (default).
- Test-Unreal writes log to `.cache/unreal-tests.log` and report to `Saved/Automation`. Runs with `-nullrhi`.
- Build-Unreal uses `-WaitMutex`. Stale build output: rerun Build-Unreal before Test-Unreal.
- `Tools/Test-MSVC.cmd` is not part of `Tools/Test-All.sh`.
