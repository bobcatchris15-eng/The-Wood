# The Wood

Unreal Engine 5.8.3 C++ project for a first-person procedural wilderness. **Current work: four smoothly blended biome families and asynchronous terrain streaming beyond the original benchmark. Validation is ongoing; photographic quality and packaged performance remain open gates.**

Read [the detailed specification](Docs/Specification.md) for the intended game, architecture and acceptance criteria. [Implementation status](Docs/Status.md) records what is verified now.

Double-click `Tools/Play.cmd` to try the prototype on this machine. The launch uses the recorded Unreal 5.8 installation and opens a 1080p window. First-run shader preparation can take time.

## Setup

1. Install Unreal Engine **5.8.3** through Epic Games Launcher. Install only Windows/core components initially; omit debug symbols and unused target platforms. Record the exact patch version used.
2. Microsoft Visual Studio 2022 Build Tools with the C++ workload and Windows SDK are installed on the development machine.
3. From this directory, run:

```powershell
./Tools/Build-Unreal.ps1 -EngineRoot 'C:/Program Files/Epic Games/UE_5.8' -InitializeContent
```

This compiles the editor module and creates the benchmark map, authored materials and palette, and imports prepared CC0 models. Bootstrap regenerates owned materials and explicitly migrates the palette to the current asset version. Open `TheWood.uproject`, open `/Game/Maps/VisualBenchmark`, and press Play. Build/bootstrap were validated with Unreal 5.8.3 on 2026-10-06.

## Controls

WASD: walk. Mouse: look. C/right-click: photograph. E: sit/stand. T: toggle 20× observation time while seated. Standing restores normal time. Current speed is 4.2m/s on land and 2.8m/s while wading. Photos exclude UI and persist in `Saved/Photos`.

Trees remain mature. Seated observation advances regional light, mist, cloud movement, foliage wind and water animation together.

Use `-WoodSeed=42` on the Unreal command line to select a seed. The current generator blends temperate forest, dry grassland, rocky highlands and taiga on a warped hexagonal regional lattice (950 m corner radius), with 200 m edge-transition bands. Ground materials follow the same regional weights. The original walking-boundary clamp is removed. Streaming requests nearby 128 m chunks first, runs up to two value-generation jobs asynchronously, and retains an outer buffer while the player travels. Unloading and revisiting currently reproduces the same seeded geography; irreversible forgetting and save/resume are deferred.

The starting position is around (-180, -180) metres. For the current development layout, dry grassland influences lie east near (930, -120) and north near (-80, 1040), rocky highlands northeast near (1080, 1130), and taiga south near (-100, -1410). These are regional blend centers, not exclusive biome boundaries or in-game navigation instructions.

## Tests and assets

```powershell
./Tools/Test-MSVC.cmd
./Tools/Test-Atmosphere.cmd
./Tools/Test-Unreal.ps1
# Alternative isolated compiler:
python -m pip install --target .cache/toolchain ziglang==0.13.0
./Tools/Test-Core.ps1

# Rebuild downloaded/prepared source art:
./Tools/Fetch-Art.ps1
& 'C:/Program Files/Blender Foundation/Blender 5.2/blender.exe' --background --python Tools/Prepare-Art.py -- C:/Misc/The-Wood
```

Generation tests cover edge continuity including negative coordinates, seed/order consistency, grounded placement, habitat exclusions, downhill shallow water, a walkable bank route, light interpolation, and seated observation time.

See [hardware](Docs/Hardware.md), [asset records](Docs/Assets.md), and [milestone status](Docs/Status.md).

## Visual limitations

The current palette contains three mature pine variants, four ferns, ten grass variants and fourteen rocks, with rooted wind and distance LODs. Four biome families share this limited asset library; richer species and climate-specific art remain necessary. Ground/contact shading, stream-bank detail, water depth appearance, tree variety and atmospheric polish still need work. The sky has no visible sun. Mist, cloud cover and wind vary; rain and a soundscape are not implemented. There is no album interface or finished settings menu.

Earlier forest-foundation review renders across three seeds and an altered lighting state are in `Saved/Review`. They do not validate the current streaming iteration. Run `Tools/Render-Review.ps1` to reproduce a supported view. Editor captures do not certify packaged performance.

Asynchronous streaming is under validation. Irreversible world forgetting, persistence, the entrance threshold, broader climate content, ruins and wildlife remain deferred. This repository must not be represented as the completed game or as achieving 60 fps.


Detailed generation design: [hex biome cells and boundaries](Docs/BiomeGeneration.md), [discoveries and prop kits](Docs/DiscoveryCatalog.md). These are specifications for the next generation stage; the current build now implements initial hex ownership and edge weights; full climate selection and boundary planning remain future work.

Expanded design catalogs: [biomes](Docs/BiomeCatalog.md) and [ruins, intact structures and unexplained artifacts](Docs/DiscoveryCatalog.md). Discoveries can mix eras and genres, including anomalies in ordinary biomes.
