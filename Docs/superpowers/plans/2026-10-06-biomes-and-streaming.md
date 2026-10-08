# Biomes and continuous exploration implementation plan

> For agentic workers: use subagent-driven development for independent core, art and grounding work; root owns Unreal integration and runtime scheduling.

**Goal:** Keep walking into recognizably different, smoothly connected environments, with firmly planted trees.
**Architecture:** A deterministic regional field drives terrain, habitat, ground materials, light and atmosphere. An asynchronous chunk queue feeds a retained runtime neighborhood; global stable instance identifiers allow unloading without corrupting other chunks. Root placement fits real imported contact geometry to rendered terrain.
**Tech stack:** Unreal5.8.3, C++20 runtime, C++17 standalone tests, existing CC0/Blender/Python art pipeline.
**Spec:** Docs/Specification.md; user approved the current look and explicitly requested biome/generation expansion and a floating-tree fix.

## Constraints

Exploration only; no combat/survival/maps/compass, no tree growth, no visible sun. Keep C/right-click photography, E seating and optional T20× shared environmental time. Preserve generated placement, neighboring seams, stable nearby landmarks, actual walking and local backtracking. No hand repairs to a seed. Remain honest about photographic/performance acceptance and the integrated development GPU.

## Tasks and contracts

- [x] Root-contact regression: inspect prepared/imported roots, demonstrate old transform gaps against actual triangulated terrain, add WoodGroundedTransform and actual-mesh tests. Enable tree CPU access for contact extraction.
- [x] Regional generation: four initial families (temperate forest, dry grassland, rocky highlands, taiga), jittered region origins with continuous weights, environmental character, independent cycles and differing habitats. Preserve drainage and a connected traversable corridor. World::terrainHeight provides exact rendered triangle height. Test multiple seeds, remote coordinates, negative boundaries, biome differences and order independence.
- [x] Biome art: add licensed/checksummed grassland and rocky ground sets. Ground vertexRGBA are biome weights; UV0=(moisture,slope). Preserve explicit leaf masks, rooted wind and conventional LODs. Reuse pine art coherently for first conifer/temperate iteration.
- [x] Runtime streaming: replace fixed generate-all/clamp with near-first asynchronous chunk generation, bounded per-frame integration, collidable terrain ready ahead, retained backtracking margin and unloading. Keep global HISM components and per-chunk stable IDs; water patches share boundary inputs. Only UObject work runs on the game thread. Runtime state has explicit pending/loaded chunks and cancellation-safe task lifetime.
- [x] Lighting/visibility: stable world-anchored local area-light grid follows streamed coverage, with smooth field queries and no source jumps near the player. Atmosphere hides unloaded distance without conspicuous edges. Generate sufficient horizon terrain ahead of player view.
- [x] Verify: core tests, root regression red/green, Unreal walking/streaming/instance removal tests, biome/transition/root-close renders across seeds and remote positions, then independent review. Update current status/spec implementation notes.

## Deliberate scope

This iteration enables continuous reproducible generation and observable biome variation. Final irreversible forgetting/fresh regional identities and save/resume require their own durable-state implementation; they remain explicitly unimplemented until delivered and tested. Region scale starts from about1200m origin spacing, with actual six-to-eight-minute crossing tuned by routes. Rain, new wildlife, ruins and the entrance remain deferred.

## Dependency map

Regional core -> runtime chunk producer -> game-thread terrain/water/HISM realization.
Rendered terrain queries + imported root geometry -> grounding helper -> feature transforms.
Biome weights/moisture/slope -> ground shader; regional light/environment -> world-anchored lights/sky/fog/wind.
Runtime retained coverage -> safe player traversal and future persistence/forgetting.

Git-tracked repository; preserve prior assets and checkpoint source/evidence in place.
