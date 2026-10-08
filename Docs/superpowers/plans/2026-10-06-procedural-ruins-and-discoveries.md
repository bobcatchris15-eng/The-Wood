# Procedural Ruins and Discoveries Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or pointer-based Clanker orchestration to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Procedurally generate ruins and natural discoveries on-the-fly during terrain generation, adapting their shapes, foundations, decay, and vegetation clearance directly to the terrain heightfield and stream geometry.

**Architecture:** Pure algorithmic generation evaluated on-the-fly per chunk. Hex cells determine candidate discovery types and seeds; procedural grammars trace contour-following walls, stream-perpendicular bridge abutments, foundation steps, and talus cascades. Active reservations dynamically suppress trees and large boulders from interior pads while allowing pioneer undergrowth along borders.

**Tech Stack:** C++17 standalone core (compiled via Zig C++ and MSVC `/std:c++17 /W4 /WX`), Unreal Engine 5.8.3 integration.

**Spec:** [`Docs/superpowers/specs/2026-10-06-ruins-and-discoveries-design.md`](file:///c:/Misc/The-Wood/Docs/superpowers/specs/2026-10-06-ruins-and-discoveries-design.md)

## Global Constraints
- Engine-independent coordinates are in metres (Unreal adapter converts to cm).
- Must compile cleanly with zero warnings under `-Wall -Wextra -Werror` / `/W4 /WX`.
- Zero file I/O or global state mutations in generation loops; 100% deterministic and chunk-order independent.
- Every individual piece must evaluate ground contact at its specific $(x, y)$ coordinate against `terrainHeight(x, y)`.
- Git-tracked repository; all modifications and verifications happen in-place.

---

### Task 1: Discovery Core Data Structures & Reservation System

**Files:**
- Create: `Source/TheWood/Public/Generation/WoodDiscovery.h`
- Create: `Source/TheWood/Private/Generation/WoodDiscovery.cpp`
- Create: `Tests/DiscoveryTests.cpp`
- Create: `Tools/Test-Discovery.cmd`

**Interfaces:**
- Produces:
  ```cpp
  namespace wood {
  enum class DiscoveryType { None, DryStoneShelter, CottageCorner, StreamFootbridge, RidgeTor };
  struct DiscoveryReservation {
      Vec3 center;
      double innerRadius = 0.0;
      double outerRadius = 0.0;
      double yaw = 0.0;
  };
  struct DiscoveryPiece {
      Kind kind;
      Vec3 position;
      double yaw = 0.0;
      double scale = 1.0;
  };
  struct DiscoveryPlan {
      DiscoveryType type = DiscoveryType::None;
      DiscoveryReservation reservation;
      std::vector<DiscoveryPiece> pieces;
  };
  bool isInsideReservation(const std::vector<DiscoveryReservation>& reservations, double x, double y, bool innerOnly);
  }
  ```

- [x] **Step 1: Write the failing test**
Create `Tests/DiscoveryTests.cpp` testing `DiscoveryReservation` point inclusion and reservation bounds.
```cpp
#include "Generation/WoodDiscovery.h"
#include <cassert>
#include <iostream>

int main() {
    using namespace wood;
    DiscoveryReservation res{{100.0, 100.0, 10.0}, 8.0, 12.0, 0.0};
    std::vector<DiscoveryReservation> list{res};
    assert(isInsideReservation(list, 100.0, 100.0, true));
    assert(isInsideReservation(list, 106.0, 100.0, true));
    assert(!isInsideReservation(list, 110.0, 100.0, true));
    assert(isInsideReservation(list, 110.0, 100.0, false));
    assert(!isInsideReservation(list, 115.0, 100.0, false));
    std::cout << "PASS: reservation inclusion tests\n";
    return 0;
}
```

- [x] **Step 2: Run test to verify it fails**
Compile with `Tools/Test-Discovery.cmd`.
Expected: FAIL due to missing `WoodDiscovery.h`.

- [x] **Step 3: Implement minimal headers and reservation math**
Write `Source/TheWood/Public/Generation/WoodDiscovery.h` and `Source/TheWood/Private/Generation/WoodDiscovery.cpp` implementing the structures and `isInsideReservation`.

- [x] **Step 4: Run test to verify it passes**
Compile and run `Tools/Test-Discovery.cmd`.
Expected: PASS.

---

### Task 2: Procedural Generation Grammars (First Tranche)

**Files:**
- Modify: `Source/TheWood/Public/Generation/WoodDiscovery.h`
- Modify: `Source/TheWood/Private/Generation/WoodDiscovery.cpp`
- Modify: `Tests/DiscoveryTests.cpp`

**Interfaces:**
- Produces:
  ```cpp
  namespace wood {
  DiscoveryPlan planDiscovery(
      std::uint32_t seed,
      int cellQ, int cellR,
      const Vec3& cellCenter,
      const Surface& cellClimate,
      const std::function<double(double, double)>& heightFn,
      const std::function<double(double)>& streamXFn,
      const std::function<double(double)>& streamHWFn
  );
  }
  ```

- [x] **Step 1: Write tests for procedural generation grammars**
In `Tests/DiscoveryTests.cpp`:
```cpp
// Assert deterministic planning for guaranteed cells
// (0, 0) -> CottageCorner or DryStoneShelter
// (1, 1) -> RidgeTor in highlands
auto plan0 = planDiscovery(12345, 0, 0, center0, climate0, heightFn, streamXFn, streamHWFn);
assert(plan0.type != DiscoveryType::None);
assert(!plan0.pieces.empty());
for(const auto& p : plan0.pieces) {
    assert(std::abs(p.position.z - heightFn(p.position.x, p.position.y)) < 0.001);
}
```

- [x] **Step 2: Run test to verify it fails**
Expected: Compilation failure (planDiscovery not declared).

- [x] **Step 3: Implement the 4 procedural generative grammars**
In `WoodDiscovery.cpp`:
1. `generateDryStoneShelter`: elliptical contour-tracing, entrance opening on leeward side, wall stones placed at exact terrain height, downhill rubble fall vectors.
2. `generateCottageCorner`: stepped rectangular foundation, intact corner pier, collapsed roof/rubble fan inside, mossy ferns around wet edges.
3. `generateStreamFootbridge`: stream tangent vector calculation, bank placement at $\pm (\text{streamHW} + 1.2\,\text{m})$, matching abutments and bed stepping stones.
4. `generateRidgeTor`: summit monolith cluster with distance-decaying talus rock rings.

- [x] **Step 4: Run test to verify it passes**
Run `Tools/Test-Discovery.cmd`.
Expected: PASS with 100% ground height adherence on every piece.

---

### Task 3: Integration into `World::generate` & Dynamic Reservation Filtering

**Files:**
- Modify: `Source/TheWood/Public/Generation/WoodGeneration.h`
- Modify: `Source/TheWood/Private/Generation/WoodGeneration.cpp`
- Modify: `Tests/GenerationTests.cpp`

**Interfaces:**
- Consumes: `planDiscovery`, `isInsideReservation` from `WoodDiscovery.h`
- Produces: `World::generate(int x, int y)` outputs features with zero tree collisions inside reservations and seamless cross-chunk discovery pieces.

- [x] **Step 1: Write test for tree exclusion and cross-chunk seams**
In `Tests/GenerationTests.cpp`:
```cpp
// Test that no trees spawn within any discovery inner clearance
World world({12345, 128.0, 64});
for (int cy = -2; cy <= 2; ++cy) {
    for (int cx = -2; cx <= 2; ++cx) {
        Chunk chunk = world.generate(cx, cy, true);
        // Verify no Tree is within any reservation inner radius
    }
}
```

- [x] **Step 2: Run test to verify failure**
Expected: Fails or prototype altar still has hardcoded features.

- [x] **Step 3: Integrate discovery queries into `World::generate`**
In `WoodGeneration.cpp`:
1. Remove old hardcoded lines 242–289.
2. At the start of `World::generate(x, y)`, query discovery plans for nearby candidate cells whose outer radius intersects chunk `[minX - 50, maxX + 50] x [minY - 50, maxY + 50]`.
3. In the tree/undergrowth placement lattice loops:
   - Check `isInsideReservation(activeReservations, px, py, true)`.
   - If inside inner reservation, reject `Kind::Tree` and large `Kind::Rock`.
   - Allow ferns/grass around outer transition bounds.
4. For each active discovery plan, clip its generated pieces to `[minX, maxX) x [minY, maxY)` and append to `chunk.features` with exact `terrainHeight`.

- [x] **Step 4: Run test to verify it passes**
Run `Tools/Test-Core.ps1` and `Tools/Test-Discovery.cmd`.
Expected: PASS.

---

### Task 4: Full Test Suite & Claude Review Regression Verification

**Files:**
- Modify: `Tools/Test-Core.ps1` to include `WoodDiscovery.cpp`
- Run: `Tools/Test-Core.ps1`, `Tools/Test-Biomes.cmd`, `Tools/Test-Discovery.cmd`

- [x] **Step 1: Update Test-Core.ps1**
Add `Source/TheWood/Private/Generation/WoodDiscovery.cpp` to the compile command.

- [x] **Step 2: Run all standalone test suites**
Run:
- `powershell -ExecutionPolicy Bypass -File Tools/Test-Core.ps1`
- `cmd /c Tools\Test-Biomes.cmd`
- `cmd /c Tools\Test-Discovery.cmd`
- `cmd /c Tools\Test-Hex.cmd`
Expected: All suites PASS with 0 warnings.

- [x] **Step 3: Document Status & Artifact Updates**
Update `Docs/Status.md` and `.clanker/CURRENT_WORK.md` with verification results.
