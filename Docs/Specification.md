# The Wood — game and development specification

Version 1.1 · 6 October 2026

This document records the intended game, the first development milestone, and the rules that should guide later implementation. It consolidates the accepted conversation and development plan. It is a specification, not a claim that every feature is already implemented. Build evidence and current limitations belong in [Status.md](Status.md); hardware and asset provenance belong in [Hardware.md](Hardware.md) and [Assets.md](Assets.md).

Statements about the intended experience and acceptance gates are requirements. Values labeled current defaults describe today's implementation and may be tuned without changing that experience. Items explicitly deferred or unresolved are future work. The platform baseline is Windows desktop with keyboard and mouse.

## 1. The experience

The Wood is a first-person wilderness exploration game. The player walks into a forest, notices something interesting, goes to look at it, and keeps wandering. A stream, a ridgeline, a patch of strange fungi, or a half-buried building can be enough reason to change direction. The environment itself is the main attraction.

The world should be artistically real. Ground, plants, water, rocks, light, and distant terrain should look as though they belong together at human scale. Botanical accuracy is useful when it makes a scene convincing, but the game does not need strict species-and-soil simulation. A believable forest can gradually become too enchanted, too fungusy, or too dark to be entirely real.

There are no required objectives. Observation and optional photographs are sufficient activities. Sitting gives the player a way to stay with a place and watch it change. Discovery should come from attention and movement rather than icons, collectible lists, or instructions telling the player where to go.

### Experience pillars

| Pillar | Required effect |
| --- | --- |
| A place worth looking at | Close ground detail and distant composition both survive inspection. A photograph can stand on its own. |
| Continuous wandering | Forests, highlands, wetlands, and stranger places blend into neighboring regions without obvious tiles or scene changes. |
| Navigation by recognition | The player follows visible landmarks and can recognize recent ground when looking back. |
| Time visible in the environment | Light, cloud, mist, wind, and moving water make staying still worthwhile. Trees are already grown. |
| Quiet discovery | Ruins and wildlife provide occasional interest without becoming mandatory activities or threats. |
| A journey that moves onward | Local backtracking remains possible; sufficiently distant places eventually disappear and cannot be recovered through normal play. |

### Explicit non-goals

The game has no combat, hostile animal attacks, survival meters, temperature damage, mandatory quests, map, or compass. The first milestone has no caves, terrain overhangs, swimming system, or dedicated climbing. Tree growth is outside the intended simulation. Third-person presentation may be reconsidered later, but first person is the development baseline.

## 2. Player movement and observation

Movement should feel comfortable and responsive while leaving time to notice scenery. The player can walk, traverse modest slopes, step over small obstacles, and wade through shallow water. Ground collision must agree with visible terrain. Tree collision should primarily protect trunks; an enormous invisible canopy collision hull must not obstruct the forest.

Current tuning uses 420 cm/s on dry ground and 280 cm/s while wading. These are implementation defaults following feedback that walking was too slow, rather than permanent design constants. Movement speed, acceleration, camera height, field of view, and slope limits must be reviewed in play. Camera motion blur is disabled by default, including an explicit first-person camera override. The current camera field of view is 80 degrees; the current step height is 40 cm and walkable slope angle is 38 degrees.

| Action | Current default | Required behavior |
| --- | --- | --- |
| Walk | W, A, S, D | Move relative to facing without a required stamina system. |
| Look | Mouse | Free first-person look while walking or seated. |
| Photograph | C or right mouse button | One action captures the current view without interface elements. |
| Sit / stand | E | Sit on suitable ground; retain free look and photography. Standing restores ordinary time. |
| Accelerate observation | T while seated | Toggle accelerated passage of time for the shared environment. |

The seated camera transition should feel like settling down rather than teleporting. Sitting stops locomotion. It should not force the camera toward a feature or lock the player's view. Suitable seating on stones or other authored features is a later option; ordinary ground seating is enough for the first milestone.

Accelerated observation currently uses a 20× rate. It is optional and available only while seated. Standing cancels acceleration. The player should see the same place at a faster environmental pace: light changes, clouds and mist develop, foliage moves, and water continues to flow. There is no requirement to watch trees grow or vegetation recolonize a cleared patch.

## 3. Photography and the album

