#include <iostream>
#include <vector>
#include <cmath>
#include <string>
#include <functional>
#include <algorithm>
#include <cstdint>

#if __has_include("Generation/WoodDiscovery.h")
#include "Generation/WoodDiscovery.h"
#elif __has_include("WoodDiscovery.h")
#include "WoodDiscovery.h"
#endif

static int gTestCount = 0;
static int gFailures = 0;

template <typename T>
static void check_true(T&& cond, const char* expr, const char* file, int line) {
    ++gTestCount;
    if (!static_cast<bool>(cond)) {
        std::cerr << "CHECK FAILED (expected true): " << expr << " at " << file << ":" << line << "\n";
        ++gFailures;
    }
}

template <typename T>
static void check_false(T&& cond, const char* expr, const char* file, int line) {
    ++gTestCount;
    if (static_cast<bool>(cond)) {
        std::cerr << "CHECK FAILED (expected false): " << expr << " at " << file << ":" << line << "\n";
        ++gFailures;
    }
}

template <typename T, typename U>
static void check_eq(T&& a, U&& b, const char* exprA, const char* exprB, const char* file, int line) {
    ++gTestCount;
    if (a != b) {
        std::cerr << "CHECK FAILED: " << exprA << " == " << exprB << " at " << file << ":" << line << "\n";
        ++gFailures;
    }
}

#define EXPECT_TRUE(expr) check_true((expr), #expr, __FILE__, __LINE__)
#define EXPECT_FALSE(expr) check_false((expr), #expr, __FILE__, __LINE__)
#define EXPECT_EQ(a, b) check_eq((a), (b), #a, #b, __FILE__, __LINE__)

// Structural pieces bed 0.10-0.25 m into terrain; no piece may float above it.
template <typename H>
static void check_grounded(const wood::DiscoveryPiece& p, H&& heightFn, const char* file, int line) {
    const double h = heightFn(p.position.x, p.position.y);
    check_true(p.position.z <= h + 1e-9, "piece does not float above terrain", file, line);
    check_true(p.position.z >= h - 0.25 - 1e-9, "piece sinks at most 0.25 m", file, line);
}
#define EXPECT_GROUNDED(piece, hfn) check_grounded((piece), (hfn), __FILE__, __LINE__)

static void test_types_and_structs() {
    std::cout << "[TEST] test_types_and_structs...\n";

    wood::DiscoveryType tNone = wood::DiscoveryType::None;
    wood::DiscoveryType tShelter = wood::DiscoveryType::DryStoneShelter;
    wood::DiscoveryType tCottage = wood::DiscoveryType::CottageCorner;
    wood::DiscoveryType tBridge = wood::DiscoveryType::StreamFootbridge;
    wood::DiscoveryType tTor = wood::DiscoveryType::RidgeTor;

    EXPECT_TRUE(tNone != tShelter);
    EXPECT_TRUE(tShelter != tCottage);
    EXPECT_TRUE(tCottage != tBridge);
    EXPECT_TRUE(tBridge != tTor);

    wood::DiscoveryReservation res(wood::DiscoveryType::DryStoneShelter, 10.0, 20.0, 5.0, 15.0);
    EXPECT_EQ(res.type, wood::DiscoveryType::DryStoneShelter);
    EXPECT_EQ(res.center.x, 10.0);
    EXPECT_EQ(res.center.y, 20.0);
    EXPECT_EQ(res.innerRadius, 5.0);
    EXPECT_EQ(res.outerRadius, 15.0);
    EXPECT_EQ(res.x(), 10.0);
    EXPECT_EQ(res.y(), 20.0);

    wood::DiscoveryPiece piece("wall_a", "SM_StoneWall", {10.0, 20.0, 1.0}, 45.0, 1.0);
    EXPECT_EQ(piece.name, std::string("wall_a"));
    EXPECT_EQ(piece.mesh, std::string("SM_StoneWall"));
    EXPECT_EQ(piece.position.x, 10.0);
    EXPECT_EQ(piece.position.y, 20.0);
    EXPECT_EQ(piece.position.z, 1.0);
    EXPECT_EQ(piece.yaw, 45.0);
    EXPECT_EQ(piece.scale, 1.0);

    wood::DiscoveryPlan plan(wood::DiscoveryType::RidgeTor, {50.0, 60.0, 25.0}, 90.0);
    EXPECT_EQ(plan.type, wood::DiscoveryType::RidgeTor);
    EXPECT_EQ(plan.position.x, 50.0);
    EXPECT_EQ(plan.position.y, 60.0);
    EXPECT_EQ(plan.position.z, 25.0);
    EXPECT_EQ(plan.yaw, 90.0);
    EXPECT_TRUE(plan.valid);
    plan.pieces.push_back(piece);
    EXPECT_EQ(plan.pieces.size(), static_cast<std::size_t>(1));
}

