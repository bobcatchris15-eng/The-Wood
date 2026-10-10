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

### LeafPools (leaf albedo, vein normal and vein mask, from the Vivarium project)

`ArtSource/Vivarium/LeafPools/` holds PNG copies only, from `C:\Misc\Vivarium\game\Textures\LeafPools\`: `Masters/<species>-0..3.png` (albedo masters for shadebell, lanternbrush, glassfinger, embercrown) and `<species>/vein_normal.png` and `<species>/vein_mask.png`. The `.res` files are not copied.

Provenance: self-generated for Vivarium (owner: project user), Codex image_gen; reused with owner permission. This is not CC0 and is not a third-party licence. It is recorded here so the reuse basis is traceable.


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

Fetched by `Tools/Fetch-Art.ps1` into `ArtSource/PolyHaven/<id>/` (MD5-verified) and prepared by `Tools/Prepare-Art.py` (`TREE_GROUPS`) into `ArtSource/Prepared/tree_<group>_<nn>.glb`. Steps match the pine pipeline (soil-plate removal via `remove_soil`, root flare kept, UV1 root mask and wind via `wind_uv(tree=True)`, metres, origin at trunk ground centre). The needle-card conversion is pine-specific and is not applied. Leaves are kept at full source geometry (`split_bark_leaf`, material slots `leaves`/`twig` are leaf, all others are bark). Only the bark part is collapse-decimated (`decimate_bark`, Blender Decimate COLLAPSE) to a ceiling of 300,000 triangles (`TREE_BARK_MAX`, `TREE_BUDGET_VERSION` 2). The bark and leaf parts are rejoined. `inspection.json` records `bark_triangles_before`, `bark_triangles_after`, `leaf_triangles`, `decimate_ratios`, and `triangles` (total LOD0). Snags have no leaf faces and are under the ceiling, so they are unchanged.

Palette (BootstrapEditor, `/Game/Art/Species/CanopyV4`): `BroadleafTrees` (jacaranda old-growth giant, tree_small_02), `ConiferTrees`, `EvergreenTrees`, `DeadWood` (fallen logs). Standing trees and dead wood are Nanite (`SMES.set_nanite_settings`, enabled, 100% triangles kept, no error trim). Standing trees have one LOD (LOD0 only, no authored distance LODs). Leaf and twig materials are converted to `BLEND_MASKED` (clip 0.35) with the opacity input re-wired to OpacityMask, because the glTF import marks them BLEND and Nanite does not draw translucent materials. All standing-tree materials are two-sided and wrapped with FoliageWind at 16 (`_2S` / `_Mask` suffixes). Standing trees have no bootstrap collision, as for pines; trunk-only collision is supplied by the world adapter. DeadWood has no collision and no wind. No project settings or component flags were changed. These arrays are not yet routed by the runtime, so the HISM WPO and Nanite instance flags are unset and must be set when the world adapter uses them.

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
- Triangle budget (per variant, LOD0, after prep): tree_broadleaf_00 2,697,433 (bark 1,457,140 → 294,999; leaf 2,402,434 untouched); tree_broadleaf_01 2,062,435 (bark 123,055; leaf 1,939,380); tree_conifer_00 4,168,173 (bark 102,054; leaf 4,066,119); tree_conifer_01 2,294,309 (bark 87,013; leaf 2,207,296); tree_conifer_02 503,607 (bark 57,533; leaf 446,074); tree_evergreen_00 1,355,031 (bark 538,924 → 294,999; leaf 1,060,032); tree_snag_00 92,581 and tree_snag_01 82,326 (bark only, unchanged). Leaves are not decimated. Nanite is the reduction path for foliage; the LOD0 totals are high, so the per-variant cost is a render-review item.
- Leaf-card replacement for the species groups was not done. The pine canopy is 88k–130k because its needle geometry was replaced by atlas cards.
- Old-growth giant: jacaranda (19.5 m tall, 24 m crown) is kept as the broadleaf giant; tree_small_02 is the small broadleaf.
- `remove_soil` removed 52–9,221 faces per tree. Those counts were not checked against root geometry visually.
- The Blender pass was headless only, with no render review.

## CC0 plant and nature models (Fetch-CC0Plants.ps1)

| asset | licence | date | files | main file sha256 |
|---|---|---|---|---|
| [anthurium_botany_01](https://polyhaven.com/a/anthurium_botany_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/anthurium_botany_01/ (1k, 5 files) | 6b3f6b8eda6cc0edfefd6a58f6758ef6538c35b2ca2a76189383f23b246dd8c6 |
| [bark_debris_01](https://polyhaven.com/a/bark_debris_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/bark_debris_01/ (1k, 5 files) | 478d222823c79a48c3eb58c2bbb91c81073dd28ce5f307b0d5a1467bd2e4e28b |
| [calathea_orbifolia_01](https://polyhaven.com/a/calathea_orbifolia_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/calathea_orbifolia_01/ (1k, 5 files) | 399130c01bfff6b493f885652112c3c841c3814b024a3d3c87773e0c5ab4f156 |
| [celandine_01](https://polyhaven.com/a/celandine_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/celandine_01/ (1k, 5 files) | ae54536f79b426e69c33449b75a89b86fb127f91342445c26cc4142c5f4220d5 |
| [cheiridopsis_succulent](https://polyhaven.com/a/cheiridopsis_succulent) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/cheiridopsis_succulent/ (1k, 5 files) | 4db4005db3e8fea6fc7b99cddbd0904fd3f5f5ddceccbabe05b7fa04ede9bcd8 |
| [crystalline_iceplant](https://polyhaven.com/a/crystalline_iceplant) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/crystalline_iceplant/ (1k, 5 files) | 46983341146dfacc96116e7468562b9e3b0a5be15d15940a98d9bab045c39910 |
| [dandelion_01](https://polyhaven.com/a/dandelion_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/dandelion_01/ (1k, 5 files) | 68f804fe29f641f37b03c470cf9065d34aacd1b4f580ed6f35385626c2bb42b7 |
| [dead_quiver_branch_01](https://polyhaven.com/a/dead_quiver_branch_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/dead_quiver_branch_01/ (1k, 5 files) | 120a9bae2f367b414852fce40d28935db0559e66634827d2e7dc045764fd4b47 |
| [dead_quiver_branch_02](https://polyhaven.com/a/dead_quiver_branch_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/dead_quiver_branch_02/ (1k, 5 files) | 6838ab37789029751b2d51eeffe630aa92dfd5e4da701831cb6d268398cf1afb |
| [didelta_spinosa](https://polyhaven.com/a/didelta_spinosa) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/didelta_spinosa/ (1k, 5 files) | 08d14d3a7667588dbd7539147b9efa64cd3277780564d86ec56b0a679935d422 |
| [dry_branches_medium_01](https://polyhaven.com/a/dry_branches_medium_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/dry_branches_medium_01/ (1k, 5 files) | 23f328ded9be1e151ccd7994b303c70221551544c4857a71474c1c01a14b8a22 |
| [dry_quiver_leaf](https://polyhaven.com/a/dry_quiver_leaf) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/dry_quiver_leaf/ (1k, 5 files) | 80ae8cad2fe7f3f79e78495c50696ada21740df965e03aa9de78fe53adf767af |
| [fir_sapling](https://polyhaven.com/a/fir_sapling) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/fir_sapling/ (1k, 8 files) | a9466ca9d8c5b9b2eeeeafd3ce426f8912dcbd98a7281bad8c734833eb35b186 |
| [fir_sapling_medium](https://polyhaven.com/a/fir_sapling_medium) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/fir_sapling_medium/ (1k, 8 files) | 2e80cd49d716c99bdead5a42aa6441e89443044d9a0edc31b56b5dbf87fc41de |
| [flower_empodium](https://polyhaven.com/a/flower_empodium) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/flower_empodium/ (1k, 5 files) | 3f39d6b7dba6de81014f5ce41e43ac1204a45bfe146cbb425515103c4c5e9798 |
| [flower_gazania](https://polyhaven.com/a/flower_gazania) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/flower_gazania/ (1k, 5 files) | 73c7f4094f2ad78ddfbe6373f8372ddb736a5d9fc6485db08ae32301edc95a24 |
| [flower_heliophila](https://polyhaven.com/a/flower_heliophila) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/flower_heliophila/ (1k, 5 files) | 629274399d44a1a9c8666d7a341bf7c5b2083c3ec292166cb23419ff9eb192b1 |
| [flower_stinkkruid](https://polyhaven.com/a/flower_stinkkruid) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/flower_stinkkruid/ (1k, 5 files) | 92f1b86573d38d4a71a5ae875f52f2a201f932694a4e5e423f5098892f337ed3 |
| [flower_ursinia](https://polyhaven.com/a/flower_ursinia) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/flower_ursinia/ (1k, 5 files) | aaa44302d04f39f03773db09deb561113213ef97155cec7d3744a079bc07b580 |
| [garden_hose_wall_mounted_01](https://polyhaven.com/a/garden_hose_wall_mounted_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/garden_hose_wall_mounted_01/ (1k, 5 files) | 7746484fbf4cea3e0d36526b3ceb05aee3ea4cb6a20d54a8c331a95e4e15a45c |
| [island_tree_02](https://polyhaven.com/a/island_tree_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/island_tree_02/ (1k, 11 files) | d8c5d9ead41cdbef91a648f40ff60470faa19eb3a7010e59e44cb1a01250f75d |
| [island_tree_03](https://polyhaven.com/a/island_tree_03) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/island_tree_03/ (1k, 11 files) | 5efbe24ad6fc769db55ac771eec7a2ee7aa389c5667656f279d0743e455ef04a |
| [leipoldtia_schultzei](https://polyhaven.com/a/leipoldtia_schultzei) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/leipoldtia_schultzei/ (1k, 5 files) | ae18b6b0d8eee9c2491577c96dbe4bb84ca923b997a22949f0421d7e7ed94432 |
| [moss_01](https://polyhaven.com/a/moss_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/moss_01/ (1k, 5 files) | 36fe6cb9889abb33f4dbee402928e260a3e7dfaec043d39b80b1e3afff684f65 |
| [nettle_plant](https://polyhaven.com/a/nettle_plant) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/nettle_plant/ (1k, 5 files) | 45baafa16feb0017e6a46712e2aa7afe7841fd00905075ead8316a5fc8314b0e |
| [othonna_cerarioides](https://polyhaven.com/a/othonna_cerarioides) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/othonna_cerarioides/ (1k, 5 files) | cbbe57f895038c490f2b73d3c068a478f74c6e74d19c8d21ae96cb78567e5a56 |
| [pachira_aquatica_01](https://polyhaven.com/a/pachira_aquatica_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/pachira_aquatica_01/ (1k, 8 files) | e73b77c0ffadd8b9fa686faabfecf37799123fe4bc756f816145a4f8c9f53364 |
| [periwinkle_plant](https://polyhaven.com/a/periwinkle_plant) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/periwinkle_plant/ (1k, 5 files) | df781eea76123fc6eee97e6e8d466743e3a5fb08e1a2c3f5025a57e090d2cc55 |
| [pine_roots](https://polyhaven.com/a/pine_roots) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/pine_roots/ (1k, 8 files) | 3f25ab982be6dee9328e012fcff9b82f21284fe8af8abdaafa6f316c819297aa |
| [pine_sapling_medium](https://polyhaven.com/a/pine_sapling_medium) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/pine_sapling_medium/ (1k, 8 files) | b08bc0f19b06b545115945164b0d3a8340c78ba86a0521ea7cfe9c2d50a83f4e |
| [potted_plant_01](https://polyhaven.com/a/potted_plant_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/potted_plant_01/ (1k, 8 files) | 23b30294407684b02f14800d6685bd8938da5d2111e17753ac8dd3c37d8c88a0 |
| [potted_plant_02](https://polyhaven.com/a/potted_plant_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/potted_plant_02/ (1k, 8 files) | c533dcce0d1aa4379eb7db04601a04983f8df2422b28578de922655a416e64a9 |
| [potted_plant_04](https://polyhaven.com/a/potted_plant_04) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/potted_plant_04/ (1k, 5 files) | b3a3bc3e97da75844999c4da07b7104b6c023f729a7c045979929b9504184339 |
| [quiver_tree_01](https://polyhaven.com/a/quiver_tree_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/quiver_tree_01/ (1k, 8 files) | aa6885a0fe43b274584851b0947e2209dc64afce1d20a75a1567e790a12d0722 |
| [quiver_tree_02](https://polyhaven.com/a/quiver_tree_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/quiver_tree_02/ (1k, 5 files) | c92ea2f60defaa9c134f43ac606bb7564ade348f92b546ba91c87bc6365d1a56 |
| [root_cluster_01](https://polyhaven.com/a/root_cluster_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/root_cluster_01/ (1k, 5 files) | b9060cfe2c1db4326428a0bf834e8409a99988082c8e5465cb09738d72117463 |
| [searsia_lucida](https://polyhaven.com/a/searsia_lucida) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/searsia_lucida/ (1k, 5 files) | ebdc8d776c058b9a6f9a04c57ca0540368531febd3bfa007d2e2d8af8d368f67 |
| [shrub_01](https://polyhaven.com/a/shrub_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/shrub_01/ (1k, 5 files) | c3bb3340687d46c684b9dab82f5b2f92b7b0fe761842423d3c9e19f59a839393 |
| [shrub_02](https://polyhaven.com/a/shrub_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/shrub_02/ (1k, 5 files) | 99de0a70fe88ad414615cc8d8e020617c8512e2abfe08b911b153a6fcc40d93e |
| [shrub_03](https://polyhaven.com/a/shrub_03) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/shrub_03/ (1k, 5 files) | b76d7c14bc027e834e82d3f984c32b5d060e62908aa90ff9420a637ca253a8ea |
| [shrub_04](https://polyhaven.com/a/shrub_04) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/shrub_04/ (1k, 5 files) | 782832cbc57e96686b78c6ef9df6234c25f564f78421c8ed4bd42c3631f5aeae |
| [shrub_sorrel_01](https://polyhaven.com/a/shrub_sorrel_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/shrub_sorrel_01/ (1k, 5 files) | 97e2c9b564610a1077de9e15de07acbf19f2e66619016aeebb7987e191ad3ce1 |
| [single_root](https://polyhaven.com/a/single_root) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/single_root/ (1k, 5 files) | b88d0e4b06f710a70af3adb8dd72dea106d3b90f4d093b3e94a09c781745d92c |
| [tree_stump_01](https://polyhaven.com/a/tree_stump_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/tree_stump_01/ (1k, 5 files) | 9c66ba87d693f35eb404acaa96e0eeff831c295b61a0a903795584cbcc3527c9 |
| [tree_stump_02](https://polyhaven.com/a/tree_stump_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/tree_stump_02/ (1k, 5 files) | a79189160d1c7cfd6d875ab4470e4d2ff9cee08d58943be69d6028034a08c7ec |
| [weed_plant_02](https://polyhaven.com/a/weed_plant_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/weed_plant_02/ (1k, 5 files) | 20fe9aa14ec8160de54d8027422ce6db93bcc6211299509067ee3edbceff218b |
| [wild_rooibos_bush](https://polyhaven.com/a/wild_rooibos_bush) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/wild_rooibos_bush/ (1k, 5 files) | 7f3fb17e4606e33d0bc4239c4901c9610b4bd17fe26b6780ba11ab4493f25d29 |
| [dead_quiver_trunk](https://polyhaven.com/a/dead_quiver_trunk) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/dead_quiver_trunk/ (1k, 5 files) | c130bce552d608057143e7f131f36e9c4e06a9b780947c85d4e5eb1cacfedbaf |
| [searsia_burchellii](https://polyhaven.com/a/searsia_burchellii) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/searsia_burchellii/ (1k, 5 files) | 77cde5ca5a5aade15e1d167cb35dd7e52d9c4f59fadffdfb1baa47eed178ea2c |
| [bananas](https://polyhaven.com/a/bananas) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/bananas/ (1k, 5 files) | 4709a758c91cbfb5df7df23fb6d9ed21778ed0030c260b11f9171ed28659e700 |
| [coast_land_rocks_02](https://polyhaven.com/a/coast_land_rocks_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coast_land_rocks_02/ (2k, 5 files) | 976262bd7e645710ae85d94b76f5c84538684a0fede22ccfcdda5c49a6e21c4b |
| [coast_land_rocks_03](https://polyhaven.com/a/coast_land_rocks_03) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coast_land_rocks_03/ (2k, 5 files) | 975cde44cd21bfc660efaf3e98f7d1b450a218f685f97c3246d1060a82670dbf |
| [coast_land_rocks_04](https://polyhaven.com/a/coast_land_rocks_04) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coast_land_rocks_04/ (2k, 5 files) | f8a235cbcce38eecceccfcc27e325448abef20678a0967bf3a8706b369409446 |
| [coast_line_01](https://polyhaven.com/a/coast_line_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coast_line_01/ (2k, 5 files) | 7bccff2e6888782f447bf93915236c2cd5113473439427616598aa78e06dc998 |
| [coast_line_02](https://polyhaven.com/a/coast_line_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coast_line_02/ (2k, 5 files) | 82f56378abe3115bbcad65b4a82f61a46f8436d3670eacd4e19c5c2526df0495 |
| [coast_rocks_01](https://polyhaven.com/a/coast_rocks_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coast_rocks_01/ (2k, 5 files) | 9e75ec94594ce0a2e7625ed4339e2f2b35da192eb41630c59aaa8ccaa9e49240 |
| [coast_rocks_02](https://polyhaven.com/a/coast_rocks_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coast_rocks_02/ (2k, 5 files) | e88d65fbdd495c60078b8e61362e2d02d51916a13f19f37fa861907fde33195e |
| [coast_rocks_03](https://polyhaven.com/a/coast_rocks_03) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coast_rocks_03/ (2k, 5 files) | b12da85ca435c27a3aea6c87dc15eca66690e888a3f1b781a97939b111f9d89e |
| [coast_rocks_05](https://polyhaven.com/a/coast_rocks_05) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coast_rocks_05/ (2k, 5 files) | 731e3c8651c6afd097b91e9d0100ef23e874f34f1f2bc0a741f3c07b0f38eb29 |
| [coastal_cliff_01](https://polyhaven.com/a/coastal_cliff_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coastal_cliff_01/ (1k, 5 files) | 2e6bb1f77965b314208b309ac89b94b8148c6a08ee6c9808cd71455e5475602d |
| [coastal_cliff_02](https://polyhaven.com/a/coastal_cliff_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coastal_cliff_02/ (1k, 5 files) | 022e2df3da198ad294be18d322f09881bc0ad90b108d88ff638fa4a3fafb033f |
| [coastal_cliff_04](https://polyhaven.com/a/coastal_cliff_04) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/coastal_cliff_04/ (2k, 5 files) | b0b1298ae7399404a8be7e894ae68c120ebe55835b6ea6bba6c29bbc211b2919 |
| [food_apple_01](https://polyhaven.com/a/food_apple_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/food_apple_01/ (1k, 5 files) | 6a7dc1cda1271c8b08e36e2b9fd44371b7149cca6262c71bc36d971cdac4325f |
| [food_avocado_01](https://polyhaven.com/a/food_avocado_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/food_avocado_01/ (1k, 5 files) | cce51afb7dcdc6c19371806993e2c1096788a10accf453fda1198875e59f7846 |
| [food_ginger_01](https://polyhaven.com/a/food_ginger_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/food_ginger_01/ (1k, 5 files) | d08d23765047a58ba29dcebd72a4aa481690cc7774179e42a4af5cb66b2c9ffb |
| [food_kiwi_01](https://polyhaven.com/a/food_kiwi_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/food_kiwi_01/ (1k, 5 files) | ba01ebeacdcb034501dc1743fd7278ee4c2dfd3e1860dcd192953fce6ff50b97 |
| [food_lime_01](https://polyhaven.com/a/food_lime_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/food_lime_01/ (1k, 5 files) | a3287904a7b56acb806c00803b9c8e0b71163649e2c87a5db3d18ac23c68e3ce |
| [food_lychee_01](https://polyhaven.com/a/food_lychee_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/food_lychee_01/ (1k, 5 files) | 2defd06eccf002026e986023f75332ace25c7d22e80a32a28fd9aea639d488ef |
| [food_pears_asian_01](https://polyhaven.com/a/food_pears_asian_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/food_pears_asian_01/ (1k, 5 files) | ff3373b91eef143a3921198f61a3b10aa87bcb870f905b2271ce3917b34ff300 |
| [food_pomegranate_01](https://polyhaven.com/a/food_pomegranate_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/food_pomegranate_01/ (1k, 5 files) | 75e8bac9feda588189245fe8d145313fe382ee11766101d4b97f1c63476d6698 |
| [lambis_shell](https://polyhaven.com/a/lambis_shell) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/lambis_shell/ (1k, 5 files) | 3fbfbe990b12f33af079671bc9ea9b1dd46b50f823692b72aa0d89fe850328e3 |
| [moon_rock_01](https://polyhaven.com/a/moon_rock_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/moon_rock_01/ (2k, 5 files) | d3cbe420cfb38d68aaf2c54433b734fb13a637ed1a8c6429137308483af12e04 |
| [moon_rock_02](https://polyhaven.com/a/moon_rock_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/moon_rock_02/ (2k, 5 files) | 8132b4687306af9e999980ef447eaa45f4acca4955f46f029037bc13f803e0ef |
| [moon_rock_03](https://polyhaven.com/a/moon_rock_03) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/moon_rock_03/ (2k, 5 files) | f8db505c924ee208ba1976b0873197d5f231aaa5ba28f7ed6ce3ea95103167e4 |
| [moon_rock_04](https://polyhaven.com/a/moon_rock_04) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/moon_rock_04/ (2k, 5 files) | 7c9db72523929130b50b32ab0c3b49cb145b761fa1d3315931d11e275931a553 |
| [moon_rock_05](https://polyhaven.com/a/moon_rock_05) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/moon_rock_05/ (2k, 5 files) | d1f362694a636dc4ef48aec60480459badedc4e3846e0279571122e03d577265 |
| [moon_rock_06](https://polyhaven.com/a/moon_rock_06) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/moon_rock_06/ (2k, 5 files) | 8d37d47bb8c10717c34f7567e07211ca32be982ab78657ebf5fb982222dfde5e |
| [moon_rock_07](https://polyhaven.com/a/moon_rock_07) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/moon_rock_07/ (2k, 5 files) | 30262e9e6f22a299db4413e89c8d776a17c1b41696220478a597e05f183e6c92 |
| [mountainside](https://polyhaven.com/a/mountainside) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/mountainside/ (2k, 5 files) | ccdbbb75744b764b19c8868e5f47b6a85e62961fa2f7fe3dc9b73b219c89834d |
| [namaqualand_boulder_02](https://polyhaven.com/a/namaqualand_boulder_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/namaqualand_boulder_02/ (2k, 5 files) | e181b722c8c8bd56f98ab8883b283b3cb3c437c372af3b831aec2f94c22fe0f2 |
| [namaqualand_boulder_03](https://polyhaven.com/a/namaqualand_boulder_03) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/namaqualand_boulder_03/ (2k, 5 files) | 5d135c8e3a74edf7f53ae04d41deed19582ed6ced6d629d5d51e730319ed0dcb |
| [namaqualand_boulder_04](https://polyhaven.com/a/namaqualand_boulder_04) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/namaqualand_boulder_04/ (2k, 5 files) | 199a6ff206a09086a82542238dbdc0e024832d8662c3f5648dd4b6bbf3e3c724 |
| [namaqualand_boulder_05](https://polyhaven.com/a/namaqualand_boulder_05) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/namaqualand_boulder_05/ (2k, 5 files) | d2e1f687c01176703e76b6c6d9ff7a98c868a3c6402c7d97bc17a613e9c64fcc |
| [namaqualand_boulder_06](https://polyhaven.com/a/namaqualand_boulder_06) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/namaqualand_boulder_06/ (2k, 5 files) | 405f95c207f1b48b1d3f84a04e9458e62f4d4269ff62f32b1ee870a8b4471dea |
| [namaqualand_boulders_01](https://polyhaven.com/a/namaqualand_boulders_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/namaqualand_boulders_01/ (2k, 5 files) | d419fb3aaf5477c475eff7f25c40114d003222d465f30eafebefd3af4dd66168 |
| [namaqualand_cliff_01](https://polyhaven.com/a/namaqualand_cliff_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/namaqualand_cliff_01/ (2k, 5 files) | 4bc082e507e04eda04fbf1bb54a6af6c59896f44d8d4194db164e6ab619e8833 |
| [namaqualand_cliff_02](https://polyhaven.com/a/namaqualand_cliff_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/namaqualand_cliff_02/ (2k, 5 files) | 42b5aa0c33e4aab50dd04f01dc0b24a57e48043ea16cefeb8a7292e243a05630 |
| [namaqualand_rocks_01](https://polyhaven.com/a/namaqualand_rocks_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/namaqualand_rocks_01/ (2k, 5 files) | cdf07b35d823f9cf2f2e46e9289b08544c5a412b9acfcc188eb0b69c9c4bdf7b |
| [namaqualand_stones_01](https://polyhaven.com/a/namaqualand_stones_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/namaqualand_stones_01/ (2k, 5 files) | 74bd016ee7d3ba395ba620be16fe460e655e66d2c9bc5972d87bc99ccc6f4e47 |
| [rock_09](https://polyhaven.com/a/rock_09) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/rock_09/ (2k, 5 files) | f5f430215ad93e3d95755aa78c1c84a619497dfdc1ee297f8ac35df607ee03a3 |
| [rock_face_01](https://polyhaven.com/a/rock_face_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/rock_face_01/ (2k, 5 files) | 5ab7fa969b57de507db72627d41f1b901e11ae406e52024b1c267c7c1caad40a |
| [rock_face_02](https://polyhaven.com/a/rock_face_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/rock_face_02/ (2k, 5 files) | 532c5662536c59dde08e1ab3e0985addcf555d7c6bd9c4ee6957c6e5a7c200c6 |
| [root_cluster_02](https://polyhaven.com/a/root_cluster_02) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/root_cluster_02/ (1k, 5 files) | 111195b40a2c6c241bfee47d00918a627689b322f53b99115d1f04e99d3514dd |
| [sand_rocks_small_01](https://polyhaven.com/a/sand_rocks_small_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/sand_rocks_small_01/ (2k, 5 files) | a4b05d1ab4323aa0ffc4af1092093be3e957548a79cc55e9a1ebee0b556c8d12 |
| [stone_01](https://polyhaven.com/a/stone_01) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/stone_01/ (2k, 5 files) | 64cb8690fc70e9eff7bc8bc432ec9f9b82890de4e8e36f92f1f3fd7571d29b9e |
| [street_rat](https://polyhaven.com/a/street_rat) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/street_rat/ (1k, 5 files) | 66d822f0828838a5ffd1f82b846bdf90c962c73781bf8f1da22b487eef6950b2 |
| [sweet_potato](https://polyhaven.com/a/sweet_potato) (CC0-1.0) | CC0-1.0 | 2026-10-09 | PolyHaven/sweet_potato/ (1k, 5 files) | 36a226b95a63b2e22711d75e17818f33f99a17e54737e5469a8c7d2a41896097 |
| [Ground112](https://ambientcg.com/a/Ground112) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Ground112/ (1K-PNG, 7 files; main Ground112_1K-PNG_Color.png) | 9b2ac7ff6b6d0298342d8ca52bb51a7c5d5faa7d7d483fccbe7225772e9b3937 |
| [Ground111](https://ambientcg.com/a/Ground111) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Ground111/ (1K-PNG, 7 files; main Ground111_1K-PNG_Color.png) | 955d2457083e8150f346bef2ade6b0ccf99f9c0faa14d4b57a29528927e90ca4 |
| [Ground110](https://ambientcg.com/a/Ground110) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Ground110/ (1K-PNG, 7 files; main Ground110_1K-PNG_Color.png) | ecbf168756fc3f513d7653b6a59f957e816df2fc07bd7ac194cd2adc82c6bab1 |
| [Ground108](https://ambientcg.com/a/Ground108) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Ground108/ (1K-PNG, 7 files; main Ground108_1K-PNG_Color.png) | d2e26e1e785338d342280ff2c2f0b5a9ed81f6ec942db4ed808252294c22b284 |
| [Ground109](https://ambientcg.com/a/Ground109) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Ground109/ (1K-PNG, 7 files; main Ground109_1K-PNG_Color.png) | 009c611957767788eab965e5c77a6160d7531ae8ccdb3171fe074ede9df6caaf |
| [Rock064](https://ambientcg.com/a/Rock064) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Rock064/ (1K-PNG, 7 files; main Rock064_1K-PNG_Color.png) | c67046d29fa5efac4e22d82fd2ead97e03700b51be9467463c8ce2a55f213178 |
| [Ground106](https://ambientcg.com/a/Ground106) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Ground106/ (1K-PNG, 7 files; main Ground106_1K-PNG_Color.png) | b34d1b6d5c687b3a49953ebf9ba51d49df929fb8ca15a2bc62c9a77a6e7f49c7 |
| [Ground103](https://ambientcg.com/a/Ground103) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Ground103/ (1K-PNG, 7 files; main Ground103_1K-PNG_Color.png) | 0d9461215ae355b6b34c85bac4102b7de8baba723b855e5a3114c3e2c0969f12 |
| [Gravel043](https://ambientcg.com/a/Gravel043) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Gravel043/ (1K-PNG, 7 files; main Gravel043_1K-PNG_Color.png) | 08fe8d727d1a58bf5b83c9c7cd5734b435824858dbc61bda4a1340f520629c02 |
| [Ground107](https://ambientcg.com/a/Ground107) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Ground107/ (1K-PNG, 7 files; main Ground107_1K-PNG_Color.png) | c1877151a1745a6f7b49fc4a47f02dcdef42dba7705f6ac0d2476eadd6cafb78 |
| [ScatteredLeaves009](https://ambientcg.com/a/ScatteredLeaves009) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/ScatteredLeaves009/ (1K-PNG, 7 files; main ScatteredLeaves009_1K-PNG_Color.png) | 07d699fc9992bf572eb32111a5bfe909f0d97b29b908d644dee13a2c5aa93e4f |
| [Grass001](https://ambientcg.com/a/Grass001) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Grass001/ (1K-PNG, 7 files; main Grass001_1K-PNG_Color.png) | c79fda29c8a1249157e5e90b033cde2b126905ef2961de3edca1255f322e64ae |
| [Rock063](https://ambientcg.com/a/Rock063) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Rock063/ (1K-PNG, 7 files; main Rock063_1K-PNG_Color.png) | 494cbc5b1c781bb27f6859a4f34275c3b101ada4cb72e7bf189b3528d343ca80 |
| [Grass004](https://ambientcg.com/a/Grass004) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Grass004/ (1K-PNG, 7 files; main Grass004_1K-PNG_Color.png) | 1c504b956e5550fedd8822e7e2135fe45f513bc1212f72ed67885de1002fabb6 |
| [Ground037](https://ambientcg.com/a/Ground037) (CC0-1.0) | CC0-1.0 | 2026-10-09 | AmbientCG/Ground037/ (1K-PNG, 7 files; main Ground037_1K-PNG_Color.png) | d428f7b2ca3c724bb6534ef6313574b4c07712e41bab84be69ba41a0d32e947d |
