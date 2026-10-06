# Procedural Ruins and Discoveries Generation Design

## Overview
This design integrates procedurally generated ruins and natural discoveries directly into the continuous procedural terrain generation pipeline of *The Wood*. Discoveries are **not** static prefabs or placed set pieces; they are algorithmic generative systems driven on-the-fly by seed, terrain gradients, hydrology, and regional biome fields as chunks are generated.

Every structure and geological landmark adapts its shape, foundation, decay, and vegetation interaction directly to the underlying terrain heightfield $Z(x,y)$ and stream curve $\text{streamX}(y)$.

---

## 1. Core Principles

1. **Procedural Synthesis, Not Prefab Stamps**:
   - Rather than dropping a static template or pre-modeled mesh cluster, discovery structures are algorithmically constructed from compositional grammars: contour-following wall traces, slope-adaptive foundation steps, mathematically derived bridge crossings across the dynamic stream function, and gradient-biased rubble collapse vectors.
   - Every realization is unique in footprint dimensions, wall segment counts, collapse severity, breach locations, and ground contact.

2. **Continuous, On-Demand Generation**:
   - Evaluation is fully deterministic and local. Chunks generated in any order (or unloaded and re-visited) produce identical geometry and feature placement without global state mutations or file I/O locks.
   - Coordinates and candidate evaluations use integer math and bounded floating-point functions compatible with standalone headless testing (`Tools/Test-Core.ps1`).

3. **Terrain & Hydrology Coupling**:
   - Features adapt to the terrain: foundations step down along slope normals, abutments anchor to actual opposite stream banks, and overhangs or collapsed stones roll downhill along the steepest descent gradient $-\nabla Z$.

4. **Organic Vegetation Co-existence (Dynamic Reservation)**:
   - Trees and large boulders yield to structural foundations, courtyards, and traversable pathways.
   - Pioneer species (ferns, grasses, moss rocks) dynamically colonize ruins based on moisture, shade, and collapsed rubble borders.

---

## 2. Generative Pipeline & Architecture

### 2.1 Hex Cell Discovery Assignment
Each 950 m hex cell $(q, r)$ deterministically derives its discovery budget from its seed hash:
- **Constructed Discovery Allocation**: Approximately 1 in 3 cells (`hash(seed, q, r, Salt) % 3 == 0`), with starter guarantees at $(0,0)$ and $(1,1)$.
- **Natural Landmark Allocation**: Evaluated per cell according to dominant regional biome weight (e.g., highland crags for Rocky Highlands, spring seeps for wet valleys, windthrow clearings for mature forest).
- **Composition Budget**: At most 1 primary landmark and 0–2 secondary discoveries per cell. Quiet wilderness cells remain untouched.

### 2.2 Procedural Site Adaptation
Candidate discovery sites are evaluated mathematically within the cell bounds:
1. **Sample Local Topography**: Compute center height $Z_0$, local slope magnitude $|\nabla Z|$, and distance to stream $D_{\text{stream}} = |x - \text{streamX}(y)|$.
2. **Grammar Suitability Qualification**:
   - *Stream Crossing*: requires $D_{\text{stream}} \approx \text{streamHalfWidth}(y)$, gentle opposite banks ($|\nabla Z| < 0.35$), and bank height delta $|\Delta Z| < 1.5\,\text{m}$.
   - *Dry-Stone Enclosure*: requires gentle open terrain ($|\nabla Z| < 0.22$) and dry elevation ($D_{\text{stream}} > \text{streamHalfWidth} + 12\,\text{m}$).
   - *Cottage Corner / Foundation*: requires moderate slope bench ($|\nabla Z| < 0.18$) within temperate/taiga forest.
   - *Granite Tor / Ridge Overlook*: requires elevated bedrock shoulder or local prominence ($\text{biome}_{\text{highlands}} > 0.25$ or peak contour).

### 2.3 Generative Assembly Grammars (First Content Tranche)

#### A. Procedural Dry-Stone Enclosure (Shepherd Shelter / Pen)
- **Grammar**:
  - Footprint span $R \in [6.0, 14.0]\,\text{m}$, eccentricity $e \in [0.0, 0.4]$, orientation $\theta_0 \in [0, 2\pi)$.
  - Elliptical or polygonal perimeter wall split into $N$ segments ($N \in [8, 16]$).
  - An entrance gap $\Delta \theta \in [30^\circ, 60^\circ]$ oriented away from the prevailing wind/exposure vector.
  - For each wall segment at $(x_i, y_i)$:
    - Sample exact ground height $Z_i = \text{terrainHeight}(x_i, y_i)$.
    - Place stacked masonry/stone elements with randomized individual scales and slight vertical tilts conforming to local slope.
    - Deterministic decay roll: collapsed wall sections generate a downhill rubble fan ($-\nabla Z_i$) using small rock features.
- **Reservation**: Circular inner clearing ($R_{\text{inner}} = 0.85 R$) suppressing trees; peripheral zone ($R_{\text{outer}} = 1.3 R$) allowing sparse grass and ferns.