static void test_empty_reservations() {
    std::cout << "[TEST] test_empty_reservations...\n";
    std::vector<wood::DiscoveryReservation> reservations;

    EXPECT_FALSE(wood::isInsideReservation(reservations, 0.0, 0.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 0.0, 0.0, true));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 100.0, -50.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 100.0, -50.0, true));
}

static void test_reservation_inclusion() {
    std::cout << "[TEST] test_reservation_inclusion...\n";
    std::vector<wood::DiscoveryReservation> reservations;
    reservations.emplace_back(wood::DiscoveryType::CottageCorner, 100.0, 200.0, 8.0, 20.0);

    // Exact center
    EXPECT_TRUE(wood::isInsideReservation(reservations, 100.0, 200.0, false));
    EXPECT_TRUE(wood::isInsideReservation(reservations, 100.0, 200.0, true));

    // Strictly inside inner radius
    EXPECT_TRUE(wood::isInsideReservation(reservations, 104.0, 200.0, false));
    EXPECT_TRUE(wood::isInsideReservation(reservations, 104.0, 200.0, true));
    EXPECT_TRUE(wood::isInsideReservation(reservations, 100.0, 205.0, false));
    EXPECT_TRUE(wood::isInsideReservation(reservations, 100.0, 205.0, true));

    // Diagonal strictly inside inner radius (dx=4, dy=4, dist^2=32 < 64)
    EXPECT_TRUE(wood::isInsideReservation(reservations, 104.0, 204.0, false));
    EXPECT_TRUE(wood::isInsideReservation(reservations, 104.0, 204.0, true));

    // Inside outer radius, but outside inner radius (dx=12, dy=0, inner=8, outer=20)
    EXPECT_TRUE(wood::isInsideReservation(reservations, 112.0, 200.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 112.0, 200.0, true));

    // Diagonal inside outer radius, outside inner radius (dx=10, dy=10, dist^2=200 < 400)
    EXPECT_TRUE(wood::isInsideReservation(reservations, 110.0, 210.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 110.0, 210.0, true));
}

static void test_boundary_points() {
    std::cout << "[TEST] test_boundary_points...\n";
    const double cx = -50.0;
    const double cy = 75.0;
    const double rInner = 10.0;
    const double rOuter = 25.0;

    std::vector<wood::DiscoveryReservation> reservations;
    reservations.emplace_back(wood::DiscoveryType::StreamFootbridge, cx, cy, rInner, rOuter);

    // Inner boundary cardinal points (+x, -x, +y, -y)
    EXPECT_TRUE(wood::isInsideReservation(reservations, cx + rInner, cy, true));
    EXPECT_TRUE(wood::isInsideReservation(reservations, cx + rInner, cy, false));

    EXPECT_TRUE(wood::isInsideReservation(reservations, cx - rInner, cy, true));
    EXPECT_TRUE(wood::isInsideReservation(reservations, cx - rInner, cy, false));

    EXPECT_TRUE(wood::isInsideReservation(reservations, cx, cy + rInner, true));
    EXPECT_TRUE(wood::isInsideReservation(reservations, cx, cy + rInner, false));

    EXPECT_TRUE(wood::isInsideReservation(reservations, cx, cy - rInner, true));
    EXPECT_TRUE(wood::isInsideReservation(reservations, cx, cy - rInner, false));

    // Outer boundary cardinal points (+x, -x, +y, -y)
    // Points on outer boundary are inside outer reservation (innerOnly=false), but NOT inner reservation
    EXPECT_TRUE(wood::isInsideReservation(reservations, cx + rOuter, cy, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, cx + rOuter, cy, true));

    EXPECT_TRUE(wood::isInsideReservation(reservations, cx - rOuter, cy, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, cx - rOuter, cy, true));

    EXPECT_TRUE(wood::isInsideReservation(reservations, cx, cy + rOuter, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, cx, cy + rOuter, true));

    EXPECT_TRUE(wood::isInsideReservation(reservations, cx, cy - rOuter, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, cx, cy - rOuter, true));
}

