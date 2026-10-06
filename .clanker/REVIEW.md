# Independent review — 2026-10-06

Scope: read-only review of the current generated forest/highland milestone against the human's exploration and visual-quality goals. Unreal/editor execution was reserved for the parent. Visual acceptance remains **pending**, because the expanded art has not yet been rendered for this review.

## Evidence

- Read current WoodGeneration, WoodAtmosphere, WoodWorld, WoodCharacter, runtime automation, BootstrapEditor, and renderer configuration.
- Ran Tools/Test-MSVC.cmd: passed, three habitat seeds generated approximately 59,600 features; shared-edge and repartition checks passed.
- Ran Tools/Test-Atmosphere.cmd: passed finite/bounded, continuous, reproducible weather and accelerated-time comparisons.
- Walking is configured at 420 cm/s, shallow wading at 280 cm/s. An actual runtime displacement assertion exists; its result must come from the parent's fresh Unreal run.
- No growth simulation was introduced. Lighting/weather core and material animation are intended to use shared accelerated game time.

## Findings to resolve or inspect

1. **High visual risk: fixed bright sky and ambient fill across regional night.** BootstrapEditor builds a constant unlit sky gradient, and WoodWorld keeps the ambient skylight at intensity 1. Regional cycles change rect-light brightness and temperature, but the sky remains daylight-colored. A seated observation render at substantially different times must establish whether the resulting night breaks the illusion. Dynamic sky brightness/color and ambient fill would close this gap if visible.
2. **Medium integration gap: modeled wind strength does not reach foliage materials.** WoodWorld samples Atmosphere.windStrength but never consumes it. Foliage does have time-driven movement and its own gust function; that provides motion but does not express the atmosphere model's changing wind. Avoid claiming weather-coherent wind until those are linked or independently demonstrated.
3. **Bootstrap failure risk: VertexColor output name.** Ground material custom input links VertexColor with output `RGB`. The earlier project notes report that the local Unreal Python binding needed the empty output name for that node. Verify actual execution rather than treating Python syntax success as material creation success.
4. **Visual acceptance needs human-scale rock grounding.** Rock transforms only yaw and place their base at one interpolated terrain point. On slopes this can expose floating edges or bury substantial rock portions. This is not a proven defect without the prepared meshes, but close-range hillside inspection is required before acceptance.

## What the source supports

The generated stream has downhill water levels, a continuous shallow bed, and a protected west-bank route. Habitat placement avoids the stream and reserves room for traversal. Features use world-coordinate candidates so chunk order and repartitioning are stable. Tree collision is deliberately limited to trunks instead of leaf cards. Sitting disables movement, retains free look, and gates 20x acceleration; standing clears acceleration. Photography requests exclude UI and save uniquely named files to the local album.

## Outstanding gate

Request fresh forest, stream, ridge, and accelerated seated screenshots, preferably across at least three seeds. Inspect canopy density/silhouette, texture repetition, leaf alpha/shadows, ground contact, water-bank fit, regional lighting boundary, and image stability. Verify a real saved photograph and fresh runtime movement/time tests. Do not label this a completed photographic environment or certify 1080p60 from core tests or an integrated-GPU editor capture.

## First expanded forest image review

Inspected `Saved/Review/12345-Forest-0.png`. Woodland structure and ground contact are visibly improved. No obvious terrain seam is visible; the central-left boulder appears grounded. This frame still fails photographic acceptance.

- The known gray/opaque leaf-card canopy is the primary defect and is already being replaced with an owned masked shader.
- Beyond that, the sandy-yellow floor is almost evenly illuminated beneath the trees. Limited contact/shadow contrast makes plants look placed on a broad flat carpet. Reassess after the leaf fix, then tune ambient/direct balance and darker forest soil/moss rather than only adding instances.
- Tree trunks and crown levels repeat strongly through the middle distance, giving a plantation impression. More varied mature/young cohorts and occasional irregular silhouettes would improve natural composition.
- Ground texture provides warm blotches but little convincing near-camera litter relief. Bare gaps need restrained fine-scale needles, twigs, moss, or equivalent surface variation.

Parent reports fresh walking, fog, and collision tests passing, plus dynamic sky/ambient and wind strength integration. Those changes supersede the earlier source gaps but still need image/time review; this reviewer did not independently execute Unreal.

