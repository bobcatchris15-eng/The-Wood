# The Wood — flora catalogue

Planning spec · 2026-10-09 · drives plant authoring (Blender Clankers) and habitat placement.
Biome families follow `Biome` in `Source/TheWood/Public/Generation/WoodGeneration.h`. Variant and motif numbering follows [BiomeCatalog.md](BiomeCatalog.md). Species enum values (`Species`) are noted where a species corresponds to an existing enum entry.

## Legend

Biome codes: TF TemperateForest · DG DryGrassland · RH RockyHighlands · TG Taiga · OG OldGrowthForest · CR ColdRainforest · IH IcyHills · SV Savannah · SW Swamp · MA Marsh · WR WarmRainforest · PR Prairie

Moisture is 0–1 (0 arid, 1 saturated). Shade tolerance: low, med, high. Water: y means placed within the near-water band of streams, pools or marsh. Density weight is relative within each biome (the number after the code). Source values: `existing:<id>` is an ArtSource asset; `Vivarium:<path>` is a CC0 texture under `C:\Misc\Vivarium\game\Textures`; `author` means author procedurally in Blender; `PolyHaven` means fetch from Poly Haven. Mappings marked UNVERIFIED are guesses from filenames and must be checked against the asset before use.

## Species — biome flora (65)

