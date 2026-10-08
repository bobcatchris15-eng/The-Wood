# The-Wood — project notes

Unreal Engine 5.8.3 C++ project (`TheWood.uproject`), pinned to UE 5.8.

## Layout
- Core logic (engine-independent, in metres): `Source/TheWood/Public` and `Source/TheWood/Private`, under `*/Generation`.
- Unreal adapter (engine-side, in cm): the UE-facing classes in `Source/TheWood`, which convert core metres to UE centimetres.
- Tests: `Tests/*.cpp` (core, compiled standalone with zig) and Unreal runtime automation (`Wood.Runtime`).
- Test entry points: `Tools/Test-*.cmd` and `Tools/Test-Core.ps1`.
- Randomness: only via `random(seed, gx, gy, salt)`. Do not use other RNG sources.

## VALIDATE
Fast: `powershell -NoProfile -File Tools\Test-Core.ps1` (run from repo root). PASS, exit 0, about 26 s wall. Requires `.cache/toolchain/ziglang` (see Seed).
Full: `powershell -NoProfile -File Tools\Build-Unreal.ps1 -EngineRoot 'C:/Program Files/Epic Games/UE_5.8'` then `powershell -NoProfile -File Tools\Test-Unreal.ps1`. Build: Succeeded, about 5 s wall (incremental). Test: `PASS: 4 Unreal runtime test, 0 failures`, about 30 s wall. `Test-Unreal.ps1` defaults `-EngineRoot` to `C:/Program Files/Epic Games/UE_5.8`. `Build-Unreal.ps1` requires `-EngineRoot`. Add `-InitializeContent` to Build-Unreal only when rebuilding Content (runs BootstrapEditor.py).
Probe: `Tools\Render-Review.ps1 [-Seed <int>] [-View Forest|Stream|Ridge|Grassland|Taiga|Highlands|Roots|Ruins] [-Time <double>]` (human review). Not run during this measurement. Produces renders for a person to inspect; no automated pass/fail.
Seed: `.cache/toolchain/ziglang` (zig 0.13.0, 323 MB; install with `python -m pip install --target .cache/toolchain ziglang==0.13.0`). `Content/` is 704 MB and is required for Unreal Full. Measured with `du -sh`.
Cost: Disk per tree is about 1.0 GB (324 MB toolchain + 704 MB Content), not counting Saved/ and Intermediate/. Provisioning time not measured.
Notes:
- Test-Core compiles `WoodGeneration.cpp`, `WoodDiscovery.cpp`, and `Tests/GenerationTests.cpp` with `-Werror` and runs the generation executable. Output in `.cache/tests`.
- Test-Unreal writes log to `.cache/unreal-tests.log` and report to `Saved/Automation`. Runs with `-nullrhi`.
- Build-Unreal uses `-WaitMutex`. Stale build output: rerun Build-Unreal before Test-Unreal.
- Test-*.cmd scripts (Atmosphere, Biomes, Discovery, Hex, MSVC, Soundscape, Streaming) were not run in this measurement.
