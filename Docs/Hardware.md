# Development reference — 2026-10-05

Inspected machine: AMD Ryzen AI 7 PRO 350, integrated AMD Radeon 860M, 32 GB system RAM, Windows desktop. This is a development reference, not a certified mainstream gaming performance baseline. WMI reports only a small dedicated graphics allocation; it does not describe the integrated GPU's total usable shared memory.

Initially no Unreal installation or MSVC compiler was found. With user authorization, Visual Studio 2022 Build Tools 17.14.41 and the C++ workload were installed, including the MSVC 14.44 toolchain and Windows SDK. The Epic Games Launcher was installed at `C:/Program Files/Epic Games/Launcher`.

The user subsequently installed Unreal **5.8.3**, changelist **58210709**, at `C:/Program Files/Epic Games/UE_5.8`. The project now targets the 5.8 release and its V7 build settings. The .NET Framework 4.8 SDK and targeting pack were added after an initial prerequisite failure. The editor module compiled successfully on 2026-10-06, followed by asset initialization, a passing in-engine runtime test and offscreen D3D12 rendering.

The engine-independent tests pass with both MSVC and a local Zig 0.13 compiler. These tests do not verify Unreal integration.

The target is 1920×1080 at 60 fps. Performance acceptance requires a recorded discrete-GPU reference PC, driver, engine patch version, scalability settings and packaged-build frame-time capture. No performance claim has been made.