Photography is immediate and optional. Taking a picture does not enter a separate composition mode or require a shutter menu. Capture the rendered viewpoint without HUD, debug text, or interface elements. The player can photograph while standing or seated.

Photographs persist locally even after the photographed place has been forgotten. The current implementation writes PNG files to `Saved/Photos`, with unique timestamp-and-identity filenames. This folder is the initial persistent album; an in-game gallery is a deferred presentation choice, not an accepted requirement for the first milestone.

Capture must avoid accidental overwrites and handle rapid repeated input without issuing overlapping requests. Failure to create or write the album must be detectable. Validate actual written images rather than treating a successful screenshot request as proof of a saved photograph. Capture costs must be included in frame-time profiling.

## 4. Regions, habitats, and scale

The next regional layout uses efficiently packed hexagonal ownership cells with natural warped boundaries and blending concentrated near edges. [BiomeGeneration.md](BiomeGeneration.md) specifies coordinates, dimensions, shared boundary contracts, weights, ordered generation, discovery placement, streaming and validation. [BiomeCatalog.md](BiomeCatalog.md) lists ordinary families and unreal variants. [DiscoveryCatalog.md](DiscoveryCatalog.md) lists planned ruins, intact structures, unexplained artifacts, geological/ecological discoveries and reusable prop kits. Eras and genres can mix freely, and intact or anomalous discoveries may appear in ordinary biomes. Those documents define intended next work; the current runtime now uses the initial hex ownership and edge-blend foundation; the broader systems remain future work.

The landscape is built from regions with smaller habitats inside them. A region has an origin, an extent, broad environmental characteristics, and influences from its neighbors. Its identity emerges from those inputs rather than from placing a fixed rectangular biome template.

A typical region should take roughly six to eight minutes to cross along an available walking route. This is travel time, not a fixed square size. At the current unobstructed walking speed, that would correspond to approximately 1.5–2 km of route, but slopes, bends, observation, and terrain interruptions change the actual distance. Region size should be tuned using traversed routes and playtests. The initial bounded benchmark is intentionally smaller and does not establish final region dimensions.

Regional inputs should cover at least:

- Origin, extent, neighbors, and stable generation identity.
- Environmental temperature, moisture, exposure, shelter, and prevailing wind character.
- Terrain roughness, broad elevation, ridge and ravine character, and drainage.
- Ecological character: canopy openness, vegetation density, ground cover, and suitable habitat families.
- Lighting cycle phase, rate, brightness range, and color temperature range.
- Ruin eligibility and unreal character, with separate decisions for each.

Environmental temperature shapes scenery, weather, and ecology. It does not impose survival mechanics. Light color temperature is a separate artistic and atmospheric variable.

The agreed climate range includes temperate forest, old-growth temperate forest, cold rainforest, other rainforest, taiga, icy hills, rocky highlands, prairie, open savannah, swamp, and wide-open marsh. Streams may be gentle forest channels or fast rills across rocky highlands. These families should be introduced incrementally after the visual foundation works.

Neighboring regions blend their conditions. A drier savannah may transition northward into rougher rock country while an eastward route enters older temperate woodland. Boundaries must not become abrupt changes in soil, tree arrangement, fog, exposure, or water elevation. Smaller wet pockets, clearings, sheltered hollows, and rock gardens provide interest within the broader region.

## 5. Unreal places, ruins, and wildlife

Approximately one tenth of regions may receive unreal character. Approximately one third may contain a ruin. These assignments are independent: a place can be ordinary with a ruin, unreal without one, both, or neither. The proportions are generation defaults across many regions, not a quota forcing exactly one ruin into every three adjacent regions.

An unreal region should have a coherent change in ecology or atmosphere. Possible directions include excessive fungi, implausible canopy forms, unusual color relationships, heavy darkness, or enchanted light. It still needs convincing ground contact, spatial depth, material behavior, and a readable route. Unreal character does not excuse disconnected meshes or repeated patterns.

Ruins vary substantially in scale, architectural family, material, damage, burial, and overgrowth. Small fragments and larger recognizable structures should both be possible. Their placement accounts for terrain and water: foundations meet the ground, access makes spatial sense, and erosion or vegetation follows the ruin's particular history. Large ruins are deferred until the initial natural environment passes review.

