# Flora: grass clumps and reeds

Authored by `Tools/Author-Flora-grass.py` (seed 7331). Solid tapered geometry, no textures.

- Units: metres. Origin at ground centre, Y-up in GLB, -Z forward / Y-up in FBX.
- One combined mesh per variant, `.glb` and `.fbx`.
- Wind VC: vertex colour `wind` (COLOR_0, red channel) = 0 at base, 1 at tip.
- Previews: `previews/<name>.png` (Cycles, ground plane, 3/4 view).

| Variant | Kind | Tris | Size (m) x,y,z |
|---|---|---|---|
| prairie_bunchgrass_v1 | grass | 1240 | 0.68 x 0.77 x 0.96 |
| prairie_bunchgrass_v2 | grass | 1240 | 0.94 x 0.90 x 0.98 |
| prairie_bunchgrass_v3 | grass | 1240 | 0.98 x 1.03 x 1.18 |
| alpine_tussock_v1 | grass | 1140 | 0.80 x 0.81 x 0.24 |
| alpine_tussock_v2 | grass | 1140 | 0.89 x 0.91 x 0.31 |
| alpine_tussock_v3 | grass | 1140 | 0.95 x 0.96 x 0.34 |
| wet_sedge_v1 | grass | 1440 | 0.22 x 0.24 x 0.69 |
| wet_sedge_v2 | grass | 1440 | 0.21 x 0.21 x 0.81 |
| wet_sedge_v3 | grass | 1440 | 0.24 x 0.23 x 0.91 |
| shade_grass_v1 | grass | 1440 | 0.81 x 0.80 x 0.29 |
| shade_grass_v2 | grass | 1440 | 0.90 x 0.93 x 0.34 |
| shade_grass_v3 | grass | 1440 | 0.93 x 0.93 x 0.37 |
| frost_fescue_v1 | grass | 1200 | 0.50 x 0.48 x 0.23 |
| frost_fescue_v2 | grass | 1200 | 0.47 x 0.49 x 0.26 |
| frost_fescue_v3 | grass | 1200 | 0.58 x 0.52 x 0.30 |
| common_reed_v1 | reed | 6656 | 1.53 x 1.50 x 3.26 |
| common_reed_v2 | reed | 8192 | 1.75 x 1.74 x 4.07 |
| horsetail_v1 | reed | 3528 | 0.44 x 0.39 x 0.84 |
| horsetail_v2 | reed | 5904 | 0.42 x 0.46 x 1.08 |
| bamboo_stand_v1 | reed | 4976 | 1.69 x 1.90 x 4.47 |
| bamboo_stand_v2 | reed | 9800 | 1.82 x 1.98 x 6.12 |

## Species notes
- prairie_bunchgrass: tall upright arching tan-green blades with seed heads (straw pods).
- alpine_tussock: dense rounded mound, short outward-bent straw/grey-green blades.
- wet_sedge: stiff triangular-section stems, dark olive green, brown seed heads.
- shade_grass: fine soft drooping blades, dark blue-green / yellow-green.
- frost_fescue: fine pale blue-grey hair-like tufts.
- common_reed: tall green stems with straw plume heads.
- horsetail: jointed upright segmented stems, darker joint sleeves, no whorl branchlets.
- bamboo_stand: 3-6 m segmented culms, darker nodes, leaf sprays above 0.8 m.

Catalogue: Docs/FloraCatalog.md. Cattail lives in ArtSource/Authored/Vegetation.
