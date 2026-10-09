# Flora approval list

The orchestrator reviews every preview before an asset is approved. Only approved assets are wired into the placement and palette tables. Rejected assets stay on disk but are not used.

| Batch | Approved | Rejected (needs redo) | Notes |
|---|---|---|---|
| canopy_a | oak_broadleaf, broadleaf_giant, evergreen_broad, deadwood_snag | pine_open, spruce_conifer | Pine used broadleaf cards and spruce was sparse. Both are being redone in `conifer/`. |
| shrub_a | hazel_coppice, sumac_scrub, salal_understory, heather_dwarf | willow_shrub, thorn_scrub, juniper_low | Willow is nearly bare. Thorn is sparse. Juniper looks stringy rather than dense. |
| flower | all 9 (placeholder tier) | — | arctic_poppy is the wrong colour (grey). Lupine is sparse. |
| canopy_b | acacia_flat, birch_pale, emergent_fig, cottonwood_river, understory_laurel | baldcypress | Bald cypress crown is clumped, not feathery; keep the older Vegetation bald_cypress_01 for now |
| grass | prairie_bunchgrass, wet_sedge, frost_fescue, common_reed, bamboo_stand | alpine_tussock, shade_grass, horsetail | Tussock and shade grass are sparse; horsetail reads like bamboo; common reed looks a bit like papyrus |