#### B. Procedural Cottage Corner / Foundation Shell
- **Grammar**:
  - Rectangular footprint $L_x \in [8.0, 16.0]\,\text{m}, L_y \in [6.0, 12.0]\,\text{m}$ rotated by angle $\theta$.
  - Foundation perimeter decomposed into 4 wall planes with corner pier anchors.
  - Procedural ruin state:
    - 1 or 2 corners remain partially upright (taller stacked column/pier features).
    - Other walls broken down to ground-level foundation footings.
    - Collapsed roof/masonry debris scattered into the interior with density proportional to distance from the surviving walls.
  - Individual wall stones step vertically to match the terrain contour along each wall segment line.
- **Reservation**: Rectangular bounding box with $1.5\,\text{m}$ clearance buffer, completely excluding tree trunks from the interior floor while spawning encroaching ferns in damp shaded pockets.

#### C. Procedural Broken Stream Footbridge
- **Grammar**:
  - Target stream point $(x_c, y_c)$ where $x_c = \text{streamX}(y_c)$.
  - Stream tangent direction $\mathbf{t} = (dx/dy, 1)$ normalized; cross-stream bridge axis $\mathbf{n} \perp \mathbf{t}$.
  - Compute left bank contact $(x_L, y_L)$ and right bank contact $(x_R, y_R)$ at $\pm (\text{streamHalfWidth}(y_c) + 1.2\,\text{m})$.
  - Ground both abutments to $Z_L = \text{terrainHeight}(x_L, y_L)$ and $Z_R = \text{terrainHeight}(x_R, y_R)$.
  - Span realization:
    - Left abutment stone mass extending inward across the water edge.
    - Right abutment stone mass matching or broken.
    - Gap / collapse: mid-span drop where fractured stones sit in the water bed at $Z_{\text{water}} - 0.2\,\text{m}$, creating a natural traversable stepping-stone crossing.
- **Reservation**: Linear corridor along bridge axis ($4.0\,\text{m}$ wide) cleared of trees, keeping the crossing visible and walkable.

#### D. Procedural Highland Granite Tor / Ridge Overlook
- **Grammar**:
  - Anchored at high-slope crag locations.
  - Central core monolith cluster: 3–6 large rock masses intersecting at varying pitches to create a rugged natural summit.
  - Surrounding concentric talus rings: rock scale decays inversely with distance from center ($S(r) = S_{\text{max}} \cdot e^{-r / r_0}$).
  - Rock orientations align with the local ridge strike and jointing angle.
- **Reservation**: Radial clearance of tall canopy, preserving open panoramic sightlines from the overlook crest.

---

## 3. Integration with `World::generate(x, y)`

During chunk generation:
1. **Chunk Bounds Check**:
   - Chunk covers $[x \cdot \text{size}, (x+1) \cdot \text{size}) \times [y \cdot \text{size}, (y+1) \cdot \text{size})$.
   - Determine which nearby hex cells could have discoveries intersecting this chunk (querying the local $3 \times 3$ chunk neighbor kernel).
2. **Collect Active Reservations**:
   - For each discovery in range, obtain its procedural reservation geometry (circle or oriented box).
   - Test if the reservation overlaps the current chunk.
3. **Foliage & Tree Filtering**:
   - When placing trees and ground scatter, test candidates against active reservations:
     - Inside `innerRadius`: reject tree trunks and large boulders completely.
     - In `transitionZone`: reduce tree density to 0, allow pioneer ferns/grasses.
4. **Assembly Clipping & Realization**:
   - For each generated discovery piece:
     - Check if $(x, y) \in [\text{minX}, \text{maxX}) \times [\text{minY}, \text{maxY})$.
     - Sample exact ground height $Z = \text{terrainHeight}(x, y)$.
     - Append to `chunk.features`.
   - Cross-chunk boundaries: because each piece is generated from a deterministic mathematical formula based on the discovery origin and seed, pieces cleanly partition across adjacent chunk boundaries without seams or double-spawning.

---

## 4. Verification and Testing

1. **Deterministic Seam & Order Test (`Tests/DiscoveryTests.cpp`)**:
   - Generate chunk $(X, Y)$ and neighboring chunk $(X+1, Y)$ in order A, then in reverse order B.
   - Assert all feature positions, scales, and yaws match bit-for-bit.
2. **Tree Exclusion Assertion**:
   - Generate 100 chunks containing ruins across 5 different seeds.
   - Assert that zero trees (`Kind::Tree`) have coordinates inside any active discovery's inner clearance radius.
3. **Grounding & Elevation Sanity**:
   - Assert that every placed discovery feature has finite coordinates and $Z == \text{terrainHeight}(x, y)$.
   - Assert no bridge abutment is submerged below the stream bed.
4. **Compilation & Performance**:
   - Build cleanly under Zig C++ (`Tools/Test-Core.ps1`) and MSVC `/std:c++17 /W4 /WX`.
   - Per-chunk generation time remains $< 2\,\text{ms}$ with zero heap allocation churn.
