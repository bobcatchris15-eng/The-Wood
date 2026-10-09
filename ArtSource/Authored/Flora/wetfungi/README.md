# Flora: aquatic plants and fungi

Authored by `Tools/Author-Flora-wetfungi.py` (seed 9017). Modelled geometry with 512 px albedo + normal textures.

- Units: metres. One combined mesh per variant, `.glb` and `.fbx` (FBX textures referenced relatively from `textures/`).
- Origins: water_lily, duckweed_mat, pondweed at water surface z=0 (pondweed roots at z=-0.5). bracket_fungus at attach face, +X outward. puffball_cluster and ground_fungus_patch at ground z=0.
- Previews: `previews/<name>.png` (Cycles; water plane for lily/duckweed, bottom plane for pondweed, trunk for bracket).

| Variant | Kind | Tris | Size (m) x,y,z |
|---|---|---|---|
| water_lily_v1 | aquatic | 808 | 0.624 x 0.786 x 0.042 |
| water_lily_v2 | aquatic | 810 | 0.742 x 0.789 x 0.042 |
| duckweed_mat_v1 | aquatic | 2 | 1.000 x 1.000 x 0.000 |
| duckweed_mat_v2 | aquatic | 2 | 1.000 x 1.000 x 0.000 |
| pondweed_v1 | aquatic | 200 | 0.438 x 0.350 x 0.501 |
| pondweed_v2 | aquatic | 280 | 0.255 x 0.482 x 0.501 |
| bracket_fungus_v1 | fungus | 864 | 0.080 x 0.200 x 0.336 |
| bracket_fungus_v2 | fungus | 576 | 0.104 x 0.260 x 0.219 |
| puffball_cluster_v1 | fungus | 1176 | 0.211 x 0.209 x 0.107 |
| puffball_cluster_v2 | fungus | 784 | 0.201 x 0.242 x 0.143 |
| ground_fungus_patch_v1 | fungus | 792 | 0.252 x 0.182 x 0.090 |
| ground_fungus_patch_v2 | fungus | 1188 | 0.280 x 0.308 x 0.102 |

Catalogue: Docs/FloraCatalog.md.