| ID | role | biomes | moisture | elev/slope | shade | water | height_m | silhouette | colour variants | source | density weight |
|---|---|---|---|---|---|---|---|---|---|---|---|
| pine_open | canopy | RH TF DG | 0.2–0.5 | 0–0.8 ridges and dry slopes, not valley floors | low | n | 15–30 | tall bare trunk with flat crown held high, sparse needle plumes | warm grey-brown bark; blue-green needles; ochre bark | existing:pine_tree_01 (Species Pine); saplings existing:pine_sapling_small | RH3 TF2 DG1 |
| oak_broadleaf | canopy | TF OG DG SV | 0.4–0.7 | 0–0.5 lowland and rolling | med | n | 15–25 | broad domed crown on heavy low limbs | green; yellow-green; autumn ochre | existing:tree_broadleaf_00 (Species Broadleaf, UNVERIFIED) | TF4 OG3 DG2 SV1 |
| broadleaf_giant | canopy | OG | 0.5–0.8 | 0–0.4 valleys and sheltered shoulders | high | n | 30–45 | irregular huge crown over a massive trunk with root flare | deep green; dark olive; bronze autumn | existing:tree_broadleaf_01 (Species BroadleafGiant, UNVERIFIED) | OG4 |
| spruce_conifer | canopy | TG OG CR | 0.4–0.8 | 0–0.9 all slopes | high | n | 20–35 | narrow spire with whorled dark branches reaching the ground | blue-green; dark green; grey-green | existing:fir_tree_01 (Species Conifer, UNVERIFIED) | TG4 OG3 CR2 |
| evergreen_broad | canopy | CR WR | 0.6–0.9 | 0–0.5 | high | n | 18–28 | dense dark evergreen dome with drooping outer branches | dark olive; blue-black; glossy green | existing:tree_small_02 (Species Evergreen, UNVERIFIED) | CR4 WR2 |
| deadwood_snag | canopy | TF TG SW | 0.2–0.9 | 0–0.9 | low | y in SW | 6–20 | bleached broken trunk with a few stub limbs | silver grey; pale bark; dark rot | existing:dead_tree_trunk; existing:dead_tree_trunk_02 (Kind Deadwood) | TF1 TG2 SW1 |
| acacia_flat | canopy | SV | 0.1–0.4 | 0–0.4 | low | n | 6–12 | flat umbrella crown on a bent trunk | grey-green; olive; pale | author (Species Acacia); existing:island_tree_01 is an UNVERIFIED candidate only | SV4 |
| baldcypress | canopy | SW MA | 0.9–1.0 | 0–0.1 flood margin | med | y | 20–30 | buttressed trunk with knees and feathery drooping foliage | fresh green; rust autumn; grey-green | author (Species BaldCypress; CypressKnees as a prop) | SW4 MA2 |
| larch_sparse | canopy | TG IH | 0.3–0.6 | 0.3–1.0 cold slopes | low | n | 12–20 | thin pale trunks with an airy crown and long sightlines | soft green; gold autumn; grey trunk | author | TG2 IH1 |
| cottonwood_river | canopy | MA SW | 0.7–1.0 | 0–0.2 floodplain | med | y | 20–30 | tall spreading crown on a pale trunk, quaking leaves | light green; yellow; silver underside | author | MA2 SW1 |
| emergent_fig | canopy | WR | 0.7–1.0 | 0–0.4 | med | n | 25–40 | buttressed trunk with a vine-draped broad crown above the understory | dark green; glossy; mottled grey | author | WR4 |
| birch_pale | subcanopy | TF | 0.4–0.7 | 0–0.6 cool slopes | med | n | 10–18 | slender white-barked stems with small leaves in an airy crown | white bark; light green; yellow | PolyHaven (birch) | TF2 |
| krummholz_pine | subcanopy | RH IH TG | 0.3–0.7 | 0.6–1.0 exposed | low | n | 1–3 | flattened windswept mat with a one-sided crown | dark green; grey-green; bronze | author (Species Krummholz); existing:pine_sapling_small as fallback candidate | RH2 IH2 TG1 |
| understory_laurel | subcanopy | WR CR OG | 0.6–0.9 | 0–0.5 | high | n | 5–10 | low tree with several short trunks and glossy broad leaves | glossy green; bronze new growth; dark olive | author | WR3 CR2 OG2 |
| juniper_low | shrub | RH DG TG IH | 0.2–0.5 | 0.3–1.0 | med | n | 0.5–1.5 | sprawling low mound with spiky needle tufts | blue-grey; green; dark | author | RH2 DG2 TG2 IH1 |
| heather_dwarf | shrub | RH TG IH | 0.4–0.7 | 0.2–1.0 peaty folds | med | n | 0.3–0.8 | dense low cushion of tiny leaves | purple; dull green; rust | author | RH1 TG2 IH1 |
| hazel_coppice | shrub | TF OG | 0.4–0.7 | 0–0.5 | med | n | 2–5 | many thin stems rising from one clump, round leaves | green; yellow-green; brown stems | PolyHaven (hazel) | TF3 OG1 |
| thorn_scrub | shrub | SV DG | 0.1–0.4 | 0–0.4 | low | n | 1–3 | dense thorny clump with hooked branches | grey-green; olive; dry brown | author | SV3 DG2 |
| willow_shrub | shrub | MA SW | 0.8–1.0 | 0–0.1 | med | y | 2–6 | drooping thin stems in an arching clump | grey-green; silver; yellow-green | author | MA3 SW2 |
| sumac_scrub | shrub | SV PR DG | 0.2–0.5 | 0–0.5 | low | n | 1–3 | rounded multi-stem thicket with feathery compound leaves | green; red autumn; yellow | author | SV2 PR2 DG1 |
| salal_understory | shrub | CR OG | 0.6–0.9 | 0–0.5 | high | n | 0.5–1.5 | low arching leafy mound of waxy leaves | dark glossy green; reddish; pale green | author | CR3 OG1 |
| bilberry_low | shrub | TG CR IH | 0.5–0.8 | 0–0.6 | med | n | 0.3–0.6 | low wiry mat with small rounded leaves | green; red autumn; blue-green | author | TG2 CR2 IH1 |
| alder_thicket | shrub | SW MA CR | 0.7–1.0 | 0–0.3 | med | y | 3–6 | dense round-headed multi-stem thicket | dark green; grey-green; rust catkin | author | SW2 MA2 CR1 |
| sagebrush_grey | shrub | DG RH | 0.1–0.3 | 0–0.8 | low | n | 0.5–1.2 | grey-green rounded bush of fine leaf mass | silver grey; blue-grey; pale | author | DG3 RH1 |
| liana_cluster | shrub | WR | 0.6–0.9 | 0–0.5 | med | n | 1–4 | ropey clustered stems looping up low trunks | green; dark; olive | author | WR2 |
| understory_ginger | shrub | WR | 0.7–0.9 | 0–0.4 | high | n | 0.8–1.5 | upright leafy stalks with broad lance leaves | bright green; variegated; maroon | author | WR3 |
| prickly_pear | shrub | DG SV | 0.1–0.3 | 0–0.5 | low | n | 0.5–1.5 | flat pad clusters with spines | blue-green; grey-green; purple-tinged | author | DG1 SV2 |
| fern_02 | fern | TF OG CR WR SW | 0.5–0.9 | 0–0.6 | high | n | 0.6–1.5 | arching fronds from a central crown | green; yellow-green; dark green | existing:fern_02 (Prepared fern_02_00 to _03) | TF3 OG3 CR3 WR2 SW1 |
| bracken | fern | TF OG PR DG | 0.3–0.6 | 0–0.5 | low | n | 0.8–2 | tall triangular fronds in dense stands | green; ochre autumn; yellow | PolyHaven (bracken) | TF2 PR2 OG1 DG1 |
| tree_fern | fern | WR CR | 0.7–0.95 | 0–0.4 | high | n | 3–7 | single upright trunk crowned by umbrella fronds | green; blue-green; dark | author | WR3 CR2 |
| royal_fern | fern | SW MA | 0.8–1.0 | 0–0.1 | med | y | 1–2 | upright clustered fronds with tassel tips | green; rust; yellow-green | author | SW2 MA2 |
| lady_fern | fern | TF CR OG | 0.5–0.8 | 0–0.6 | high | n | 0.4–0.9 | lacy fine fronds in tight vase clumps | pale green; blue-green; light | PolyHaven (fern) | TF2 CR2 OG1 |
| rock_fern | fern | RH TG | 0.3–0.6 | 0.4–1.0 rock crevices | med | n | 0.1–0.3 | tiny rosettes clinging to stone | grey-green; dark; silver-green | author | RH1 TG1 |
| grass_medium_01 | grass | TF OG DG PR | 0.3–0.7 | 0–0.6 | low | n | 0.4–0.9 | clumped mid-height blades | green; straw; olive | existing:grass_medium_01 (Prepared _00 to _16) | DG3 PR2 TF2 OG1 |
| grass_medium_02 | grass | DG SV PR MA | 0.2–0.6 | 0–0.5 | low | n | 0.5–1 | fine upright tufts | gold; green; pale | existing:grass_medium_02 (Prepared _00 to _04) | DG3 SV2 PR2 MA1 |
| grass_bermuda_01 | grass | SV DG PR | 0.1–0.5 | 0–0.5 | low | n | 0.2–0.5 | low dense mat with runners | blue-green; straw; brown | existing:grass_bermuda_01 (Prepared _00 to _20) | SV3 DG2 PR1 |
| prairie_bunchgrass | grass | PR DG RH | 0.2–0.5 | 0–0.8 | low | n | 0.6–1.2 | tall arching bunches with seed heads | straw; gold; grey-green | author (Species PrairieGrass) | PR4 DG2 RH1 |
| alpine_tussock | grass | RH IH TG | 0.3–0.7 | 0.3–1.0 | low | n | 0.1–0.4 | dense rounded tussock on stony ground | grey-green; straw; dark | author | RH2 IH2 TG1 |
| wet_sedge | grass | MA SW | 0.8–1.0 | 0–0.1 | med | y | 0.3–0.8 | triangular stems in tight clumps | green; olive; rust | author | MA3 SW1 |
| shade_grass | grass | OG TF | 0.5–0.8 | 0–0.5 | high | n | 0.2–0.5 | fine low blades in shaded patches | dark green; blue-green; yellow-green | PolyHaven (shade grass) | OG2 TF1 |
| frost_fescue | grass | IH RH | 0.3–0.6 | 0.4–1.0 | low | n | 0.1–0.3 | fine pale hair-like tufts in cracks | pale grey-green; frosted white; straw | author | IH2 RH1 |
| common_reed | reed | MA SW | 0.9–1.0 | 0–0.1 | low | y | 2–3.5 | tall dense stems with feathery plume tops | green; straw; grey-brown | author | MA4 SW2 |
| cattail | reed | MA SW | 0.9–1.0 | 0–0.1 | low | y | 1.5–2.5 | straight stems with brown sausage heads | green; brown; cream | author (Species Cattail) | MA3 SW2 |
| horsetail | reed | MA OG | 0.7–1.0 | 0–0.3 | high | y | 0.3–1.0 | jointed green stems in dense stands | green; dark green; grey-green | author | MA2 OG1 |
| bamboo_stand | reed | WR | 0.7–0.9 | 0–0.4 | med | n | 4–8 | tall thin segmented culms with sparse leaf tufts | green; yellow culm; dark green | author | WR2 |
| meadow_flower_mix | flower | TF DG RH PR SV | 0.3–0.6 | 0–0.8 | low | n | 0.2–0.6 | scattered multi-colour stems with small heads | yellow; white; violet; pink | author (cluster of three stems) | PR4 DG2 SV1 RH1 TF1 |
| lupine | flower | PR RH | 0.3–0.6 | 0–0.6 | low | n | 0.6–1.0 | tall spires of palmate leaves with flower spikes | blue; violet; pink | PolyHaven (lupine) | PR2 RH1 |
| arctic_poppy | flower | IH TG RH | 0.2–0.5 | 0.3–1.0 | low | n | 0.1–0.3 | single bowl blooms on thin stems above rosettes | white; yellow; orange | author | IH2 TG1 RH1 |
| swamp_iris | flower | SW MA | 0.9–1.0 | 0–0.1 | med | y | 0.5–1.0 | sword leaves with upright blue flower spikes | blue-violet; yellow; cream | author | SW1 MA2 |
| heliconia_bloom | flower | WR | 0.7–0.9 | 0–0.4 | med | n | 1–2 | upright red-orange bracts with pointed blooms | red; orange; yellow | author | WR2 |
| forest_anemone | flower | TF OG | 0.4–0.7 | 0–0.5 | high | n | 0.1–0.3 | small white star blooms above three-lobed leaves | white; pale pink; cream | PolyHaven (anemone) | TF2 OG2 |
| savanna_sunflower | flower | SV DG PR | 0.1–0.4 | 0–0.5 | low | n | 0.6–1.4 | single-stem daisy heads on rough stems | yellow; orange; brown centre | author | SV2 DG1 PR1 |
| cotton_grass | flower | MA TG | 0.8–1.0 | 0–0.3 | low | y | 0.3–0.5 | thin stems with white fluff heads | white; cream; grey-green | author | MA2 TG1 |
| frost_saxifrage | flower | IH RH | 0.2–0.5 | 0.4–1.0 | low | n | 0.05–0.15 | tiny rosette cushion with starry white flowers | white; silver-green; pale pink | author | IH1 RH1 |
| water_lily | aquatic | SW MA | 1.0 | 0 open water | low | y | 0–0.2 surface | round floating pads with star flowers | green; dark green; red-tinged | author | MA3 SW2 |
| duckweed_mat | aquatic | MA | 1.0 | 0 open water | med | y | 0 surface | flat mat of tiny round fronds (decal or instanced mat) | bright green; yellow-green; red-tinged | author | MA2 |
| pondweed | aquatic | MA SW TG | 1.0 | 0 submerged | med | y | 0–0.5 submerged | submerged ribbon stems with floating tips | green; olive; brown-green | author | MA1 SW1 TG1 |
| feather_moss | moss | TF CR | 0.6–0.9 | 0–0.6 | high | n | 0.02–0.05 | soft feathery carpet on logs and ground | green; yellow-green; dark | Vivarium:game/Textures/Moss002_1K-JPG_Color.jpg | TF2 CR3 |
| sphagnum_hummock | moss | TG SW CR | 0.9–1.0 | 0–0.1 | med | y | 0.05–0.2 | puffy hummocks mixing pale and red moss | pale green; rust-red; cream | author (instanced hummock) with Vivarium:Moss002 colour | TG2 SW2 CR1 |
| lichen_crust | moss | RH IH TG | 0.2–0.6 | 0.2–1.0 rock | med | n | 0.01–0.05 | flat grey-green crust on stone with leafy edges | grey-green; pale yellow; orange-brown | Vivarium:game/Textures/LichenThallus.png | RH2 IH2 TG2 |
| ground_moss_carpet | moss | CR OG | 0.7–0.95 | 0–0.5 | high | n | 0.02–0.06 | tight cushion over roots and soil | bright green; dark green; olive | Vivarium:game/Textures/Moss002_1K-JPG_Color.jpg | CR3 OG2 |
| rock_moss_patch | moss | RH CR | 0.6–0.9 | 0.2–1.0 | high | n | 0.05–0.2 | green cushion draped over stone faces | green; grey-green; dark | existing:rock_moss_set_01, rock_moss_set_02 (moss on rock props, not standalone flora); Vivarium:Moss002 | RH2 CR1 |
| bracket_fungus | fungus | OG TF CR | 0.6–0.9 | 0–0.5 | high | n | 0.05–0.3 | stacked shelf brackets on dead trunks | cream; orange-brown; grey | author | OG2 TF1 CR1 |
| puffball_cluster | fungus | TF | 0.5–0.8 | 0–0.4 | med | n | 0.05–0.2 | clustered round white bulbs on litter | cream; tan; grey-brown | author | TF1 |
| ground_fungus_patch | fungus | SW WR OG | 0.7–1.0 | 0–0.2 | high | n | 0.05–0.15 | low flat caps in clusters on wet litter | ochre; grey; orange | author | OG1 SW1 WR1 |