static void test_exclusion() {
    std::cout << "[TEST] test_exclusion...\n";
    const double cx = 0.0;
    const double cy = 0.0;
    const double rInner = 6.0;
    const double rOuter = 14.0;

    std::vector<wood::DiscoveryReservation> reservations;
    reservations.emplace_back(wood::DiscoveryType::DryStoneShelter, cx, cy, rInner, rOuter);

    // Just beyond inner radius (exclusion for innerOnly=true)
    EXPECT_FALSE(wood::isInsideReservation(reservations, cx + 6.01, cy, true));
    EXPECT_TRUE(wood::isInsideReservation(reservations, cx + 6.01, cy, false));

    // Just beyond outer radius (exclusion for both)
    EXPECT_FALSE(wood::isInsideReservation(reservations, cx + 14.01, cy, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, cx + 14.01, cy, true));

    EXPECT_FALSE(wood::isInsideReservation(reservations, cx - 14.01, cy, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, cx - 14.01, cy, true));

    EXPECT_FALSE(wood::isInsideReservation(reservations, cx, cy + 14.01, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, cx, cy + 14.01, true));

    EXPECT_FALSE(wood::isInsideReservation(reservations, cx, cy - 14.01, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, cx, cy - 14.01, true));

    // Far away points
    EXPECT_FALSE(wood::isInsideReservation(reservations, 1000.0, 2000.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 1000.0, 2000.0, true));
    EXPECT_FALSE(wood::isInsideReservation(reservations, -500.0, -500.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, -500.0, -500.0, true));
}

static void test_multiple_reservations() {
    std::cout << "[TEST] test_multiple_reservations...\n";
    std::vector<wood::DiscoveryReservation> reservations;
    // Res 1 at (0, 0), inner 5, outer 12
    reservations.emplace_back(wood::DiscoveryType::DryStoneShelter, 0.0, 0.0, 5.0, 12.0);
    // Res 2 at (100, 100), inner 8, outer 20
    reservations.emplace_back(wood::DiscoveryType::RidgeTor, 100.0, 100.0, 8.0, 20.0);

    // Point in Res 1 inner
    EXPECT_TRUE(wood::isInsideReservation(reservations, 2.0, 2.0, true));
    EXPECT_TRUE(wood::isInsideReservation(reservations, 2.0, 2.0, false));

    // Point in Res 2 inner
    EXPECT_TRUE(wood::isInsideReservation(reservations, 102.0, 102.0, true));
    EXPECT_TRUE(wood::isInsideReservation(reservations, 102.0, 102.0, false));

    // Point in Res 1 outer only
    EXPECT_TRUE(wood::isInsideReservation(reservations, 8.0, 0.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 8.0, 0.0, true));

    // Point in Res 2 outer only
    EXPECT_TRUE(wood::isInsideReservation(reservations, 115.0, 100.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 115.0, 100.0, true));

    // Midpoint between both (50, 50): excluded from both
    EXPECT_FALSE(wood::isInsideReservation(reservations, 50.0, 50.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 50.0, 50.0, true));
}

static void test_zero_and_negative_radius() {
    std::cout << "[TEST] test_zero_and_negative_radius...\n";
    std::vector<wood::DiscoveryReservation> reservations;
    reservations.emplace_back(wood::DiscoveryType::None, 10.0, 10.0, 0.0, 0.0);
    reservations.emplace_back(wood::DiscoveryType::None, 50.0, 50.0, -5.0, -10.0);

    // Even exact center shouldn't be included for 0 or negative radius
    EXPECT_FALSE(wood::isInsideReservation(reservations, 10.0, 10.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 10.0, 10.0, true));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 50.0, 50.0, false));
    EXPECT_FALSE(wood::isInsideReservation(reservations, 50.0, 50.0, true));
}