Wildlife is occasional. Examples include raccoons, armadillos, snakes, deer, bears, fauna from other continents, and stranger creatures in selected unreal regions. Habitat suitability should guide encounters. Animals can notice, watch, retreat, or warn; they do not attack. Their behavior supports observation rather than combat or resource harvesting. Species selection, encounter frequency, animation sources, and detailed behavior remain later implementation choices.

## 6. Lighting, weather, water, wind, and sound

Regional lighting cycles progress independently and slowly. There is no visible sun and no requirement to track a shared celestial sun direction. Regions vary in brightness and light color temperature. Light shafts and shadows must remain convincing within the scene even though they do not expose a literal solar disk.

The first milestone must demonstrate two independent regional cycles and a blended boundary. Crossing it in either direction should not cause an abrupt exposure jump, shadow discontinuity, or sudden color shift. Regional differences should be visible without making neighboring parts of the same scene look disconnected.

Weather changes over time and responds to regional character. The current development pass explores cloud, mist, and gust changes before a complete rain or snow system. Weather should affect visible light, atmosphere, wind, and eventually sound coherently. All environmental animation must use a consistent simulated time basis so acceleration and pause do not leave parts of the world running at unrelated rates.

Water follows terrain and drainage. Channels connect across generated boundaries. Streambeds, banks, pools, wet ground, and vegetation should agree about where water is. Moving surface detail must read as flowing water rather than a stationary blue ribbon. Full fluid simulation is not required; a convincing authored shader and terrain-aware surface can satisfy the initial visual goal.

Wind moves leaves, grasses, and other flexible plants without moving rooted bases. Nearby vegetation should respond to related gusts rather than unrelated random shaking. Water and windblown plants are the principal continuous sources of visible life. Sound should reinforce them, with spatial stream sound and foliage ambience appropriate to location; audio implementation is still part of the visual-foundation work.

## 7. Navigation, streaming, and forgetting

Navigation is landmark based. The player sees an interesting ridgeline, walks toward it, and can look back to recognize the place they came from. Terrain, silhouettes, and discovered features should support that recognition. Visible landmarks must remain consistent and reachable where the terrain permits; the system must not show a mountain and replace it before the player arrives.

The eventual world generates ahead of travel and retains nearby geography. Distant regions can be removed only after they are beyond both relevant visibility and a local backtracking buffer. Forgetting is part of the journey, but immediate surroundings must remain stable. Individual cliffs or islands can be inaccessible; connected walking routes between regions must remain available.

Generation uses reproducible seeds for debugging. In normal endless play, forgotten regions receive fresh identities rather than reappearing from the same location seed. The player cannot recover a discarded place merely by walking back to old coordinates. The exact visibility envelope, retention distance, identity allocation, and travel-speed-dependent generation budget require later implementation and testing.

Save/resume preserves the player, retained world, observation state, and pending generation identities sufficiently to restore the same immediate surroundings. An interrupted generation task must not create a different seam or replace a recognizable landmark on resume. Photographs persist independently of world retention.

## 8. The beginning of a journey

Every new journey begins at the same generic gravel trailhead parking lot on a pleasant warm day. A fixed beginning forest leads toward the generated wilderness. This familiar opening establishes scale and mood before variation takes over.

An occluded passage conceals the irreversible threshold. Crossing it preserves immediate geometry and continuity while removing the route back to the entrance. Returning through the passage leads into further wilderness. This should feel like continuing through a place, without an obvious loading screen or unexplained scene replacement.

New journeys restart at the trailhead. Resumed journeys restore saved surroundings. The trailhead, opening forest, and threshold are deferred until generation, retention, and persistence can support them reliably.

## 9. Engine and generation architecture

Use Unreal Engine 5 with C++ for generation, scheduling, and world state. The installed development baseline is Unreal 5.8.3, changelist 58210709; the project targets the 5.8 release. Record patch changes and retest rather than silently moving the baseline. Experimental rendering features must not be mandatory for the game to function.

Unreal data assets provide palettes and authorable parameters. Materials, Blueprints, and PCG may provide authoring and presentation. Their use must preserve the shared generation model; a presentation system must not independently invent drainage or vegetation conditions that contradict terrain. PCG is an available authoring tool, not a requirement that every placement run through a PCG graph.

### Ordered generation responsibilities

