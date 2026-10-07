# UE project context

Read by the `ue-*` skills to avoid generic answers. Everything here is verified
against this repository as of 2026-10-07.

## Project

| | |
|---|---|
| Name | The Wood |
| Engine | **Unreal Engine 5.8.3**, changelist 58210709, targets the 5.8 release |
| Language | C++20 runtime, C++17 for the engine-independent core |
| Platform | Windows desktop, keyboard + mouse |
| Modules | `TheWood` (Runtime), plus `TheWood` and `TheWoodEditor` targets |
| Game | First-person procedural wilderness exploration. No combat, no survival meters, no map or compass, no tree growth. |

The project descriptor is `TheWood.uproject`.

## Plugins enabled

| Plugin | Why it matters |
|---|---|
| `ProceduralMeshComponent` | Runtime triangle construction |
| `PCG` | Authoring-time placement. **Available, not mandatory.** `Specification.md` §9 is explicit that PCG is an authoring tool and that every placement does *not* need a PCG graph. |
| `PythonScriptPlugin` | Content bootstrap |
| `EditorScriptingUtilities` | Content bootstrap |

## Module layout

```
Source/TheWood/
  Public/
    Generation/     WoodAtmosphere.h  WoodDiscovery.h  WoodGeneration.h
                    WoodHex.h  WoodSoundscape.h  WoodStreaming.h
    WoodAmbience.h  WoodCharacter.h  WoodGameMode.h  WoodGrounding.h
    WoodPalette.h   WoodWorld.h
  Private/
    Generation/     WoodAtmosphere.cpp WoodDiscovery.cpp WoodGeneration.cpp
                    WoodSoundscape.cpp WoodStreaming.cpp
    Tests/          WoodGroundingTests.cpp WoodInstanceRetentionTests.cpp
                    WoodRuntimeTests.cpp WoodStreamingRuntimeTests.cpp
    WoodAmbience.cpp WoodCharacter.cpp WoodGameMode.cpp WoodGrounding.cpp
    WoodPreparedChunk.cpp/.h WoodRuntime.h WoodWorld.cpp WoodWorldStreaming.cpp
  TheWood.Build.cs  TheWood.Target.cs  TheWoodEditor.Target.cs
```

`WoodStreaming.h` is a **pure, engine-independent** header: settings, `plan()`,
`retained()`. `WoodWorldStreaming.cpp` is the Unreal adapter that consumes it.
That split is the project's central architectural decision — see
`Docs/BiomeGeneration.md`.

## Architecture decisions that constrain answers

- **Metres in the core, centimetres in the adapter.** The engine-independent layer
  is metres. `WoodWorldStreaming` converts. Keep the boundary explicit.
- **Ordered generation is a dependency rule, not permission to guess.** §9: regional
  planning → structural planning → terrain realisation → hydrology → habitat
  placement → presentation. Each stage consumes the previous; none may invent
  conditions that contradict terrain.
- **Determinism is over world coordinates, not completion order.** Random draws are
  `random(seed, gx, gy, salt)` on a global lattice. Chunk-order independence is a
  hard requirement.
- **Chunk size is 128 m.** It appears as three independent literals in the adapter
  (a known defect, see below) — treat any drift as a bug.
- **No hand repairs to a seed.** If a seed exposes a floating rock or blocked route,
  repair the rules and retest other seeds.

## Current implementation state

Implemented and tested: four biome families (temperate forest, dry grassland,
rocky highlands, taiga) on a warped hex lattice with smooth regional weights;
packed pointy-top hex cells at 950 m corner radius with 200 m edge bands;
asynchronous chunk streaming beyond the original sixteen-chunk benchmark;
procedurally generated ruins and discoveries.

**Not implemented, and must not be described as implemented:** irreversible
fresh-identity forgetting, save/resume, the fixed trailhead and occluded entrance,
climate families beyond the initial four, independent ruin/unreal probability
assignment, non-attacking wildlife, rain, natural audio, album browsing UI.

## Known defects in the streaming adapter

Found by audit 2026-10-07 (`docs` receipt `W01`). Relevant when touching
`WoodWorldStreaming.cpp`:

- **H1** — with a null pawn, `Stream()` centres on the world origin and unloads
  everything in one tick (`WoodWorld.cpp:129-131`, `WoodWorldStreaming.cpp:59-64`).
- **H2** — `EnsureTerrainAround` runs `WoodPrepareChunk` synchronously on the game
  thread: ~21k heavy samples per chunk, every boundary crossing.
- **H3** — background jobs recompute mesh attributes that line 49 discards.
- **H4** — a throwing background job escapes `Get()` before `Remove(Key)`, leaving
  the key permanently present: a crash loop plus permanently occupied job slots.
- **M4** — `retained()`, `Plan.removed` and `Settings::maxConcurrentJobs` have no
  runtime caller; three duplicated chunk-size literals.

## Honest-reporting requirement

`Docs/Specification.md` §11 and `Docs/Status.md` both state the repository must
not be represented as the completed game or as achieving 60 fps. §12 states that
a passing compile proves compilation and a passing terrain test proves only the
condition it exercises. Preserve that framing in any generated text, commit
message, or documentation.

## Toolchain reality on this machine

- **Unreal is reinstalling.** Do not attempt engine builds or editor automation.
- **No C++ compiler available.** `Tools/Test-Core.ps1` needs ziglang; MSVC Build
  Tools are absent. Report findings from reading code and say so explicitly.
- Blender 5.2 is available for asset work.
- `E:\Vivarium` holds a sibling project's procedurally generated flora — no mesh
  files, but reusable algorithms. See `Docs/clanker/WorkerBrief.md`.