static void test_dry_stone_shelter_plan() {
    std::cout << "[TEST] test_dry_stone_shelter_plan...\n";
    auto heightFn = [](double x, double y) -> double {
        return 12.0 + 3.0 * std::sin(x * 0.08) + 2.0 * std::cos(y * 0.06);
    };
    auto streamXFn = [](double y) -> double { return 1000.0 + y * 0.1; };
    auto streamHWFn = [](double) -> double { return 4.0; };

    wood::Surface climate;
    climate.forest = 0.1;
    climate.biome[1] = 0.9; // DryGrassland

    wood::Vec3 center{0.0, 0.0, 12.0};
    wood::DiscoveryPlan plan = wood::planDiscovery(42, 0, 0, center, climate, heightFn, streamXFn, streamHWFn, true);

    EXPECT_TRUE(plan.valid);
    EXPECT_TRUE(plan.type == wood::DiscoveryType::DryStoneShelter);
    EXPECT_FALSE(plan.pieces.empty());
    EXPECT_TRUE(plan.reservation.type == wood::DiscoveryType::DryStoneShelter);
    EXPECT_TRUE(plan.reservation.innerRadius > 0.0);
    EXPECT_TRUE(plan.reservation.outerRadius >= plan.reservation.innerRadius);

    bool hasWall = false;
    bool hasRubble = false;
    for (const auto& p : plan.pieces) {
        EXPECT_GROUNDED(p, heightFn);
        EXPECT_TRUE(wood::isInsideReservation(plan.reservation, p.position.x, p.position.y, false));
        if (p.name.find("wall") != std::string::npos) hasWall = true;
        if (p.name.find("rubble") != std::string::npos) hasRubble = true;
    }
    EXPECT_TRUE(hasWall);
    EXPECT_TRUE(hasRubble);
}

static void test_cottage_corner_plan() {
    std::cout << "[TEST] test_cottage_corner_plan...\n";
    auto heightFn = [](double x, double y) -> double {
        return 8.0 + 1.5 * std::cos(x * 0.05) + 2.2 * std::sin(y * 0.07);
    };
    auto streamXFn = [](double y) -> double { return 500.0 + y * 0.05; };
    auto streamHWFn = [](double) -> double { return 3.5; };

    wood::Surface climate;
    climate.forest = 0.85;
    climate.biome[0] = 0.85; // TemperateForest

    wood::Vec3 center{0.0, 0.0, 8.0};
    wood::DiscoveryPlan plan = wood::planDiscovery(12345, 0, 0, center, climate, heightFn, streamXFn, streamHWFn, true);

    EXPECT_TRUE(plan.valid);
    EXPECT_TRUE(plan.type == wood::DiscoveryType::CottageCorner);
    EXPECT_FALSE(plan.pieces.empty());
    EXPECT_TRUE(plan.reservation.type == wood::DiscoveryType::CottageCorner);
    EXPECT_TRUE(plan.reservation.innerRadius > 0.0);
    EXPECT_TRUE(plan.reservation.outerRadius >= plan.reservation.innerRadius);

    bool hasPier = false;
    bool hasFoundation = false;
    bool hasFernOrRubble = false;
    for (const auto& p : plan.pieces) {
        EXPECT_GROUNDED(p, heightFn);
        EXPECT_TRUE(wood::isInsideReservation(plan.reservation, p.position.x, p.position.y, false));
        if (p.name.find("pier") != std::string::npos) hasPier = true;
        if (p.name.find("foundation") != std::string::npos) hasFoundation = true;
        if (p.name.find("rubble") != std::string::npos || p.name.find("fern") != std::string::npos) hasFernOrRubble = true;
    }
    EXPECT_TRUE(hasPier);
    EXPECT_TRUE(hasFoundation);
    EXPECT_TRUE(hasFernOrRubble);
}

