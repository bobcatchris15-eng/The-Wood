#include <cmath>
#include <cstdint>
#include <iostream>
#include <vector>

#include "Generation/WoodLandmarks.h"

using namespace wood;
using namespace wood::landmark;

static int gTestCount = 0;
static int gFailures = 0;

static void check(bool cond, const char* expr, const char* file, int line) {
    ++gTestCount;
    if (!cond) {
        std::cerr << "CHECK FAILED: " << expr << " at " << file << ":" << line << "\n";
        ++gFailures;
    }
}

#define EXPECT_TRUE(expr) check(static_cast<bool>(expr), #expr, __FILE__, __LINE__)

static const std::uint32_t kSeed = 12345u;
static const int kQMin = -25, kQMax = 24, kRMin = -20, kRMax = 19; // 50 x 40 = 2000 regions

static bool sameLandmark(const Landmark& a, const Landmark& b) {
    return a.kind == b.kind && a.x == b.x && a.y == b.y && a.z == b.z &&
           a.heightM == b.heightM && a.footprintRadiusM == b.footprintRadiusM;
}

static bool isForest(Biome b) {
    return b == Biome::TemperateForest || b == Biome::OldGrowthForest || b == Biome::ColdRainforest ||
           b == Biome::WarmRainforest || b == Biome::Taiga || b == Biome::Swamp;
}
static bool isHighland(Biome b) { return b == Biome::RockyHighlands || b == Biome::IcyHills; }
static bool isGrass(Biome b) { return b == Biome::DryGrassland || b == Biome::Savannah; }

static void test_determinism(const World& world) {
    std::cout << "[TEST] test_determinism...\n";
    for (int q = -10; q < 10; ++q) {
        for (int r = -10; r < 10; ++r) {
            const auto a = placeLandmark(kSeed, q, r, world);
            const auto b = placeLandmark(kSeed, q, r, world);
            EXPECT_TRUE(a.has_value() == b.has_value());
            if (a && b) EXPECT_TRUE(sameLandmark(*a, *b));
        }
    }
}

static void test_placement_rate_and_mapping(const World& world, std::vector<std::pair<int, int>>& placed) {
    std::cout << "[TEST] test_placement_rate_and_mapping...\n";
    int count = 0, total = 0;
    for (int q = kQMin; q <= kQMax; ++q) {
        for (int r = kRMin; r <= kRMax; ++r) {
            ++total;
            const auto lm = placeLandmark(kSeed, q, r, world);
            if (!lm) continue;
            ++count;
            placed.emplace_back(q, r);
            const Biome family = world.region(q, r).family;
            switch (lm->kind) {
            case LandmarkKind::GiantTree: EXPECT_TRUE(isForest(family)); break;
            case LandmarkKind::Spire:
            case LandmarkKind::Tower:     EXPECT_TRUE(isHighland(family)); break;
            case LandmarkKind::StoneRing: EXPECT_TRUE(isGrass(family)); break;
            case LandmarkKind::Waterfall: break; // any family, gated by stream slope instead
            }
            if (lm->kind != LandmarkKind::Waterfall) {
                EXPECT_TRUE(std::fabs(lm->x - world.streamX(lm->y)) >= kStreamClearM);
            }
        }
    }
    const double rate = static_cast<double>(count) / static_cast<double>(total);
    std::cout << "  placed " << count << " of " << total << " (" << rate << ")\n";
    EXPECT_TRUE(total == 2000);
    EXPECT_TRUE(std::fabs(rate - 0.40) <= 0.05);
}

static void test_visibility_and_height(const World& world, const std::vector<std::pair<int, int>>& placed) {
    std::cout << "[TEST] test_visibility_and_height...\n";
    for (const auto& p : placed) {
        const auto lm = placeLandmark(kSeed, p.first, p.second, world);
        EXPECT_TRUE(lm.has_value());
        if (!lm) continue;
        EXPECT_TRUE(lm->heightM >= kCanopyCeilingM + kVisibilityMarginM);
        EXPECT_TRUE(lm->z == world.terrainHeight(lm->x, lm->y));
    }
}

static void test_reachability(const World& world, const std::vector<std::pair<int, int>>& placed) {
    std::cout << "[TEST] test_reachability...\n";
    const std::size_t limit = placed.size() < 150 ? placed.size() : 150;
    for (std::size_t i = 0; i < limit; ++i) {
        const auto lm = placeLandmark(kSeed, placed[i].first, placed[i].second, world);
        if (!lm) continue;
        const Region reg = world.region(placed[i].first, placed[i].second);
        EXPECT_TRUE(reachableOnFoot(world, reg.origin.x, reg.origin.y, *lm));
    }
    // A landmark well outside the search window must not be reported reachable.
    Landmark far;
    far.kind = LandmarkKind::Tower;
    far.x = 500.0;
    far.y = 500.0;
    far.z = world.terrainHeight(far.x, far.y);
    far.heightM = kCanopyCeilingM + kVisibilityMarginM;
    far.footprintRadiusM = 5.0;
    EXPECT_TRUE(!reachableOnFoot(world, 0.0, 0.0, far));
}

int main() {
    const World world(Settings{kSeed, 128, 64});
    test_determinism(world);
    std::vector<std::pair<int, int>> placed;
    test_placement_rate_and_mapping(world, placed);
    test_visibility_and_height(world, placed);
    test_reachability(world, placed);

    if (gFailures == 0) {
        std::cout << "PASS: " << gTestCount << " landmark checks\n";
        return 0;
    }
    std::cout << "FAIL: " << gFailures << " of " << gTestCount << " landmark checks\n";
    return 1;
}