Re-inspected the same forest path after the owned masked leaf shader and ground/light tuning. The opaque slab artifact is substantially resolved; canopy reads as finer actual foliage. No new hard seam, floating asset, or broken mesh appears in this frame. This is suitable as one frame of a meaningful user review build, provided the outstanding stream/ridge/time checks pass and the handoff does not claim photographic acceptance. Dark olive/brown needles can plausibly sit in shade; modest greener leaf grading is optional, while ground/contact-shadow balance remains the more consequential visual improvement.

## Final checkpoint verdict

Inspected `42-Stream-0.png`, `98765-Ridge-0.png`, and `12345-Forest-1650.png` alongside the daylight forest frame. **Suitable for a substantial user review build; photographic acceptance and performance certification remain open.** No hard terrain seam, detached floating rock, or clearly broken tree mesh is evident in these four stills.

The late forest frame visibly darkens both environment and sky while retaining readable nearby vegetation, resolving the earlier static-daylight concern. The stream is continuous in its visible reach and banks meet its surface without obvious holes. The highland frame shows an open, rock-strewn transition with different vegetation density.

Remaining material visual limits: water reads as a smooth, uniformly wide pale ribbon with clean geometric banks, rather than a natural stream; the ground remains bright and relatively flat in appearance with weak rock/plant contact shading; the ridge frame does not independently demonstrate a striking overlook, because its composition primarily shows nearby ground and a foreground boulder. These should guide the next visual pass after human feedback, not be hidden by a claim that the photographic gate has passed. Still screenshots cannot verify flowing motion, wind temporal stability, traversal, or frame rate.

## Subsequent four-family streaming source review

Fresh core generation tests and pure streaming-planner tests pass. No Unreal process was launched by this reviewer. Runtime streaming is independently implemented rather than using the tested pure planner, so those planner tests do not prove runtime residency behavior.

**Blocking correctness defect:** the resident chunks store `FPrimitiveInstanceId` returned by shared HISM `AddInstancesById`, then unload using those IDs after repeated `BuildTreeIfOutdated`. In installed UE 5.8 source, HISM `ApplyBuildTree` calls `MarkForRebuildFromLegacy`, which explicitly calls `ClearIdTracking(InstanceReorderTable.Num())` in its non-external branch (`Engine/Private/InstancedStaticMesh/ISMInstanceDataManager.cpp`, around line 975). The engine even marks restoration of ID tracking as TODO. Once any removal has swapped indices, subsequent rebuilds rebase identity tracking and other residents' stored IDs can identify different instances or become invalid. This can unload retained neighboring vegetation or leave stale foliage. Use chunk-owned instance components, plain ISM with preserved ID tracking, or explicit rebuild-safe bookkeeping, and test multiple unload/reload rounds with retained transform assertions.

**Correctness edge case:** `Realize` returns when full generation produces an empty features vector without setting `Detailed`. Such a valid chunk is repeatedly scheduled forever. Distinguish terrain-only realization from a completed full generation explicitly; emptiness is not unfinished work.

Lifetime review: asynchronous jobs capture a plain copied generator and coordinate, not actor/UObject pointers; discarding late results therefore appears safe. Terrain/water components remain GC-rooted through reflected arrays. Shared boundary heights, derivatives, and water row coordinates use consistent world inputs. Fixed world-space light tiles add their new distant row outside immediate light influence, so source does not show an unavoidable intensity jump on every 512m crossing.

Performance remains unverified: terrain realization still performs collision creation and substantial repeated climate/normal sampling on the game thread; generation is asynchronous but realization is not. Radius four plus two retention reaches up to 169 chunks and hundreds of thousands of retained instances. Actual movement frame-time measurements are needed, particularly during chunk completion, unload bursts, and accelerated sitting. The emergency current-chunk terrain realization can also block synchronously if the prefetch window is outrun or a developer teleport occurs.

### Streaming review resolution

The parent replaced shared HISM with ordinary ISM, which avoids HISM's legacy hierarchy rebuild/ID reset, and explicitly distinguishes terrain-only realization from completed detail. Full empty chunks can now become complete. The actual runtime scheduler now invokes the pure planner; preparation also moved normals, climate sampling, and root fitting into background work. Emergency realization and collision/instance insertion still occur on the game thread, so this does not constitute a frame-time certification.

Added `Wood.Runtime.RetainedVegetation` in the separately owned test file. It snapshots all original transforms in a retained chunk, moves the viewer three then four chunks east, waits for actual background placement, checks outgoing original vegetation is gone, and checks the retained features/counts/transforms remain identical through successive unloads. Parent reports fresh build and all four runtime tests passing, including this regression. These fixes resolve the identified ID and empty-state blockers for the current reproducible-streaming scope; irreversible forgetting remains deferred.