static void test_ridge_tor_plan() {
    std::cout << "[TEST] test_ridge_tor_plan...\n";
    auto heightFn = [](double x, double y) -> double {
        return 45.0 + 5.0 * std::sin(x * 0.04) + 4.0 * std::cos(y * 0.04);
    };
    auto streamXFn = [](double y) -> double { return 2000.0 + y * 0.1; };
    auto streamHWFn = [](double) -> double { return 3.0; };

    wood::Surface climate;
    climate.biome[2] = 0.8; // RockyHighlands
    climate.slope = 0.35;

    wood::Vec3 center{950.0, 950.0, 45.0};
    wood::DiscoveryPlan plan = wood::planDiscovery(999, 1, 1, center, climate, heightFn, streamXFn, streamHWFn, true);

    EXPECT_TRUE(plan.valid);
    EXPECT_TRUE(plan.type == wood::DiscoveryType::RidgeTor);
    EXPECT_FALSE(plan.pieces.empty());
    EXPECT_TRUE(plan.reservation.type == wood::DiscoveryType::RidgeTor);
    EXPECT_TRUE(plan.reservation.innerRadius > 0.0);
    EXPECT_TRUE(plan.reservation.outerRadius >= plan.reservation.innerRadius);

    bool hasMonolith = false;
    bool hasTalus = false;
    for (const auto& p : plan.pieces) {
        EXPECT_GROUNDED(p, heightFn);
        EXPECT_TRUE(wood::isInsideReservation(plan.reservation, p.position.x, p.position.y, false));
        if (p.name.find("monolith") != std::string::npos) hasMonolith = true;
        if (p.name.find("talus") != std::string::npos) hasTalus = true;
    }
    EXPECT_TRUE(hasMonolith);
    EXPECT_TRUE(hasTalus);
}

static void test_stream_footbridge_plan() {
    std::cout << "[TEST] test_stream_footbridge_plan...\n";
    auto heightFn = [](double x, double y) -> double {
        return 5.0 + 1.2 * std::sin(x * 0.1) + 1.0 * std::cos(y * 0.1);
    };
    auto streamXFn = [](double y) -> double { return 50.0 + 2.0 * std::sin(y * 0.02); };
    auto streamHWFn = [](double) -> double { return 4.0; };

    const std::uint32_t seed = 777;
    // Cell (2,0) is a ruins region by construction; placement is gated by the explicit ruins argument.
    int streamQ = 2;
    int streamR = 0;

    const double centerY = 200.0;
    const double centerX = streamXFn(centerY);
    wood::Vec3 center{centerX, centerY, heightFn(centerX, centerY)};
    wood::Surface climate;

    wood::DiscoveryPlan plan = wood::planDiscovery(seed, streamQ, streamR, center, climate, heightFn, streamXFn, streamHWFn, true);

    EXPECT_TRUE(plan.valid);
    EXPECT_TRUE(plan.type == wood::DiscoveryType::StreamFootbridge);
    EXPECT_FALSE(plan.pieces.empty());
    EXPECT_TRUE(plan.reservation.type == wood::DiscoveryType::StreamFootbridge);
    EXPECT_TRUE(plan.reservation.innerRadius > 0.0);
    EXPECT_TRUE(plan.reservation.outerRadius >= plan.reservation.innerRadius);

    bool hasAbutment = false;
    bool hasSteppingStone = false;
    for (const auto& p : plan.pieces) {
        EXPECT_GROUNDED(p, heightFn);
        EXPECT_TRUE(wood::isInsideReservation(plan.reservation, p.position.x, p.position.y, false));
        if (p.name.find("abutment") != std::string::npos) hasAbutment = true;
        if (p.name.find("stepping_stone") != std::string::npos) hasSteppingStone = true;
    }
    EXPECT_TRUE(hasAbutment);
    EXPECT_TRUE(hasSteppingStone);
}

static void test_guaranteed_sites() {
    std::cout << "[TEST] test_guaranteed_sites...\n";
    auto heightFn = [](double, double) -> double { return 10.0; };
    auto streamXFn = [](double) -> double { return 5000.0; };
    auto streamHWFn = [](double) -> double { return 5.0; };

    // (0, 0) guaranteed CottageCorner or DryStoneShelter
    wood::Surface forestClimate;
    forestClimate.forest = 0.9;
    wood::DiscoveryPlan plan00Forest = wood::planDiscovery(100, 0, 0, {0,0,10}, forestClimate, heightFn, streamXFn, streamHWFn, true);
    EXPECT_TRUE(plan00Forest.valid);
    EXPECT_TRUE(plan00Forest.type == wood::DiscoveryType::CottageCorner);

    wood::Surface dryClimate;
    dryClimate.forest = 0.05;
    wood::DiscoveryPlan plan00Dry = wood::planDiscovery(100, 0, 0, {0,0,10}, dryClimate, heightFn, streamXFn, streamHWFn, true);
    EXPECT_TRUE(plan00Dry.valid);
    EXPECT_TRUE(plan00Dry.type == wood::DiscoveryType::DryStoneShelter);

    // (1, 1) in highlands guaranteed RidgeTor
    wood::Surface highlandClimate;
    highlandClimate.biome[2] = 0.6;
    wood::DiscoveryPlan plan11High = wood::planDiscovery(100, 1, 1, {100,100,20}, highlandClimate, heightFn, streamXFn, streamHWFn, true);
    EXPECT_TRUE(plan11High.valid);
    EXPECT_TRUE(plan11High.type == wood::DiscoveryType::RidgeTor);
}