## Species — unreal-only (LeafPools overlay, 4)

Not counted toward per-biome viability. Placed only in overlay cells (about one tenth of cells, per BiomeCatalog motifs) on top of the physical family listed. Atlases: `Vivarium:game/Textures/LeafPools/Masters/<name>-0..3.png` for four colour variants; per-species `color`, `normal`, `physical`, `vein_mask`, `vein_normal` sets sit in `LeafPools/<name>/`.

| ID | role | overlay | moisture | elev/slope | shade | water | height_m | silhouette | colour variants | source | density weight |
|---|---|---|---|---|---|---|---|---|---|---|---|
| shadebell | shrub | motif 45 unnaturally dark forest on TF OG | 0.6–0.9 | 0–0.5 | high | n | 0.8–2 | cupped bell-shaped leaves in tight clusters | 4 (Masters -0 to -3) | Vivarium:LeafPools/shadebell | OG1 TF1 (overlay only) |
| lanternbrush | reed | motif 44 luminous moss woodland on TF OG and MA | 0.8–1.0 | 0–0.3 | med | y | 1–2.5 | upright lantern-shaped leaf clusters on thin stalks | 4 (Masters -0 to -3) | Vivarium:LeafPools/lanternbrush | MA1 (overlay only) |
| glassfinger | fern | motif 47 glassy mineral woodland on RH TG | 0.3–0.7 | 0.3–1.0 | med | n | 0.3–1 | translucent finger-like fronds rising from stone | 4 (Masters -0 to -3) | Vivarium:LeafPools/glassfinger; also Vivarium:Leaves/GlassfingerLeaf_2K-JPG | RH1 (overlay only) |
| embercrown | subcanopy | motif 54 inverted-colour rainforest on WR CR | 0.6–0.9 | 0–0.4 | med | n | 4–8 | crown of warm broad leaves with ember-coloured veining | 4 (Masters -0 to -3) | Vivarium:LeafPools/embercrown | WR1 (overlay only) |

