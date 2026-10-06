# The Wood — discovery and prop catalog

Concept specification · 6 October 2026

This catalog describes possible generated discoveries for the proposed biome-cell layout. It is a future content library, not an inventory of assets already owned or features already implemented. The [detailed hex layout specification](BiomeGeneration.md) defines cell geometry and neighboring influences; this document defines what a place can contain and what its generation needs to account for.

Discoveries support wandering, recognition, sitting and photographs. They provide no required objectives, loot, combat encounters or completion checklist. A cell should feel like a landscape containing occasional things worth noticing, not a park packed with marked attractions.

## Placement and composition rules

Reserve up to **one primary landmark and zero to two secondary discoveries per cell** as an initial composition budget. This is a ceiling, not a quota. A quiet cell may have no specially authored discovery; an ordinary ridge or changing canopy can carry its identity. Primary landmarks compete for silhouette, route and attention. Secondary discoveries should complement the place rather than create three unrelated spectacles.

Approximately **one third of cells** are eligible for a constructed discovery (ruin, intact structure or anomalous artifact), independently of the approximately **one tenth** later eligible for unreal character. An eligible cell still needs a suitable site. Do not force a structure onto unsuitable terrain or silently reroll its family until every eligible cell becomes densely developed. Record candidate rejection for debugging; tune actual occurrence across many cells rather than repairing individual seeds. Discoveries of any era or genre can appear in ordinary or unreal cells. Environmental fit concerns grounding, access and visual composition, not whether the object historically belongs there.

Generate a ruin as one composition record, not a scatter of random wall meshes. That record establishes family, footprint, orientation, foundation, scale, construction logic, damage history, access, drainage and overgrowth. Child pieces inherit those choices. A broken bridge must align its abutments across a channel; a collapsed roof must leave plausible supports and debris; vegetation must respond to shade and retained moisture.

Natural discoveries also need composition records when multiple systems meet. A falls-and-pool site reserves its elevation break and channel before ground realization. A wind-shaped grove reserves exposure and tree orientation before habitat placement. Features consume the shared terrain, water and habitat queries; they do not guess conditions independently.

All dimensions below are approximate footprint spans, not final mesh specifications. **H** means compatible with the initial heightfield plus fitted meshes. **F** means future topology or traversal work is required. The latter may be planned now but must not become a hidden dependency of the first milestone.

## Ruins, structures and unexplained objects

The discovery library deliberately spans eras, genres, scales and degrees of preservation. An ancient marble temple, an industrial smokestack, a gigantic rusted sword and a pristine suburban house can belong to the same wilderness. They do not need a shared civilization, historical timeline, explanation or story payoff. A structure may be intact, maintained-looking, partly ruined, buried or almost erased.

Keep physical presentation convincing: foundations contact ground, water meets walls coherently, materials have readable scale, and shadows belong to the scene. Historical or functional plausibility is optional. An unexplained staircase may genuinely lead nowhere; it still needs grounded supports. Do not add surrounding industrial rubble merely to explain a solitary smokestack, or distress the pristine house merely because it is in a bog. Change preservation, setting and composition as well as architecture.

The approximately one-third ruin allocation is the **constructed-discovery allocation**, covering ruins, intact structures and anomalous artifacts. These count within the same quiet discovery budget. They are not restricted to unreal-flagged biomes: a perfectly ordinary forest may contain an impossible object. The one-tenth unreal flag describes sustained regional ecology/atmosphere, independently of a discovery's era or genre.

