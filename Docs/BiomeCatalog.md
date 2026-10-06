# The Wood — biome roster

Concept specification · 6 October 2026

This roster defines planned environmental families and regional variants. It is not an inventory of implemented assets. The current generator implements temperate forest, dry grassland, rocky highlands and taiga using a limited shared pine library. The [generation specification](BiomeGeneration.md) defines hex ownership and edge-local blending; the [discovery catalog](DiscoveryCatalog.md) defines what can be found within these places.

A family describes broad climate/ecology; a variant describes a cell's recognizable character. Similar variants can be adjacent without a jarring scene change. Smaller habitats—fern hollows, streambanks, grass openings, shaded pools—occur inside every appropriate family. This is artistically believable scenery, not a botanical classification system.

## Temperate and cool woodland

| Variant | Visual character | Terrain, water and useful small habitats |
| --- | --- | --- |
| 1. Mixed temperate woodland | Varied crowns, moderate light and layered understory | Gentle folds, litter pockets, streams and grassy openings |
| 2. Old-growth temperate forest | Huge trunks, irregular canopy, fallen timber and deep shade | Root hollows, moss-covered logs and sheltered clearings |
| 3. Open oak-like woodland | Broad crowns above grasses and scattered shrubs | Dry rolling ground, occasional shallow watercourses |
| 4. Birch-like pale woodland | Light trunks and small leaves; airy diffuse light | Cool slopes, fern bands and young regeneration patches |
| 5. Pine woodland | Open needle canopy, warm bark and sparse floor | Sandy ridges, rocky clearings and dry litter |
| 6. Dense conifer forest | Closely layered dark crowns and strong depth | Sheltered valleys, deadwood and narrow light gaps |
| 7. Cold temperate rainforest | Saturated moss, ferns, dripping branches and soft mist | Ravines, abundant streams, root buttresses and wet rock |
| 8. Foggy coastal-like forest | Wind-shaped edges, subdued color and persistent low cloud | Exposed shoulders and sheltered hollows; an actual coast is unnecessary |
| 9. Autumn-toned woodland | Warm leaves, pale shafts and deep litter | Mixed slopes, leaf-filled pools and quiet glades |
| 10. Coppice and young woodland | Many thin stems, vigorous shrubs and shifting visibility | Regeneration patches alternating with older canopy |
| 11. Ravine forest | Trees frame a narrow wet floor and steep rock | Continuous drainage, fern banks and occasional crossings |
| 12. Dry deciduous forest | Sparse understory, dusty light and broken canopy | Rough soil, exposed roots and seasonal-looking channels |

## Open and dry country

| Variant | Visual character | Terrain, water and useful small habitats |
| --- | --- | --- |
| 13. Tallgrass prairie | Wind-driven grass waves and broad open sky | Rolling ground, flower patches, swales and isolated trees |
| 14. Shortgrass steppe | Low grasses, bare soil and distant silhouettes | Gentle relief, stone clusters and sparse drainage |
| 15. Open savannah | Widely spaced broad trees above warm grasses | Dry slopes, shaded islands and occasional water pockets |
| 16. Thorny scrubland | Dense low shrubs with open dusty gaps | Rocky ground, dry gullies and small sheltered groves |
| 17. Heath and moorland | Low flowering shrubs, muted purples and exposed wind | Peaty folds, rocky knolls and shallow rills |
| 18. Dry upland meadow | Fine pale grasses, flowers and scattered rock | Walkable hills, exposed outcrops and cooler hollows |
| 19. Sandy woodland | Loose-looking ground and sparse pine-like crowns | Low dunes or sandy ridges, roots and dry depressions |
| 20. Semi-arid badlands | Eroded earth, subdued vegetation and sculpted relief | Drainage fingers, clay banks and narrow vegetated channels |
| 21. Rust-red rocky scrub | Warm mineral ground and hardy vegetation | Layered outcrops, scree, dry washes and isolated shade |
| 22. Chalk-like downland | Pale ground, short turf and soft rolling horizons | Gentle escarpments, scattered shrubs and protected valleys |

## Highlands and cold country

| Variant | Visual character | Terrain, water and useful small habitats |
| --- | --- | --- |
| 23. Rocky highlands | Rough outcrops, scattered trees and mineral ground | Ridges, passes, fast rills and overlook shoulders |
| 24. Granite uplands | Rounded tors, sparse turf and exposed wind | Boulder clefts, talus and sheltered moss pockets |
| 25. Basalt-like highlands | Dark fractured stone and column rhythms | Broken ridges, stream steps and contrasting grass |
| 26. Alpine-like meadow | Low flowers, short vegetation and cool clear light | High rolling benches, snowmelt-like streams and stone fields |
| 27. Taiga | Conifers, cold ground color and subdued understory | Moss, lichen, gravel streams and open rocky pockets |
| 28. Sparse larch-like woodland | Thin crowns and long sightlines through pale trunks | Cold slopes, low shrubs and wet depressions |
| 29. Tundra | Very low plants, lichen and exposed soil | Microrelief, stones, shallow pools and wind-shaped shrubs |
| 30. Icy hills | Frost, intermittent snow and dark exposed rock | Rounded relief, icy rills and safer sheltered routes |
| 31. Snow-heavy forest | Snow-defined branches and quiet high contrast | Drifts, partially open streams and dense sheltered canopy |
| 32. Glacial gravel plain | Pale stones, cold light and distant isolated masses | Braided channels, moraine ridges and sparse hardy plants |