### Regional images

Inspected `12345-Grassland-0.png` and `12345-Highlands-0.png`. Terrain, ground appearance, and vegetation density visibly distinguish these regions. No definite mesh seam or floating asset appears. Grassland currently resembles sparse sandy steppe more than a lush grassland; highlands have denser rock distribution and darker gray soil. The shared pine asset library remains a variety limitation. A left-side highland rock has a particularly dark underside worth checking close up, but the still does not distinguish shadow/overhang from a contact defect. The grassland's very straight distant horizon should be checked during movement for exposed streaming-window edges; this still alone cannot prove one.

Inspected `12345-Roots-0.png` and `12345-Taiga-0.png`. The close tree has no definite visible air gap; the trunk appears seated. Its angular scanned-soil skirt and abrupt brown material edge are conspicuous, however, and should be removed, hidden, or blended in a later asset adaptation rather than treated as a proven grounding failure. Updated fog gives the forest substantially better distant depth. Taiga reads colder/darker and rockier than the temperate view, although shared tree silhouettes remain apparent; the large foreground boulder texture is soft at human scale.

**Current increment verdict:** review-ready for the human to assess four-family exploration, streaming, faster movement, and environmental observation. Identified streaming blockers have corresponding fixes and a passing regression reported by the parent. Photographic quality, continuous movement frame times, and final irreversible forgetting/save behavior are separate outstanding gates. Known art limits are scanned soil skirts, close rock texture quality, sparse sandy grassland cover, shared pine silhouettes, water/bank naturalism, and ground/contact lighting.

## Future hex/discovery specification review

Read BiomeGeneration.md and DiscoveryCatalog.md. The pointy-top axial/cube formulas are correct. A 950m corner radius gives 1,645m across flats, approximately 2.345km², and a 6.53-minute unobstructed crossing at 4.2m/s. A displacement Lipschitz constant below .25 makes the identity-plus-displacement map injective and invertible on the plane; amplitude caps alone would not, so including the derivative bound is appropriate. Radius-two enumeration is a conservative bounded neighborhood for the stated narrow transition widths. Canonical edge inputs, common influences, structural reservations, and final triangle grounding match the user's ordered terrain/water/habitat requirements. The catalog has 36 ruin and 40 natural concepts, explicitly not 76 owned assets or implemented features.

Implementation cautions to resolve before the relevant stages:

- Taking the minimum of six normalized affine margins and applying smoothstep yields continuous weights, but not generally continuously differentiable weights. At switches between minimizing edges, gradients can kink within the corner blend. Height or roughness modulation can consequently introduce normal artifacts despite continuous values. Choose a C1 edge combination or explicitly validate derivative seams; do not treat smoothstep alone as proof of smooth corner derivatives.
- Suitability fields plus symmetric neighbor compatibility do not yet define a bounded, deterministic family-assignment algorithm. Direct provisional-family queries plus one fixed refinement pass, or another explicit bounded construction, are needed before implementation; a recursive neighbor solver would violate the stated order-independent contract.
- Merged cells retain six neighbors per underlying cell, but a merged macroregion generally has more than six distinct neighboring regions. Clarify which topology the six-neighbor statement describes.
- Internal macro-catchment DAGs alone do not prevent cycles or elevation disagreement between macro-catchments. Cross-catchment outlet contracts need an explicit acyclic/elevation rule before broader hydrology is built.

These are implementation underspecifications, not evidence the current square-lattice runtime falsely claims the future design is implemented. The documents correctly preserve that distinction. Hydrology's constrained terrain adjustments before final collision commit are consistent with the required dependency order.

## Hex specification review resolutions � 2026-10-06

Parent addressed review findings: edge factors now multiply C1 smoothstep kernels rather than use a nondifferentiable minimum; family compatibility uses an explicit bounded one-pass formula over base neighbor probabilities; merged-region adjacency is distinguished from six-neighbor constituent cells; macro-drainage requires decreasing cross-basin potential and compatible elevations, with full potential construction separately designed before implementation. Numerical specification probes pass interior, midpoint edge, three-cell vertex, and 20,000 normalized nonnegative coverage samples. This is design validation, not an implemented hex generator.

Camera/plant follow-up evidence: editor target/content bootstrap completed; generation and biome suites pass; four runtime tests pass; forest capture inspected. Actual saplings and wider established-tree/understory scales are in the palette/generator. Camera override and project default disable motion blur.