| Assembly | Span / role | Suitable habitat and site prerequisites | Composition dependencies |
| --- | --- | --- | --- |
| 1. Cottage shell | 8–18 m; secondary | Forest edge; modest dry bench | Foundation, doorway route, collapsed roof footprint |
| 2. Farmstead courtyard | 25–60 m; primary | Prairie or savannah; broad gentle ground | Related buildings, yard, old boundary and drainage |
| 3. Shepherd shelter | 3–8 m; secondary | Highland; sheltered slope pocket | Low wall windward, level resting patch |
| 4. Roofless longhouse | 15–35 m; primary | Taiga or temperate clearing | Repeated structural bays, inward/outward collapse |
| 5. Barn skeleton | 12–30 m; primary | Grassland margin; accessible flat site | Timber frame, roof debris, former entrance apron |
| 6. Dry-stone livestock pen | 10–35 m; secondary | Open grassland; shallow slopes | Continuous enclosure, gap, terrain-following walls |
| 7. Terraced garden remnant | 15–70 m; primary | Moist slope; usable contour bands | Retaining walls, steps, terrace soils and runoff |
| 8. Orchard enclosure | 20–60 m; primary | Temperate clearing; drained soils | Wall outline, irregular old tree cohort, shaded ground |
| 9. Wayside shrine | 2–6 m; secondary | Most habitats; small stable ledge | Pedestal contact, approach and restrained vegetation |
| 10. Chapel fragment | 10–30 m; primary | Forest or prairie; dry foundation site | Nave outline, surviving arch, coherent rubble fall |
| 11. Cloister corner | 20–50 m; primary | Sheltered forest; broad bench | Courtyard, matching arcade bays, planted encroachment |
| 12. Gatehouse stump | 8–20 m; primary | Pass or old track; traversable opening | Paired masses, gateway scale and approach corridor |
| 13. Watchtower base | 5–12 m; primary | Ridge; stable visible shoulder | Thick footing, height budget and downward rubble fan |
| 14. Hill fort wall | 35–120 m; primary | Highland; defensible contour | Wall continuity, breaks, contour-following access |
| 15. Isolated stair flight | 3–15 m; secondary | Slope with real level difference | Lower/upper landings, usable stair angle and contact |
| 16. Broken footbridge | 8–25 m; primary | Narrow stream; stable opposite banks | Matched abutments, span direction, alternate safe crossing |
| 17. Stone bridge pier | 4–12 m; secondary | River reach; credible old crossing | Flow clearance, pier footing, flood staining |
| 18. Aqueduct segment | 20–80 m; primary | Valley edge; coherent elevation | Aligned piers, consistent channel grade and collapse |
| 19. Mill foundation | 10–30 m; primary | Flowing stream; suitable fall | Race channel, wheel pit, bank walls and return flow |
| 20. Sluice house remnant | 4–12 m; secondary | Wetland outlet; channel junction | Gate slot, embankment and water-level relationship |
| 21. Culvert headwalls | 3–10 m; secondary | Drainage under former track | Inlet/outlet agreement; **F** if walkable enclosed passage |
| 22. Cistern rim | 3–10 m; secondary | Dry country; sheltered collection site | Basin, partial infill, safe rim and runoff catchment |
| 23. Well surround | 1–4 m; secondary | Settlement remnant; stable ground | Grounded ring; filled opening for initial **H** version |
| 24. Bathhouse floor | 10–25 m; primary | Moist valley; foundation bench | Basin plan, drains, tiled remnants and wall supports |
| 25. Kiln shell | 4–12 m; secondary | Dry margin; open working apron | Fired masonry, opening, localized debris and discoloration |
| 26. Quarry yard | 20–80 m; primary | Rocky highland; exposed stone face | Cut marks, spoil heaps, blocks and walking connection |
| 27. Mason's work site | 5–20 m; secondary | Near suitable outcrop | Related unfinished blocks, working ground, limited scatter |
| 28. Forest sawmill remnant | 15–40 m; primary | Forest/stream edge; flat pad | Foundation, frame and old timber piles coherent in age |
| 29. Abandoned rail embankment | 30–120 m; primary | Broad valley; low-gradient route | Continuous grade, drainage cuts and sparse track remnants |
| 30. Platform and signal post | 15–50 m; primary | Former transport corridor | Platform edge, aligned trackbed and restrained furniture |
| 31. Collapsed boardwalk | 10–60 m; secondary | Marsh; shallow traversable water | Supports reach substrate; gaps do not trap the player |
| 32. Boathouse footings | 6–20 m; secondary | Quiet bank; credible water access | Slipway slope, shoreline level and timber remains |
| 33. Fire lookout remnant | 6–15 m; primary | Forest ridge; wide sightlines | Anchored base, stairs or safe inaccessible upper remains |
| 34. Survey shelter | 3–10 m; secondary | Highland or taiga; exposed working site | Shelter orientation, sparse equipment supports, weathering |
| 35. Buried entrance facade | 4–15 m; secondary | Stable bank or slope | Retaining mass and infill; explorable interior is **F** |
| 36. Monument court | 10–35 m; primary | Open glade; modest level clearing | Central mass, broken paving, respectful quiet composition |