static void test_wilderness_cell_untouched() {
    std::cout << "[TEST] test_wilderness_cell_untouched...\n";
    auto heightFn = [](double, double) -> double { return 10.0; };
    auto streamXFn = [](double) -> double { return 5000.0; };
    auto streamHWFn = [](double) -> double { return 5.0; };

    const std::uint32_t seed = 42;
    const int unallocQ = 2;
    const int unallocR = 1;

    wood::Surface climate;
    climate.forest = 0.2;
    wood::DiscoveryPlan plan = wood::planDiscovery(seed, unallocQ, unallocR, {500,500,10}, climate, heightFn, streamXFn, streamHWFn, false);
    EXPECT_FALSE(plan.valid);
    EXPECT_TRUE(plan.type == wood::DiscoveryType::None);
    EXPECT_TRUE(plan.pieces.empty());
}

static void test_all_four_types_heightfn_and_reservations() {
    std::cout << "[TEST] test_all_four_types_heightfn_and_reservations...\n";
    auto complexHeightFn = [](double x, double y) -> double {
        return 33.7 + 4.8 * std::sin(x * 0.033 + 0.5) - 3.2 * std::cos(y * 0.041 - 0.2) + 0.02 * (x + y);
    };
    auto streamXFn = [](double y) -> double { return 120.0 + 3.5 * std::cos(y * 0.015); };
    auto streamHWFn = [](double) -> double { return 5.2; };

    const std::uint32_t seeds[] = { 1U, 42U, 999U, 12345U, 777777U };

    for (std::uint32_t seed : seeds) {
        // 1. DryStoneShelter
        wood::Surface dryClimate;
        dryClimate.forest = 0.0;
        dryClimate.biome[1] = 1.0;
        wood::DiscoveryPlan planShelter = wood::planDiscovery(seed, 0, 0, {0, 0, 0}, dryClimate, complexHeightFn, streamXFn, streamHWFn, true);
        EXPECT_TRUE(planShelter.valid);
        EXPECT_TRUE(planShelter.type == wood::DiscoveryType::DryStoneShelter);
        EXPECT_FALSE(planShelter.pieces.empty());
        for (const auto& piece : planShelter.pieces) {
            EXPECT_GROUNDED(piece, complexHeightFn);
            EXPECT_TRUE(wood::isInsideReservation(planShelter.reservation, piece.position.x, piece.position.y, false));
        }

        // 2. CottageCorner
        wood::Surface forestClimate;
        forestClimate.forest = 0.8;
        forestClimate.biome[0] = 0.8;
        wood::DiscoveryPlan planCottage = wood::planDiscovery(seed, 0, 0, {0, 0, 0}, forestClimate, complexHeightFn, streamXFn, streamHWFn, true);
        EXPECT_TRUE(planCottage.valid);
        EXPECT_TRUE(planCottage.type == wood::DiscoveryType::CottageCorner);
        EXPECT_FALSE(planCottage.pieces.empty());
        for (const auto& piece : planCottage.pieces) {
            EXPECT_GROUNDED(piece, complexHeightFn);
            EXPECT_TRUE(wood::isInsideReservation(planCottage.reservation, piece.position.x, piece.position.y, false));
        }

        // 3. RidgeTor
        wood::Surface highlandClimate;
        highlandClimate.biome[2] = 0.7;
        highlandClimate.slope = 0.4;
        wood::DiscoveryPlan planTor = wood::planDiscovery(seed, 1, 1, {950, 950, 0}, highlandClimate, complexHeightFn, streamXFn, streamHWFn, true);
        EXPECT_TRUE(planTor.valid);
        EXPECT_TRUE(planTor.type == wood::DiscoveryType::RidgeTor);
        EXPECT_FALSE(planTor.pieces.empty());
        for (const auto& piece : planTor.pieces) {
            EXPECT_GROUNDED(piece, complexHeightFn);
            EXPECT_TRUE(wood::isInsideReservation(planTor.reservation, piece.position.x, piece.position.y, false));
        }

        // 4. StreamFootbridge
        const int streamQ = 2;
        const int streamR = 0;
        const double sy = 150.0;
        const double sx = streamXFn(sy);
        wood::Surface neutralClimate;
        wood::DiscoveryPlan planBridge = wood::planDiscovery(seed, streamQ, streamR, {sx, sy, 0}, neutralClimate, complexHeightFn, streamXFn, streamHWFn, true);
        EXPECT_TRUE(planBridge.valid);
        EXPECT_TRUE(planBridge.type == wood::DiscoveryType::StreamFootbridge);
        EXPECT_FALSE(planBridge.pieces.empty());
        for (const auto& piece : planBridge.pieces) {
            EXPECT_GROUNDED(piece, complexHeightFn);
            EXPECT_TRUE(wood::isInsideReservation(planBridge.reservation, piece.position.x, piece.position.y, false));
        }
    }
}