## Existing asset mapping

- Species enum to catalogue ID: Pine to pine_open; Broadleaf to oak_broadleaf; BroadleafGiant to broadleaf_giant; Conifer to spruce_conifer; Evergreen to evergreen_broad; Acacia to acacia_flat; BaldCypress to baldcypress; CypressKnees to baldcypress (prop); Cattail to cattail; PrairieGrass to prairie_bunchgrass; Krummholz to krummholz_pine.
- ArtSource Prepared/PolyHaven mapped directly: pine_tree_01 to pine_open; pine_sapling_small to pine_open (saplings); fern_02 to fern_02; grass_medium_01 to grass_medium_01; grass_medium_02 to grass_medium_02; grass_bermuda_01 to grass_bermuda_01; dead_tree_trunk and dead_tree_trunk_02 to deadwood_snag; rock_moss_set_01 and rock_moss_set_02 to rock_moss_patch (prop context).
- UNVERIFIED by filename only: tree_broadleaf_00 to oak_broadleaf; tree_broadleaf_01 to broadleaf_giant; fir_tree_01 to spruce_conifer; tree_small_02 to evergreen_broad; island_tree_01 is not mapped to acacia_flat.
- Non-flora, do not map: rock_01, rock_07, boulder_01, picnic, fence and bin assets.
- Vivarium ground cards (not species): Bark*, Ground*, Gravel*, ScatteredLeaves007 (litter ground). Vivarium Moss002 and LichenThallus map to moss rows above.