### Expanded cross-era and anomalous discoveries

| Assembly | Span / role | Setting and site needs | Composition and variation |
| --- | --- | --- | --- |
| 37. Ancient crumbling marble temple | 20�90 m; primary | Forest glade, savannah or stony shoulder; stable foundations | Columns, cracked stylobate, fragments of pediment; intact bays versus collapsed sections; moss optional |
| 38. Thoroughly overgrown farmstead | 30�100 m; primary | Forest, grassland or wet woodland; related foundation sites | House, barn, orchard remnants and swallowed yard; roots and vegetation reclaim different parts |
| 39. Ten-metre rusted sword | 10 m exposed height; primary | Any family; footing strong enough for embedded mass | Blade thrust into ground, visible hilt, localized ground displacement and corrosion; no required legend or loot |
| 40. Single smokestack in a grove | 15�45 m high; primary | Tree grove; grounded chimney base and viewing gap | Brick or concrete shaft standing alone; factory remnants optional, never required |
| 41. Pristine suburban house in a bog | 12�25 m; primary | Marshy bog; deliberately resolved foundation/water contact | Clean siding, intact roof and windows, perhaps a neat porch; surrounding peat and reeds remain wild; no mandatory decay |
| 42. Freestanding monumental doorway | 4�18 m high; primary | Open glade or ridge; stable base | Ornate stone or metal frame with nothing behind it; optional doors, no portal mechanic implied |
| 43. Staircase to nowhere | 5�30 m; secondary | Gentle slope or clearing | Grounded foot, convincing structure and abrupt end; historical destination need not exist |
| 44. Giant broken crown | 8�25 m; primary | Prairie or hollow; resting contact footprint | Tarnished metal arcs, missing jewels or weathered stone; partly buried versus balanced in grass |
| 45. Colossal statue hand | 5�20 m; primary | Forest floor, rocky slope or marsh edge | Fingers emerge from soil; remainder of statue can be absent; restrained surrounding debris |
| 46. Fallen monumental face | 6�25 m; primary | Meadow or sheltered valley | Stone, ceramic or metal portrait fragment; eye sockets catch rain and vegetation |
| 47. Intact glass conservatory | 15�50 m; primary | Damp forest or taiga clearing; foundation pad | Clear or fogged glass, delicate frame and contrasting interior plants; breakage optional |
| 48. Victorian bandstand | 8�18 m; secondary | Deep forest clearing or open marsh island | Roof, railings and raised floor; intact paint, weathering or engulfing roots |
| 49. Deserted diner | 12�30 m; primary | Prairie, forest margin or cold highland | Stainless panels, windows and counter silhouette; intact versus faded; parking lot not required |
| 50. Solitary railway carriage | 15�30 m; primary | Grove, marsh margin or hillside bench | Bogies supported or sunk coherently; tracks optional; interior separately scoped |
| 51. Clock tower without a town | 8�20 m footprint; primary | Broad glade or ridge | Single readable silhouette, stopped or slowly moving clock; no surrounding town required |
| 52. Empty swimming pool in woodland | 10�30 m; primary | Forest floor; planned basin and safe bypass | Tile, leaf litter, clean water or fern infill; retain believable rim and drainage |
| 53. Lighthouse far inland | 8�25 m footprint; primary | Forested hill, prairie or bog | Tower and gallery; lamp optional; coast and maritime explanation unnecessary |
| 54. Abandoned observatory dome | 12�35 m; primary | Ridge or open plain | Dome, shutter and plinth; telescope implied or visible; no mandatory puzzle |
| 55. Brutalist concrete pavilion | 15�60 m; primary | Forest or marsh; supported slabs | Bold mass and openings, moss/water stains or pristine concrete; enclosed topology separately scoped |
| 56. Torii-like ceremonial gate | 5�15 m; secondary | Forest trail gap, icy hill or reed channel | Strong frame silhouette, grounded posts, red timber or weathered stone |
| 57. Roofless palace ballroom | 25�80 m; primary | Sheltered broad site | Grand stairs, columns and floor pattern; grass under open sky, mirrors only if rendering supports them |
| 58. Half-buried spacecraft hull | 15�70 m; primary | Prairie, taiga or rocky basin | Fitted burial mask, exposed ribs and hull seams; no explosion crater required |
| 59. Silent antenna dish | 8�35 m; primary | Hill shoulder or woodland opening | Grounded pedestal, dish orientation and coherent metal weathering |
| 60. Weathered launch gantry | 15�60 m; primary | Open plateau | Supported truss, missing platforms and rust; rocket or facility optional |
| 61. Giant abandoned diving helmet | 5�15 m; primary | Bog, stream bank or dry grass | Metal rim contact, glass ports, water staining; no ocean required |
| 62. Ceremonial stone chess piece | 5�18 m; secondary | Grove or prairie | One isolated rook, knight or king; no full board required |
| 63. Concrete bus shelter | 3�8 m; secondary | Deep forest or grassland | Shelter and bench; road and timetable optional; maintained or weathered |
| 64. Neat garden fence with no garden | 10�40 m; secondary | Bog, prairie or forest | Small coherent enclosure, gate and grounded posts; wild habitat continues through it |
| 65. Fragment of a suspension bridge | 20�80 m; primary | Valley or forest; terrain-supported anchor masses | Tower and hanging cable lengths; safe debris below; complete crossing not required |
| 66. Monumental library facade | 20�60 m; primary | Forested slope or clearing | Steps, doors and carved exterior; unexplorable facade allowed until interiors are supported |
| 67. Intact tiled courtyard fountain | 5�20 m; secondary | Marsh island or forest hollow | Basin and sculpture, dry or circulating water; surrounding settlement unnecessary |
| 68. Giant cracked porcelain vessel | 5�20 m; primary | Grove, grassland or wetland | Glazed surface, shards and soil contact; sheltered plants or still water inside |
| 69. Old carousel canopy | 10�25 m; primary | Meadow or dense woodland clearing | Circular structure and optional motionless figures; no music or menace required |
| 70. Single elevator door in a stone face | 2�6 m; secondary | Fitted rock face | Grounded threshold and recessed facade; no working lift implied; interior future-only |
| 71. Rusted submarine sail | 6�20 m; primary | Marsh or dry woodland | Partially buried tower, hatches and periscope shapes; rest of vessel may never be shown |
| 72. Marble arcade around ancient trees | 20�60 m; primary | Mature grove | Trees thread through bays; architecture/roots cooperate physically without implying a history |