| Stage | Produces and consumes |
| --- | --- |
| 1. Regional planning | Establish origins, extent, climate, terrain and ecological character, neighbor influences, and shared boundary constraints. |
| 2. Structural planning | From regional inputs, define broad elevation, drainage, ravines, ridges, outcrop footprints, and reserved feature sites. |
| 3. Terrain realization | Construct continuous ground around structural features, fit rock geometry, and retain traversable connections. |
| 4. Hydrology | Realize channels and pools, refine streambeds and banks, and expose water depth and wetness information. |
| 5. Habitat placement | Use terrain, water, slope, moisture, exposure, shelter, and available space to place vegetation and surface detail. |
| 6. Presentation | Apply lighting, weather, wind, sound, and eventually wildlife using the same environmental state. |

Ravines and outcrop placement influence ground construction. Water accounts for ground and rocks. Trees and plants account for terrain and water. This ordering is a dependency rule, not permission for each stage to guess its own incompatible landscape.

Shared interfaces consist of regional descriptions, boundary constraints, terrain/habitat queries, and generated feature records. The current engine-independent core uses metres; the Unreal adapter converts to centimetres. Keep that unit boundary explicit.

Initial terrain is a chunked heightfield with fitted rock geometry. Shared edge inputs must produce identical terrain and waterways regardless of chunk generation order, including negative coordinates. Random choices must derive from stable identities or coordinates rather than the order tasks happen to finish. Large-coordinate precision and origin management are later streaming concerns that must be resolved before truly long journeys.

The runtime adapter realizes procedural meshes and collision, instanced assets, stream surfaces, and local atmospheric presentation. Regional family planning and asynchronous chunk streaming are now under development and validation as described in Section 13. Persistent retained-world saves and irreversible forgetting remain future work. Do not describe traversal streaming as the completed endless journey.

## 10. Assets and visual construction

Use free assets with suitable redistribution rights. Preserve source URLs, license records, and checksums. CC0 sources are the current preference. Blender is available for mesh adaptation and Gimp for texture work; Inkscape is available when vector authoring is useful. Tool availability does not require making every asset from scratch.

Artist-authored assets, generation rules, and composition templates are allowed. Manually placing scenery to repair a particular seed is not. If a seed exposes a floating rock, blocked route, or empty forest, repair the rules or asset preparation and retest other seeds.

The asset pipeline must verify scale, ground-contact pivots, normals, alpha masking, wind weights, collision, material compatibility with instancing, and distance detail. Ground textures need variation at multiple scales so tiling does not dominate photographs. Rocks should meet terrain convincingly; vegetation should have plausible spacing and rooted bases. Distance simplification must preserve recognizable silhouettes without distracting popping or unstable thin foliage.

The current source library comes from Poly Haven, with manifests and adapted variants documented in [Assets.md](Assets.md). Mature canopy, ferns, grass, textured forest floor, and larger mossy rocks are being used to replace the earliest sparse diagnostic scene. The presence of imported assets does not itself establish visual acceptance.

## 11. Delivery sequence and acceptance gates

### Milestone 1 — a generated place worth exploring

Create a bounded environment with multiple seeds, continuous routes, a temperate forest adjoining rocky highlands, outcrops, a connected stream, and an overlook. Generate environmental placement from inputs. Include close ground detail, coherent wind, convincing banks, atmospheric depth, and sunless lighting.

Provide movement, shallow wading, modest slope traversal, seating with free look, instant photography, and a persistent local album. Demonstrate two independently progressing regional light cycles and their blended boundary. Accelerated sitting must affect the shared environment and standing must restore normal time.

Review the scene while walking, sitting, looking close to the ground, looking across distance, and taking photographs. Check several seeds for floating assets, seams, repeated arrangements, blocked routes, collision problems, and broken water connections. Wildlife, large ruins, the opening trailhead, and endless streaming remain deferred until this environment passes the visual gate.

### Milestone 2 — continuous generation and forgetting

Generate ahead asynchronously, retain nearby and visible geography, preserve reachable landmarks, and discard distant regions beyond the backtracking buffer. Save retained state and pending identities. Validate travel in multiple directions, local returns, distant views, repeated forgetting, interruption, and save/resume.

### Milestone 3 — the complete entrance