## Per-role authoring batches (parallel Blender Clankers, max 10 each)

- canopy-a (6): pine_open, oak_broadleaf, broadleaf_giant, spruce_conifer, evergreen_broad, deadwood_snag
- canopy-b (5): acacia_flat, baldcypress, larch_sparse, cottonwood_river, emergent_fig
- subcanopy (3): birch_pale, krummholz_pine, understory_laurel (embercrown is unreal-only, deferred)
- shrub-a (7): juniper_low, heather_dwarf, hazel_coppice, thorn_scrub, willow_shrub, sumac_scrub, salal_understory
- shrub-b (6): bilberry_low, alder_thicket, sagebrush_grey, liana_cluster, understory_ginger, prickly_pear
- fern (6): fern_02, bracken, tree_fern, royal_fern, lady_fern, rock_fern (glassfinger deferred)
- grass (8): grass_medium_01, grass_medium_02, grass_bermuda_01, prairie_bunchgrass, alpine_tussock, wet_sedge, shade_grass, frost_fescue
- reed (4): common_reed, cattail, horsetail, bamboo_stand (lanternbrush deferred)
- flower (9): meadow_flower_mix, lupine, arctic_poppy, swamp_iris, heliconia_bloom, forest_anemone, savanna_sunflower, cotton_grass, frost_saxifrage
- aquatic (3): water_lily, duckweed_mat, pondweed
- moss (5): feather_moss, sphagnum_hummock, lichen_crust, ground_moss_carpet, rock_moss_patch
- fungus (3): bracket_fungus, puffball_cluster, ground_fungus_patch