Anachronism is deliberate. Preserve contrast rather than normalizing every structure into the same mossy ruin. A clean house against dark peat, white marble among black conifers or rusted steel above pale grass can supply the entire discovery. Do not stack several unrelated anomalous landmarks into one cell simply because the library contains them.

Damage variants include roof loss, one surviving corner, flood undercutting, slope displacement, frost splitting, root pressure, partial burial and deliberate material removal. Avoid giving every ruin the same diagonal wall break or identical vine coverage. Dry exposed faces, shaded damp joints and ground-level infill should weather differently.

## Geological and ecological discoveries

These can serve as primary or secondary features depending on scale. Ecological sites should preserve living variety: not every fallen tree gets a perfectly centered mushroom patch, and not every pool needs a picturesque rock on its edge.

| Discovery | Span / role | Habitat and prerequisites | Generation dependencies |
| --- | --- | --- | --- |
| 1. Ridge overlook | 30–150 m; primary | Highland or forest; safe crest approach | Far silhouette, view corridor, reachable resting patch |
| 2. Rock garden hollow | 10–40 m; secondary | Forest/highland; sheltered depression | Embedded rock clusters, moss and paths between masses |
| 3. Jointed stone ridge | 20–100 m; primary | Highland; exposed bedrock | Common fracture direction, coherent fitted outcrops |
| 4. Granite tors | 10–60 m; primary | Rough upland; stable crest | Stacked masses, contact and traversable base |
| 5. Basalt-like column face | 15–80 m; primary | Rocky region; steep exposed face | Aligned column rhythm; irregular breaks avoid wallpaper |
| 6. Talus fan | 20–100 m; primary | Below steep rock | Source face, downhill size sorting, safe bypass |
| 7. Scree tongue | 10–60 m; secondary | Exposed highland slope | Slope-constrained scatter and terrain contact |
| 8. Glacial erratic | 3–15 m; secondary | Prairie, taiga or icy hills | Distinct isolated mass, stable footing, scale contrast |
| 9. Moraine ridge | 40–200 m; primary | Cold region; broad landform | Terrain ridge before rock and habitat placement |
| 10. Frost-heaved stone field | 15–80 m; secondary | Icy hills or taiga; sparse canopy | Stone exposure, soil gaps and frost pattern variation |
| 11. Eroded clay bank | 10–50 m; secondary | Dry grassland; runoff slope | Drainage grooves, exposed soil, sparse rooted edges |
| 12. Badland fingers | 30–150 m; primary | Dry country; soft eroding terrain | Branching drainage and heightfield ridges |
| 13. Shallow ravine | 30–150 m; primary | Forest/highland; connected drainage | Grade, crossings, rock fit and continuous banks |
| 14. Gorge overlook | 40–200 m; primary | Highlands; steep cut | Safe approach; enclosed caves/overhangs are **F** |
| 15. Natural arch | 5–40 m; primary | Rock country | **F**: supported arch geometry, collision and sightlines |
| 16. Cave mouth | 3–20 m; primary | Exposed rock face | **F**: interior topology, water and safe traversal |
| 17. Rock shelter | 5–25 m; secondary | Cliff base | **F**: overhang contact and sheltered lighting |
| 18. Spring seep | 3–15 m; secondary | Moist slope; source opportunity | Wetness source, trickle path and local lush habitat |
| 19. Fast rill staircase | 15–60 m; secondary | Rocky upland; adequate gradient | Connected small falls, stones, splash/wetness zones |
| 20. Falls and plunge pool | 15–60 m; primary | Elevation break; upstream supply | Structural drop, bed carving, downstream continuity |
| 21. Braided shallow reach | 20–100 m; primary | Broad low-gradient valley | Multiple connected channels, islands and sediment |
| 22. Gravel bar | 10–50 m; secondary | Bending stream; local deposition | Flow relation, material sorting and sparse vegetation |
| 23. Oxbow-like pool | 15–70 m; secondary | Marsh or floodplain | Floodplain form, still water and moist edges |
| 24. Reed-ringed pond | 10–50 m; secondary | Wetland; shallow depression | Water depth bands and irregular reed colonization |
| 25. Beaver-like flood pocket | 20–80 m; primary | Forest stream; shallow basin | Dam composition, changed water level; animal presence optional |
| 26. Fallen trunk crossing | 5–25 m; secondary | Narrow channel or hollow | Supported ends, trunk contact, optional safe walking width |
| 27. Windthrow clearing | 20–80 m; primary | Forest; coherent exposure event | Shared fall direction, root plates and recovering understory |
| 28. Ancient tree grove | 20–80 m; primary | Sheltered moist forest | Mature cohort, varied gaps and distinctive silhouettes |
| 29. Root buttress pocket | 3–12 m; secondary | Humid forest; large-tree site | Roots fitted to slope and shaded soil detail |
| 30. Moss-carpet hollow | 10–35 m; secondary | Cool moist shelter | Moisture continuity, soft ground and sparse interruption |
| 31. Fern ravine | 15–80 m; secondary | Shaded moist drainage | Canopy shelter, stream exclusion and fern colonies |
| 32. Flowering prairie patch | 15–80 m; secondary | Open grassland; suitable soil | Patch scale, species mix and coherent wind |
| 33. Wind-shaped tree line | 30–120 m; primary | Exposed taiga/highland margin | Prevailing exposure and shared growth-form direction |
| 34. Dead standing grove | 20–70 m; primary | Wet or disturbed forest | Plausible mortality cause, snags and fallen age cohorts |
| 35. Peat hummock mosaic | 20–100 m; secondary | Bog or marsh; shallow water table | Microrelief, pools, wetness and plant zoning |
| 36. Fungal log colony | 1–8 m; secondary | Damp forest; decaying timber | Host wood, shaded moisture and limited species palette |
| 37. Lichen outcrop | 3–25 m; secondary | Exposed cold/dry rock | Aspect, crevices and restrained surface variation |
| 38. Unreal luminous hollow | 10–50 m; primary | Unreal-flagged sheltered region | Coherent emission, ecology and neighboring light transition |
| 39. Unreal fungal canopy | 20–80 m; primary | Unreal moist region | Shared forms, grounded stems, readable route and atmosphere |
| 40. Dark still grove | 20–100 m; primary | Unreal forest | Controlled canopy/light density; navigable ground remains visible |

