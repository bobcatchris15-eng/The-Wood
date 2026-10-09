# Forest art library

Powered by [Poly Haven](https://polyhaven.com). Every source is [CC0](https://polyhaven.com/license). `Tools/Fetch-Art.ps1` downloads the API's 1k glTF models (rocks: 2k glTF, falling back to 1k with a warning) and 2k JPEG ground maps and verifies every file against the API MD5. `ArtSource/manifest.json` preserves source URLs, licensing and checksums. Downloaded and prepared sources currently occupy about 1.3GB.

The canopy uses three [pine_tree_01](https://polyhaven.com/a/pine_tree_01) variants, 14.88–20.37m tall and 7.2–8.3m across. Blender preserves the original bark, trunk and branch geometry and replaces the original 4.1–6.8 million triangle needle geometry with deterministic masked atlas cards at source needle sites. Each crown has 4,200 crossed tuft pairs (16,800 triangles); total trees contain 88,166–129,502 triangles. The original whole-tree collapse prototype removed foliage and damaged roots, so it was replaced before visual acceptance. Pivots sit at the trunk's ground contact, rather than the canopy bounding-box center. Trees remain mature; wind animation does not simulate growth.

Ground uses four CC0 2k material sets, each with base color, DirectX normal and roughness: [forest_floor](https://polyhaven.com/a/forest_floor) for temperate leaf litter, [withered_grass](https://polyhaven.com/a/withered_grass) for dry straw/soil, [gravel_ground_01](https://polyhaven.com/a/gravel_ground_01) for gray mineral highlands, and [forest_ground_04](https://polyhaven.com/a/forest_ground_04) for cold dark taiga soil with twigs and sparse stones. Grassland does not sample the broadleaf-litter texture; highlands desaturate the mineral texture toward gray. Taiga applies a darker cool tint and muted moisture-driven moss variation without initial snow.

The ground material is `/Game/Wood/M_Ground_BiomeV1`; the palette points to it while mature art imports remain on CanopyV3. Terrain vertex RGBA encodes normalized weights in order TemperateForest, DryGrassland, RockyHighlands, Taiga. UV0 encodes `(moisture,slope)`; it is habitat data, not the texture projection. Custom inputs are `W=Vertex RGB`, `T=Vertex Alpha`, `H=UV0`, and `P=WorldPosition`. Four differently rotated world-space tile scales (2.7m, 2.2m, 3.6m and 2.3m) and coarse variation reduce repetition. Albedo, normals and roughness blend continuously across biome weights. Moisture above 0.55 darkens and slightly smooths soil toward wet stream banks; steeper slopes expose more mineral ground. Normal detail uses a world-space surface basis derived from position derivatives, so habitat UVs cannot rotate the terrain normal map. The shader uses 12 texture samples. The opaque stream material retains moving normal ripples and subtle water color variation; it is a surface shader, not fluid physics.

Boulders use [boulder_01](https://polyhaven.com/a/boulder_01), [rock_moss_set_01](https://polyhaven.com/a/rock_moss_set_01), and [rock_moss_set_02](https://polyhaven.com/a/rock_moss_set_02). Their 14 variants have a normalized maximum horizontal span of 1m, so instance scale 1.5–4.5 yields boulders 1.5–4.5m across. Their texture detail and moss come from the sources. Rock sources use the Poly Haven 2k glTF set (`Resolution=2k` in `ArtSource/manifest.json`) so close-up surfaces stay sharp; rock materials should report max texture dimension 2048 in the BootstrapEditor `ROCK_TEX` log lines. Verified 2k glTF MD5s: rock_07 `903924785f3c43703b77ffd692897814`, boulder_01 `3ef4b3c88c898e12b096eeb40f1edbb9`, rock_moss_set_01 `c45cebb55c848a11233126f691557ca0`, rock_moss_set_02 `6161594df6870389d65b7d95fa6461b0`. Rock meshes are force re-imported into `/Game/Art/PolyHaven/CanopyV4` and their instance materials are copied under `/Game/Wood/RockMaterials/*_CanopyV4_2K`. `rock_01` was rejected because its glTF is a material-preview sphere, not a natural rock mesh.

The prepared library contains 99 GLBs (`ArtSource/Prepared/*.glb`, counted after the species decimation run): three mature pines, three saplings, four ferns, seventeen grasses, one original pebble, one boulder and thirteen moss rocks. `ArtSource/Prepared/inspection.json` records dimensions and triangle budgets. Saplings and the original pebble stay available as source library assets; the review palette uses mature canopy, larger rocks and ten meaningful grass variants, excluding fragments with horizontal spans under 15cm.

Foliage wind uses a dedicated UV1 mask generated from final mesh height, zero in the bottom 8cm and increasing toward the crown. Tree weighting is quadratic. Needle cards use the source twig diffuse atlas and the separately downloaded, checksum-verified alpha PNG, exported as glTF MASK with cutoff 0.35 and double-sided shading. Source sampling preserves irregular branch layers and taper. The shader keeps roots still; it applies bounded horizontal motion to copies of imported project materials and preserves texture, alpha-mask and shading connections. It does not modify engine materials. Automatic lightmap UV generation is disabled for these dynamically lit meshes to preserve UV1. `WindStrength` is a weather multiplier; `SkyBrightness` controls the two-sided sunless sky gradient. `CloudCover` adjusts smooth, slowly drifting analytic wisps with the same game clock. All animated material Time nodes use game time (`ignore_pause=False`) so pause/time dilation follow the runtime clock.

`Tools/BootstrapEditor.py` imports to versioned `/Game/Art/PolyHaven/CanopyV3` destinations and explicitly migrates the palette, replacing the obsolete sapling-only canopy. Ground and water are versioned project materials; the runtime's fixed `/Game/Wood/M_Sky` asset is rebuilt as a two-sided emissive gradient. Imported foliage parents and instances are copied under `/Game/Wood/FoliageWind` before adding wind. The bootstrap should be run by the editor integration owner; Python syntax checks alone do not verify Unreal shader compilation or imports.

Needle cards use an explicitly authored project material, `M_Needles_CanopyV3_Masked1`, to bypass the imported glTF master's opaque blend behavior. The bootstrap extracts the unchanged combined RGBA atlas embedded in the GLB, preserves texture alpha, and connects RGB directly to base color and Alpha directly to Opacity Mask. It uses MASKED blending, two-sided foliage shading, cutoff 0.35 and modest subsurface transmission. The extracted atlas has alpha values 0–255; 70.4% of the selected tuft rectangle is transparent at the cutoff. This direct material keeps the original UV0 atlas layout and UV1 wind mask.

The bootstrap authors conservative distance LODs with UE5 `StaticMeshEditorSubsystem.set_lods`. LOD0 stays at 100%; trees get 65%, 35% and 18% levels, while grasses, ferns and rocks get 50% and 20% levels. The final tree LOD targets about 15,870–23,310 triangles. Tree screen thresholds are 0.45, 0.18 and 0.065; undergrowth thresholds are 0.08 and 0.018, and rock thresholds are 0.15 and 0.04. The subsystem copies mesh build settings from LOD0, preserving the wind UV channel. A per-mesh metadata version makes subsequent runs reuse authored LODs. These are conventional distance LODs; Nanite settings are not changed.

Tree meshes enable CPU access before builds/saves, including existing sapling assets, so packaged runtime grounding can probe the low-root vertex footprint. This flag does not modify mesh geometry, transforms or pivots.

Prairie grass candidates are two CC0 Poly Haven 1k glTF models: [grass_bermuda_01](https://polyhaven.com/a/grass_bermuda_01) (glTF MD5 `a1bdd74118d2387a42dba4f605226f87`, 21 variants, 2–8cm horizontal spans per fragment) and [grass_medium_02](https://polyhaven.com/a/grass_medium_02) (glTF MD5 `dd8f166a6399238553bc3b2931677b68`, 5 variants, 0.12–0.43m across, 0.4m tall at most). Both are prepared by `Tools/Prepare-Art.py` into `ArtSource/Prepared`. Neither source clump reaches the 0.6m prairie footprint on its own; the grassland prairie slot must scale or assemble clumps before this is accepted. Blender's exporter reports multiple image-sampler warnings on source materials. All 42 GLB headers, UV1 weight ranges and source MD5 checksums passed verification, and the mature canopy silhouette was rendered in Blender. The initial Unreal import and material bootstrap passed in UE5.8.3. The corrected CanopyV3 cards, distance LODs and final rendered appearance are verified by the editor integration owner. Runtime trunk-only tree collision must be supplied by the world adapter; glTF imports do not provide a trustworthy collision hull. Native Unreal `.uasset` files are project content; preserve manifests even when excluding source downloads from a future Git repository.

## Entrance zone props (prop_00..prop_03)

All four are CC0 Poly Haven 1k glTF sources, fetched by `Tools/Fetch-Art.ps1` into `ArtSource/PolyHaven/<id>/` and verified against the API MD5. Every file (`.gltf`, `.bin`, textures) has its own MD5 in `ArtSource/manifest.json`. The glTF MD5s are listed below. `Tools/Prepare-Art.py` (`build_props`) joins each source to one mesh, scales it to real-world metres, sets the origin at base centre, keeps the source orientation (+Y forward as imported), and exports `ArtSource/Prepared/prop_0N.glb`. Dimensions are in `ArtSource/Prepared/inspection.json`.

| Prop id | Source | Source URL | glTF MD5 | Target | Output MD5 | Output dims (X x Y x Z, m) |
|---|---|---|---|---|---|---|
| prop_00 signboard | standing_chalkboard_01 (Standing Chalkboard 01), CC0-1.0 | https://polyhaven.com/a/standing_chalkboard_01 | 7cdb491ebdea655db8402f7d6fc817c6 | height 2.0 m | 6398478c4d768f7575a86116d23dbda6 | 1.22 x 1.01 x 2.00 |
| prop_01 picnic table | wooden_picnic_table (Wooden Picnic Table), CC0-1.0 | https://polyhaven.com/a/wooden_picnic_table | 6da01f8a75e559f356b494059f7b0eda | native scale (1.0) | 5bf7275eb1bd3236fc302d06afd2c07b | 2.24 x 3.02 x 0.75 |
| prop_02 bin | metal_trash_can (Metal Trash Can), CC0-1.0 | https://polyhaven.com/a/metal_trash_can | c322802832a61ad7b17711dfbbc52e6b | height 1.0 m | fdeb92b17335a52100c6d20f69355a40 | 0.86 x 0.61 x 1.00 |
| prop_03 fence segment | modular_chainlink_fence (Modular Chainlink Fence), CC0-1.0 | https://polyhaven.com/a/modular_chainlink_fence | 8c8f0c91cf48ba68fb32178bcbd6351a | longest horizontal 4.0 m | 97ec8c945abd55ba05a758eefdcc6d68 | 4.00 x 1.06 x 1.24 |

Notes on the picks:
- No fallbacks were built. Every id matched a Poly Haven model by name and tags.
- prop_00 is a standing chalkboard, not a wooden board. prop_03 is galvanised chainlink, not wood. Both are CC0 and were chosen for shape and name. Swap them if the entrance needs wood.
- prop_01 is at native scale (1.0). The source is already real-world size: 3.02 m long, 2.24 m wide, 0.75 m tall.
- The native chainlink segment is 8.1 m long and 2.5 m tall. At 4 m long it is about 1.24 m tall.
- prop_02 keeps one clean can from metal_trash_can: the body, lid and handles, with the rust variant dropped. It is scaled uniformly to 1.0 m tall. Body footprint is about 0.61 m. Handles extend the X span to 0.86 m.
- prop_00 through prop_03 have no wind UV (they are not foliage).

### Gravel022 (ground texture, from the Vivarium project)

`ArtSource/Textures/Gravel022/` holds three files copied byte-for-byte from `C:\Misc\Vivarium\game\Textures\`. They were not fetched by the script. Original source: ambientCG, https://ambientcg.com/view?id=Gravel022, licence CC0-1.0. Resolution 1K JPEG.

| File | MD5 |
|---|---|
| Gravel022_1K-JPG_Color.jpg | 5df8085ea81cae13e0cedbee07a28f00 |
| Gravel022_1K-JPG_NormalGL.jpg | 4e82cc6c91982cff262b144fa1af024a |
| Gravel022_1K-JPG_Roughness.jpg | 7d0c3565a154de45414fa5ecc535c892 |

The copies match the Vivarium originals byte-for-byte (MD5 checked). The CC0 licence and source URL are from the packet, not re-verified against the ambientCG site.


## Discovery stone kit (CC0 procedural masonry)

Eleven `kit_<meshname lower>.glb` files in `ArtSource/Prepared/` cover every `WoodDiscovery.cpp` mesh name. They are generated by `build_stone_kit()` in `Tools/Prepare-Art.py` from seeded, bevelled block primitives. Origin is base centre, Z is up, and metres are the unit at grammar scale 1.0. Yaw convention: the grammar sets a piece's yaw to its edge direction (`atan2(dy, dx)` in degrees), and `WoodGrounding.cpp` passes it as UE `FRotator` yaw (0 = +X). Wall-run kit meshes (SM_DryStone_Wall, SM_FoundationCourse) therefore have their length on local +X, so a piece at yaw Y lies along `(cos Y, sin Y)`. `build_stone_kit()` rotates them 90 deg CCW about Z (`LENGTH_Y_TO_X` in `Tools/Prepare-Art.py`) after building them along Y. SM_BridgeAbutment keeps its 1.7 m length on X (the span yaw axis), and square or radially scattered pieces need no orientation. `BridgeAbutment` yaw is the span direction; check the bank-parallel orientation in render review. Box-projected UVs use 1 m per tile. `inspection.json` records the nominal size, grammar placement and scale for each piece under `asset: stone_kit`.

Materials come from two CC0 Poly Haven 2k sets fetched by `Tools/Fetch-Art.ps1` into `ArtSource/PolyHaven/<id>/` and verified against the API MD5:

| Set | Used for | Diffuse MD5 | GL normal MD5 | Roughness MD5 |
|---|---|---|---|---|
| [stacked_stone_wall](https://polyhaven.com/a/stacked_stone_wall) (CC0-1.0) | masonry pieces | f20377a6d0a90386d46a82dfc0e5fc97 | d37be81d921fe39c6708c07baea8187c | d86fda3889a30f2f402e84af0e434d47 |
| [rustic_stone_wall](https://polyhaven.com/a/rustic_stone_wall) (CC0-1.0) | natural rock pieces | c4975d0dbac510e746710050fcc8c955 | 31c42224b560df2ef4db780686fb15ce | 08b54fde78923b0960c60d2a2d47d482 |

`SM_FernPatch` merges `fern_02_00`, `_01` and `_02` from the existing prepared library.

| Mesh name | File | Dims X x Y x Z (m) | Grammar scale |
|---|---|---|---|
| SM_DryStone_Wall | kit_sm_drystone_wall.glb | 2.01 x 0.64 x 1.00 | 0.9-1.15 (top 0.88x) |
| SM_DryStone_Rubble | kit_sm_drystone_rubble.glb | 1.84 x 1.20 x 0.25 | 0.45-0.98 |
| SM_StonePier | kit_sm_stonepier.glb | 0.83 x 0.83 x 1.59 | 0.9-1.2 |
| SM_StonePier_Ruined | kit_sm_stonepier_ruined.glb | 1.44 x 0.96 x 0.80 | 0.95 |
| SM_FoundationCourse | kit_sm_foundationcourse.glb | 1.60 x 0.61 x 0.47 | 0.9-1.1 (upper 0.85x) |
| SM_MasonryDebris | kit_sm_masonrydebris.glb | 0.69 x 0.74 x 0.16 | 0.5-0.9 |
| SM_FernPatch | kit_sm_fernpatch.glb | 1.01 x 0.96 x 0.43 | 0.7-1.1 |
| SM_BridgeAbutment | kit_sm_bridgeabutment.glb | 1.72 x 1.13 x 1.31 | 1.35 / 1.1 |
| SM_RiverSteppingStone | kit_sm_riversteppingstone.glb | 0.68 x 0.75 x 0.30 | 0.75-0.95 |
| SM_GraniteMonolith | kit_sm_granitemonolith.glb | 0.69 x 0.44 x 1.03 | 2.4-3.8 (2.4-3.8 m tall) |
| SM_TalusRock | kit_sm_talusrock.glb | 0.97 x 0.89 x 0.51 | 0.31-0.96 (by ring) |

These are procedural placeholders for layout and scale. They are not yet imported into Unreal.

## Tree species groups (CC0, Poly Haven 1k glTF)

Fetched by `Tools/Fetch-Art.ps1` into `ArtSource/PolyHaven/<id>/` (MD5-verified) and prepared by `Tools/Prepare-Art.py` (`TREE_GROUPS`) into `ArtSource/Prepared/tree_<group>_<nn>.glb`. Steps match the pine pipeline (soil-plate removal via `remove_soil`, root flare kept, UV1 root mask and wind via `wind_uv(tree=True)`, metres, origin at trunk ground centre). The needle-card conversion is pine-specific and is not applied. Instead, each broadleaf, conifer and evergreen tree is collapse-decimated (`decimate_tree`, Blender Decimate COLLAPSE, whole mesh, one ratio per pass) to a LOD0 ceiling of 150,000 triangles (`TREE_LOD0_MAX`, `TREE_BUDGET_VERSION` 1). Result: 145,000 triangles each, with material slots and UV layers preserved. Trunk, branch and leaf geometry share the same ratio; the leaves are not replaced with alpha cards and the trunk is not decimated separately. Snags are below the ceiling and are not decimated. Dimensions and triangle counts are in `ArtSource/Prepared/inspection.json` (`height_m`, `crown_width_m`, `pre_decimate_triangles`, `decimate_ratios`, `triangles` on tree records).

Palette (BootstrapEditor, `/Game/Art/Species/CanopyV4`): `BroadleafTrees` (jacaranda old-growth giant, tree_small_02), `ConiferTrees`, `EvergreenTrees`, `DeadWood` (fallen logs). Standing trees get three LODs at 65/35/18% of LOD0 with screen sizes 0.45/0.18/0.065, as the pines do (about 26,100 triangles at the coarsest level). Leaves and bark take the FoliageWind wrapper. Standing trees have no bootstrap collision, as for pines; trunk-only collision is supplied by the world adapter. DeadWood has no collision and no wind. These arrays are not yet routed by the runtime.

Candidate inventory (Poly Haven `assets?t=models`, categories `trees` or `plants`/`nature` with tree tags):
- Broadleaf deciduous/semi-deciduous: jacaranda_tree, tree_small_02 (Burkea africana), island_tree_01/02/03 (coastal, broadleaf)
- Conifer / fir: fir_tree_01 (tall, trunk and bark, geometry nodes), fir_sapling, fir_sapling_medium, pine_sapling_medium
- Tropical or broadleaf evergreen: island_tree_01 (chosen), island_tree_02, island_tree_03, pachira_aquatica_01 (shrub, not a tree)
- Dead / snag: dead_tree_trunk, dead_tree_trunk_02 (both chosen; fallen logs, not standing), dead_quiver_trunk (Karoo, not prepared), tree_stump_01, tree_stump_02, root_cluster_01/02 (not prepared)

| Group | Source | Prepared files | Height (m) | Crown or span (m) | Triangles (source → LOD0) | glTF MD5 |
|---|---|---|---|---|---|---|
| broadleaf | [jacaranda_tree](https://polyhaven.com/a/jacaranda_tree) (CC0-1.0), old-growth giant | tree_broadleaf_00.glb | 19.47 | 24.42 x 19.15 | 3,859,574 → 145,000 | 8fed93ff7cbdaac0f5c199ef1fd0f694 |
| broadleaf | [tree_small_02](https://polyhaven.com/a/tree_small_02) (CC0-1.0), small broadleaf | tree_broadleaf_01.glb | 4.56 | 4.29 x 2.92 (footprint) | 2,062,435 → 145,000 | 63f42b19687332f7b3a5c8b531734d8e |
| conifer | [fir_tree_01](https://polyhaven.com/a/fir_tree_01) (CC0-1.0), 3 variants | tree_conifer_00/01/02.glb | 18.93 / 14.06 / 14.52 | 6.53 / 6.06 / 6.31 | 4,168,173 → 145,000 / 2,294,309 → 145,000 / 503,607 → 145,000 | 0a184431efdba9e4bf76900d8d56504d |
| evergreen | [island_tree_01](https://polyhaven.com/a/island_tree_01) (CC0-1.0) | tree_evergreen_00.glb | 5.03 | 4.82 | 1,598,956 → 145,000 | fbc0c570ebd71ea88cedc1f9d5edb835 |
| snag | [dead_tree_trunk](https://polyhaven.com/a/dead_tree_trunk) (CC0-1.0) | tree_snag_00.glb | 0.29 (lying log) | 3.05 long | 92,581 | 7bbf9fc9fdf61b50ed0495a29c03ecab |
| snag | [dead_tree_trunk_02](https://polyhaven.com/a/dead_tree_trunk_02) (CC0-1.0) | tree_snag_01.glb | 1.06 (lying log) | 4.05 long | 82,326 | c16595a5951634914898e1eb6bb0ed3d |

Notes:
- No standing dead snag was chosen. Both dead-trunk sources are fallen logs, so the snag group is horizontal and needs a yaw or pitch decision before use as a standing snag.
- Triangle budget: source sets were 0.5–4.2 million triangles. Species LOD0 is now capped at 150,000 by collapse decimation (145,000 achieved). The pine canopy is 88k–130k because its needle geometry was replaced by atlas cards. Snags stay at 82k–93k (below the cap).
- Leaf-card replacement for the species groups was not done; leaves are decimated with the rest of the mesh. A per-material split (leaves decimated harder than trunk) is the next refinement if the silhouette or trunk detail suffers in render review.
- Old-growth giant: jacaranda (19.5 m tall, 24 m crown) is kept as the broadleaf giant; tree_small_02 is the small broadleaf.
- `remove_soil` removed 52–9,221 faces per tree. Those counts were not checked against root geometry visually.
- The Blender pass was headless only, with no render review.