static void test_shelter_walls_contiguous() {
    std::cout << "[TEST] test_shelter_walls_contiguous...\n";
    auto heightFn = [](double x, double y) -> double {
        return 12.0 + 3.0 * std::sin(x * 0.08) + 2.0 * std::cos(y * 0.06);
    };
    auto streamXFn = [](double y) -> double { return 1000.0 + y * 0.1; };
    auto streamHWFn = [](double) -> double { return 4.0; };

    wood::Surface climate;
    climate.forest = 0.1;
    climate.biome[1] = 0.9;
    const wood::Vec3 center{0.0, 0.0, 12.0};

    for (std::uint32_t seed = 1; seed <= 40; ++seed) {
        const auto plan = wood::planDiscovery(seed, 0, 0, center, climate, heightFn, streamXFn, streamHWFn, true);
        EXPECT_TRUE(plan.valid);

        std::vector<const wood::DiscoveryPiece*> walls;
        for (const auto& p : plan.pieces) {
            EXPECT_GROUNDED(p, heightFn);
            if (p.mesh == "SM_DryStone_Wall") walls.push_back(&p);
        }
        EXPECT_TRUE(walls.size() >= 4);
        if (walls.size() < 2) continue;

        // Consecutive walls, plus the closing pair, butt end-to-end: centre spacing = mean segment length
        // (2.0 m x scale each). Any other spacing must be a deliberate gap (doorway or collapse breach).
        int gapPairs = 0;
        for (std::size_t i = 0; i < walls.size(); ++i) {
            const wood::DiscoveryPiece& a = *walls[i];
            const wood::DiscoveryPiece& b = *walls[(i + 1) % walls.size()];
            const double expected = a.scale + b.scale;
            const double d = std::hypot(b.position.x - a.position.x, b.position.y - a.position.y);
            const bool butt = std::abs(d - expected) <= 0.05 * expected;
            if (!butt) {
                ++gapPairs;
                const double gap = d - expected;
                EXPECT_TRUE(gap >= 0.9 && gap <= 2.8);
            }
        }
        EXPECT_EQ(gapPairs, 2);
    }
}