Authoring note: several batches are already covered by existing assets (fern_02, grass_*, pine). Those rows need variant generation only, not new modelling.

## Per-biome density targets (instances per 100 m²)

Initial targets for placement tuning. Treat as ceilings to tune against the render review, not measured values. Unreal overlay cells use these values times 0.1.

| Biome | canopy | subcanopy | shrub | fern | grass | flower | fungus | moss | reed | aquatic |
|---|---|---|---|---|---|---|---|---|---|---|
| TemperateForest | 1.5 | 1.0 | 3 | 4 | 6 | 2 | 1 | 3 | 0 | 0 |
| DryGrassland | 0.3 | 0 | 2 | 0.2 | 20 | 3 | 0 | 0.5 | 0 | 0 |
| RockyHighlands | 0.6 | 0.4 | 4 | 0.5 | 12 | 2 | 0 | 3 | 0 | 0 |
| Taiga | 2.0 | 0.5 | 4 | 1 | 6 | 1 | 0 | 6 | 0 | 0.2 |
| OldGrowthForest | 1.5 | 1.0 | 3 | 6 | 4 | 2 | 2 | 5 | 0.5 | 0 |
| ColdRainforest | 2.0 | 1.5 | 6 | 8 | 3 | 1 | 2 | 8 | 0.5 | 0.2 |
| IcyHills | 0.5 | 0.2 | 2 | 0 | 3 | 1 | 0 | 3 | 0 | 0 |
| Savannah | 0.4 | 0 | 3 | 0 | 22 | 2 | 0 | 0 | 0 | 0 |
| Swamp | 1.5 | 0.5 | 5 | 2 | 3 | 1 | 1 | 4 | 10 | 4 |
| Marsh | 0.4 | 0.3 | 4 | 1 | 8 | 4 | 1 | 1 | 20 | 6 |
| WarmRainforest | 2.5 | 2.5 | 8 | 6 | 2 | 3 | 2 | 0.5 | 2 | 0.5 |
| Prairie | 0.1 | 0 | 2 | 1 | 25 | 6 | 0 | 0 | 0 | 0 |

## Coverage check

- Species per biome family (from the weight codes above): TemperateForest 15, DryGrassland 14, RockyHighlands 15, Taiga 14, OldGrowthForest 15, ColdRainforest 14, IcyHills 10, Savannah 9, Swamp 15, Marsh 15, WarmRainforest 10, Prairie 9. Every family is within 8–15.
- Species total: 65 biome flora plus 4 unreal-only = 69.
- Biomes differ: no species appears in all 12 families; the broadest (meadow_flower_mix) is in 5.
