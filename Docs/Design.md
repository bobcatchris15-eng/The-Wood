# The Wood — accepted direction

This is a brief summary. [Specification.md](Specification.md) is the detailed game and development specification; [Status.md](Status.md) records implementation evidence and open acceptance work.

The game is a first-person, artistically believable wilderness for walking, observing, sitting and taking photographs. There are no required objectives, compass, map, combat or survival mechanics. Environmental sound, moving plants and flowing water carry most of its life; wildlife is occasional and aware without attacking.

Regions blend their terrain, climate, ecology, light and atmosphere. A typical region takes six to eight minutes to cross along walkable routes, with smaller habitats discovered along the way. Climate includes temperate and cold rainforest, taiga, icy hills, rocky highlands, prairie, savannah, swamp and open marsh. Physical temperature affects the environment rather than player health.

Light is local to regions, with independently progressing slow cycles, brightness and color temperature. No sun is visible or tracked as a celestial source. Light shafts and shadows must remain spatially convincing. Unreal regions occur in approximately one tenth of regions, independently of ruins in approximately one third. Impossible ecology is coherent, beautiful and occasionally unsettling.

Navigation is entirely landmark based. Visible terrain must stay consistent and reachable where traversal permits; walking up a ridge should reveal recognizable recent places behind the player. Distant regions are forgotten only beyond visibility and a local backtracking buffer. Saved games preserve the player and retained surroundings; photographs persist beyond forgotten places.

New journeys begin in a fixed generic gravel trailhead parking lot on a pleasant warm day, followed by a fixed entrance forest. An occluded, seamless threshold permanently removes access to that entrance while preserving immediate scenery. Returning through the passage leads into more wilderness. Resumed journeys start in their saved surroundings.

Photography is a single action from the current viewpoint, without UI in the result. Sitting retains free look and capture and optionally speeds the shared world clock. Standing restores normal time. Walking and shallow wading are sufficient; no dedicated climbing or swimming. Connected routes must exist between generated regions, while some individual cliffs and islands may remain inaccessible.

Development order: fully generated bounded visual benchmark; visual acceptance; runtime generation/forgetting/persistence; fixed entrance; broader climates and ruins/unreal variants; weather and wildlife. Unreal 5.8.3 with C++ is the starting engine architecture. Target 1080p60 on a recorded mainstream gaming reference. Assets are free first, with license provenance preserved. Visual quality and engine verification are gates, not assumed achievements.