static void test_discovery_deterministic() {
    std::cout << "[TEST] test_discovery_deterministic...\n";
    auto heightFn = [](double x, double y) -> double {
        return 33.7 + 4.8 * std::sin(x * 0.033 + 0.5) - 3.2 * std::cos(y * 0.041 - 0.2) + 0.02 * (x + y);
    };
    auto streamXFn = [](double y) -> double { return 120.0 + 3.5 * std::cos(y * 0.015); };
    auto streamHWFn = [](double) -> double { return 5.2; };

    wood::Surface dryClimate;
    dryClimate.biome[1] = 1.0;
    wood::Surface forestClimate;
    forestClimate.forest = 0.8;
    forestClimate.biome[0] = 0.8;
    const wood::Surface* climates[2] = { &dryClimate, &forestClimate };

    for (std::uint32_t seed : { 42U, 12345U }) {
        for (const wood::Surface* climate : climates) {
            const auto a = wood::planDiscovery(seed, 0, 0, {0, 0, 0}, *climate, heightFn, streamXFn, streamHWFn, true);
            const auto b = wood::planDiscovery(seed, 0, 0, {0, 0, 0}, *climate, heightFn, streamXFn, streamHWFn, true);
            EXPECT_EQ(a.pieces.size(), b.pieces.size());
            if (a.pieces.size() != b.pieces.size()) continue;
            for (std::size_t i = 0; i < a.pieces.size(); ++i) {
                EXPECT_TRUE(a.pieces[i].position.x == b.pieces[i].position.x);
                EXPECT_TRUE(a.pieces[i].position.y == b.pieces[i].position.y);
                EXPECT_TRUE(a.pieces[i].position.z == b.pieces[i].position.z);
                EXPECT_TRUE(a.pieces[i].yaw == b.pieces[i].yaw);
                EXPECT_TRUE(a.pieces[i].scale == b.pieces[i].scale);
            }
        }
    }
}

static void test_cottage_foundation_butt_joints() {
    std::cout << "[TEST] test_cottage_foundation_butt_joints...\n";
    auto heightFn = [](double x, double y) -> double {
        return 8.0 + 1.5 * std::cos(x * 0.05) + 2.2 * std::sin(y * 0.07);
    };
    auto streamXFn = [](double y) -> double { return 500.0 + y * 0.05; };
    auto streamHWFn = [](double) -> double { return 3.5; };

    wood::Surface climate;
    climate.forest = 0.85;
    climate.biome[0] = 0.85;

    for (std::uint32_t seed = 1; seed <= 20; ++seed) {
        const auto plan = wood::planDiscovery(seed, 0, 0, {0, 0, 8}, climate, heightFn, streamXFn, streamHWFn, true);
        const wood::DiscoveryPiece* prev = nullptr;
        for (const auto& p : plan.pieces) {
            EXPECT_GROUNDED(p, heightFn);
            if (p.name != "cottage_foundation_course") { prev = nullptr; continue; }
            // Same wall = identical yaw; centre spacing equals course length (1.6 m x scale).
            if (prev && prev->yaw == p.yaw) {
                const double expected = 1.6 * p.scale;
                const double vx = p.position.x - prev->position.x;
                const double vy = p.position.y - prev->position.y;
                const double d = std::hypot(vx, vy);
                EXPECT_TRUE(std::abs(d - expected) <= 0.05 * expected);
                // Yaw convention: yaw is the edge direction and SM_FoundationCourse's 1.6 m length lies on
                // local +X (Tools/Prepare-Art.py LENGTH_Y_TO_X). UE yaw 0 = +X, so a course at yaw runs along
                // (cos yaw, sin yaw); consecutive courses of one straight wall must be centred along that line.
                const double kTestPi = 3.14159265358979323846;
                const double yawRad = p.yaw * (kTestPi / 180.0);
                const double ux = std::cos(yawRad);
                const double uy = std::sin(yawRad);
                EXPECT_TRUE(d > 0.0 && std::abs(ux * vx + uy * vy) / d > 0.99);
            }
            prev = &p;
        }
    }
}

int main() {
    std::cout << "Running DiscoveryTests...\n";

    test_types_and_structs();
    test_empty_reservations();
    test_reservation_inclusion();
    test_boundary_points();
    test_exclusion();
    test_multiple_reservations();
    test_zero_and_negative_radius();

    test_dry_stone_shelter_plan();
    test_cottage_corner_plan();
    test_ridge_tor_plan();
    test_stream_footbridge_plan();
    test_guaranteed_sites();
    test_wilderness_cell_untouched();
    test_all_four_types_heightfn_and_reservations();
    test_shelter_walls_contiguous();
    test_discovery_deterministic();
    test_cottage_foundation_butt_joints();

    std::cout << "\nTest Summary: " << (gTestCount - gFailures) << "/" << gTestCount << " passed.\n";

    if (gFailures != 0) {
        std::cerr << "FAIL: " << gFailures << " assertions failed.\n";
        return 1;
    }

    std::cout << "SUCCESS: All tests passed.\n";
    return 0;
}