## Wetlands and humid country

| Variant | Visual character | Terrain, water and useful small habitats |
| --- | --- | --- |
| 33. Forest swamp | Dark water between trunks and layered shade | Shallow pools, root islands and grounded fallen timber |
| 34. Open marsh | Broad reeds, grasses and reflective channels | Low relief, wet meadows and many walkable margins |
| 35. Peat bog | Dark pools, low shrubs and pale or rust-colored moss | Hummocks, shallow water and drier connected footing |
| 36. Fen | Rich grasses, sedges and spring-fed wetness | Seep lines, clearer pools and dense plant zoning |
| 37. Floodplain woodland | Mixed canopy above silt, reeds and water marks | Channel bends, gravel bars and occasional pooled hollows |
| 38. Wet meadow | Bright low vegetation and scattered reflective patches | Gentle ground, flowering patches and small drainage |
| 39. Reed labyrinth | Dense tall reeds with glimpsed open pools | Branching shallows and multiple readable walking passages |
| 40. Warm rainforest | Layered broad leaves, vines and humid depth | Streams, buttressed roots, glades and rich shade |
| 41. Cloud forest | Moss-heavy branches and cool suspended mist | Steep but traversable folds, seepage and fern shelves |
| 42. Tree-fern-like wet forest | Strong umbrella forms and saturated ground | Sheltered hollows, stone-lined streams and irregular clearings |

## Unreal regional overlays and variants

Approximately one tenth of cells receive sustained unreal ecology/atmosphere. These variants build on a physical family rather than abandon all terrain and habitat rules. A strange structure in an otherwise ordinary cell does **not** require this flag. A pristine suburban house can stand in an ordinary bog; a gigantic sword can stand in ordinary prairie.

| Motif | Regional expression | Grounding and restraint |
| --- | --- | --- |
| 43. Excessively fungal forest | Large fruiting bodies, fungal shelves and unfamiliar canopy layers | Shared moisture and decay logic; stems and hosts remain grounded |
| 44. Luminous moss woodland | Soft light from selected moss and fungi | Small coherent emission palette; retain dark resting areas |
| 45. Unnaturally dark forest | Light seems absorbed beneath deep crowns | Traversable ground remains readable; no forced threat |
| 46. Pale enchanted grove | Ivory bark, muted leaves and unusually soft light | Preserve surface detail and shadows instead of flat white geometry |
| 47. Glassy mineral woodland | Translucent-looking mineral forms among trees | Controlled reflections, physical support and limited repetition |
| 48. Violet twilight heath | Unusual vegetation color and a long dusky light cycle | No visible sun; color variation still has material texture |
| 49. Oversized understory hollow | Ferns, leaves and fungi exaggerate human scale | Keep walking gaps and believable branching structures |
| 50. Root-woven forest | Large root networks shape views and small terrain shelters | Ground contact, supports and traversal; true overhangs need later topology |
| 51. Ash-pale silent woodland | Powdery pale surfaces, subdued plants and strange stillness | Do not require catastrophe lore or hostile wildlife |
| 52. Metallic reed marsh | Unfamiliar sheen and ringing-looking plant forms | Wind and water remain coherent; avoid pervasive glitter noise |
| 53. Frosted warm grove | Frost-like mineral surfaces within a warm-looking habitat | Deliberate local contradiction; smooth atmosphere transition |
| 54. Inverted-color rainforest | Restrained unusual foliage/bark palette, ordinary spatial depth | One controlled color idea, not randomized rainbow materials |

## Selection and variation rules

- Weight ordinary families through temperature, moisture, elevation tendency, exposure and substrate; use the bounded neighbor compatibility pass in the generation spec.
- Family labels do not prescribe exact species or demand strict scientific realism. Each needs a recognizable silhouette, ground treatment, density and atmospheric character.
- Vary age and size cohorts, canopy openness, roughness, wetness and local habitats within a family. Two temperate cells should not be copies.
- Allow unusual neighboring families through ecotones. Transition vegetation can combine the two without inventing a strip of generic mixed forest at every boundary.
- A biome's physical traits constrain **how** an artifact sits in the landscape, not which historical genre is permitted. Pristine, industrial, ancient and fantastical objects are all valid.
- Snow, dense rainforests, reed fields and reflective minerals need their own asset/performance acceptance; the catalog is not a promise to deliver all families at once.
- Expand ordinary families and unreal motifs incrementally. Initial four-family implementation is a foundation; shrub, broadleaf, reed, snow and other distinct asset kits remain future content.