## Reusable prop kits

Assemblies and kit pieces are different levels of content. A wall segment is a piece; a roofless chapel is a composition using pieces under construction and damage constraints. Reuse should reduce asset cost without making every discovery visibly identical.

| Kit | Candidate pieces | Rules for reuse |
| --- | --- | --- |
| Stone construction | Footings, corners, wall lengths, caps, thresholds, arches, lintels, stairs | Match block scale, masonry family and supporting spans. |
| Timber structures | Posts, beams, braces, rafters, planks, joints, collapsed sections | Preserve load-bearing logic and grain direction. |
| Brick utilities | Kiln rings, chimney fragments, drain tiles, retaining courses | Keep brick dimensions and heat/weather damage coherent. |
| Paving and earthworks | Slabs, cobbles, edging, compacted ground, embankment profiles | Fit grade; break surfaces around roots and washouts. |
| Water infrastructure | Piers, headwalls, sluice frames, race walls, slipway pieces | Water surface and bed determine placement. |
| Recent infrastructure | Rail fragments, platform edging, rusted supports, boardwalk posts | Use sparingly; avoid a ubiquitous junk-scatter appearance. |
| Ruin debris | Family-specific rubble, broken tiles, displaced blocks, timber fragments | Derive location and orientation from a damage event. |
| Natural rock | Outcrop families, fracture blocks, scree sizes, stream stones | Shared geology, contact, scale sorting and slope rules. |
| Dead wood | Snags, trunks, branch sections, root plates, stumps | Ground support, decay stage and fall history agree. |
| Surface ecology | Moss, lichen, fungi, litter, reed clumps, flowers, root mats | Habitat eligibility and patch structure precede scatter. |
| Anomalous artifacts | Oversized blades, monumental fragments, hull panels, ceremonial objects | Scale and grounding remain convincing; historical explanation is optional. |
| Intact architecture | Clean siding, roof assemblies, windows, porch rails, glazed panels | Preserve pristine variants; do not automatically apply ruin damage or overgrowth. |
| Weathering overlays | Damp bands, sediment, stains, cracks, moss masks | Driven by exposure, water and age; avoid uniform decals. |

## Suggested first content tranche

Prioritize a fitted ridge overlook, spring seep with rill, mossy rock hollow, windthrow clearing and fallen-log colony. They strengthen existing terrain, water and forest systems with relatively few new assets. For the first ruin families, a dry-stone shelter, cottage corner, and broken footbridge offer different scales and clear placement constraints without requiring interiors.

Build and inspect one complete composition per family before widening its variant count. Check photographs, close contact, walking access, distant recognition, several seeds and neighbor transitions. Defer caves, natural arches and explorable buried interiors until topology support exists. Leave room between discoveries: a convincing ordinary stretch of forest is part of the catalog's success.