Add the fixed parking lot and entrance forest. Implement and inspect the occluded irreversible passage. Verify that immediate scenery survives crossing, the old entrance cannot be recovered, a new journey restarts correctly, and a resumed journey restores its surroundings.

### Milestone 4 — broader places and discoveries

Add climate families incrementally. Tune six-to-eight-minute region crossings using actual routes. Introduce terrain-aware ruins, varied architecture, damage and overgrowth, and coherent unreal ecology. Audit ruin and unreal probabilities independently across many generated regions.

### Milestone 5 — environmental life

Expand changing weather and introduce occasional habitat-appropriate wildlife. Validate observation, noticing, retreat, and warning without attacks. Add stranger creatures selectively in unreal regions. Early cloud and mist work may support Milestone 1 without implying completion of this broader milestone.

## 12. Validation and performance

The performance target is 1920×1080 at 60 fps on a recorded mainstream gaming PC. Record CPU, GPU, RAM, driver, engine patch, resolution, scalability settings, and relevant rendering options. Acceptance uses packaged builds and measured frame times, including movement, generation, photography, and accelerated observation. Average frame rate alone is insufficient when frequent generation or capture stalls interrupt exploration.

The current development machine has a Ryzen AI 7 PRO 350, integrated Radeon 860M, and 32 GB RAM. It is a development reference, not a certified mainstream gaming baseline. Editor startup, offscreen rendering, and automated test passes cannot certify the performance target.

Validation layers should include:

- Engine-independent tests for deterministic queries, generation order, shared edges, habitat constraints, and observation time state.
- Unreal integration checks for collision, grounded movement, actual travel distance, seated time restoration, material/import behavior, and written photographs.
- Visual inspection across seeds and viewpoints, including both directions through regional boundaries.
- Packaged-build frame-time profiling with density, shadow, and detail-distance adjustments supported by measurements.
- Later retention, persistence, entrance, and long-distance consistency tests.

A passing compile proves compilation. A passing terrain test proves the condition it exercises. Neither proves a convincing forest. Expansion should wait when the current scene still exposes repeated patterns, poor ground contact, broken alpha, abrupt lighting, unstable foliage, or obvious water seams.

## 13. Current scope and unresolved decisions

### Four-biome streaming development update — 6 October 2026

Following the original bounded review checkpoint, implementation is expanding to four smoothly blended families: temperate forest, dry grassland, rocky highlands and taiga. Shared regional weights use a 1,200 m lattice and now drive four-family ground material treatment. Current streaming schedules nearby 128 m chunks first, allows two asynchronous value-generation jobs, requests a radius-four neighborhood of 81 chunks, and retains a radius-six buffer of up to 169 chunks. The original walking clamp is removed; terrain under the player is protected. Stable instance identities, terrain-footprint root fitting, regional grid lights and viewer-relative sky support this lifecycle. Sapling meshes now provide a separate young-tree cohort alongside a broad distribution of intermediate and mature sizes; understory plants vary in size too. These are static maturity choices, not a tree-growth simulation.

This iteration is still being validated. Unloaded places currently regenerate reproducibly when revisited. It does not implement irreversible fresh-identity forgetting or save/resume. Final retention tests and current rendered review remain pending; earlier bounded screenshots are not evidence that the new streaming or biome blends are visually accepted. These implementation defaults do not replace the full journey requirements above.

The previous bounded 512×512 m review checkpoint comprised sixteen 128 m terrain chunks, mature canopy, habitat placement, textured ground, larger rocks, coherent wind, and observable atmospheric time. Its generation and atmosphere tests, Unreal runtime automation, and actual photograph output were verified; several seeded viewpoints were inspected. Photographic quality, complete interactive play, and packaged-build performance acceptance remain open. Refer to dated build and review evidence for precise checks and remaining limitations.

Decisions still requiring implementation or review include the final mainstream reference PC; final movement tuning and accessibility settings; album browsing UI; detailed audio production; weather precipitation; final regional schema and blending widths; long-distance coordinate strategy; retention and visibility budgets; save format; ruin architectural families; wildlife asset and behavior selection; and whether third person ever adds enough value to justify support.

These open choices should be resolved in the relevant milestone. They do not block the agreed first-person visual foundation, and they do not add tree growth, combat, survival, or compulsory objectives to the scope.
