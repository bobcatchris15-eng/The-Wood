# Flora approval list

The orchestrator reviews every preview before an asset is approved. Only approved assets are wired into the placement and palette tables. Rejected assets stay on disk but are not used.

| Batch | Approved | Rejected (needs redo) | Notes |
|---|---|---|---|
| canopy_a | oak_broadleaf, broadleaf_giant, evergreen_broad, deadwood_snag | pine_open, spruce_conifer | Pine used broadleaf cards and spruce was sparse. Both are being redone in `conifer/`. |
| shrub_a | hazel_coppice, sumac_scrub, salal_understory, heather_dwarf | willow_shrub, thorn_scrub, juniper_low | Willow is nearly bare. Thorn is sparse. Juniper looks stringy rather than dense. |
| flower | all 9 (placeholder tier) | — | arctic_poppy is the wrong colour (grey). Lupine is sparse. |
| canopy_b | acacia_flat, birch_pale, emergent_fig, cottonwood_river, understory_laurel | baldcypress | Bald cypress crown is clumped, not feathery; keep the older Vegetation bald_cypress_01 for now |
| grass | prairie_bunchgrass, wet_sedge, frost_fescue, common_reed, bamboo_stand | alpine_tussock, shade_grass, horsetail | Tussock and shade grass are sparse; horsetail reads like bamboo; common reed looks a bit like papyrus |
| fern | bracken, tree_fern, royal_fern, rock_fern, feather_moss, ground_moss_carpet, rock_moss_patch, lichen_crust v01, sphagnum_hummock v01 | lady_fern, lichen_crust v02, sphagnum_hummock v02 | Lady fern is not lacy; lichen v02 is gold; sphagnum v02 is tall and olive; moss is slightly oversaturated |
| conifer | — | pine_open, spruce_conifer, larch_sparse, krummholz_pine (all, 2 attempts) | Procedural conifers failed twice (gaps between whorls, floating pom-poms). Use the Poly Haven CC0 pine_tree_01 and fir_tree_01, plus any fetched conifers. Larch and krummholz reuse those, scaled or tinted. |
| shrub_b | understory_ginger, liana_cluster | bilberry_low, alder_thicket, sagebrush_grey, prickly_pear | Alder and bilberry are sparse twig frames; prickly pear is pale mint floating discs, not jointed pads; sagebrush is sparse. Pending CC0 replacements. |
| wetfungi | water_lily, ground_fungus_patch, puffball_cluster, pondweed | bracket_fungus, duckweed_mat | Bracket looks like egg domes; duckweed looks like a bead grid |
| conifer (Sonnet redo) | pine_open, spruce_conifer, larch_sparse, krummholz_pine | — | Supersedes the earlier conifer rejection. Spruce coverage 82-84%, pine 66-78%. Spruce is slightly columnar. |
| shrub_c (Sonnet redo) | willow_shrub, thorn_scrub, juniper_low v02, bilberry_low, alder_thicket, sagebrush_grey, prickly_pear | juniper_low v01 (teal) | Supersedes earlier shrub rejections. Coverage 0.67-0.83. Willow is bushy rather than weeping; prickly pear is slightly oversaturated. |
