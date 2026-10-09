#include <iostream>
#include <vector>
#include <cstddef>
#include <cstdint>

#include "Generation/WoodGeneration.h"
#include "Generation/WoodFauna.h"

using namespace wood;
using namespace wood::fauna;

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
#define EXPECT_FALSE(expr) check(!static_cast<bool>(expr), "!" #expr, __FILE__, __LINE__)
#define EXPECT_EQ(a, b) check((a) == (b), #a " == " #b, __FILE__, __LINE__)

static const Biome kAllFamilies[] = {
    Biome::TemperateForest, Biome::DryGrassland, Biome::RockyHighlands, Biome::Taiga,
    Biome::OldGrowthForest, Biome::ColdRainforest, Biome::IcyHills, Biome::Savannah,
    Biome::Swamp, Biome::Marsh, Biome::WarmRainforest,
};

static bool sameSpawns(const std::vector<CreatureSpawn>& a, const std::vector<CreatureSpawn>& b) {
    if (a.size() != b.size()) return false;
    for (std::size_t i = 0; i < a.size(); ++i) {
        if (a[i].kind != b[i].kind || a[i].x != b[i].x || a[i].y != b[i].y || a[i].heading != b[i].heading) return false;
    }
    return true;
}

static void test_determinism() {
    std::cout << "[TEST] test_determinism...\n";
    for (Biome f : kAllFamilies) {
        EXPECT_TRUE(sameSpawns(spawnCreatures(42u, 3, -7, f), spawnCreatures(42u, 3, -7, f)));
    }
}

static void test_chunk_order_independence() {
    std::cout << "[TEST] test_chunk_order_independence...\n";
    const std::uint32_t seed = 1234u;
    const auto a1 = spawnCreatures(seed, 0, 0, Biome::Taiga);
    const auto b1 = spawnCreatures(seed, 5, -2, Biome::TemperateForest);
    const auto b2 = spawnCreatures(seed, 5, -2, Biome::TemperateForest);
    const auto a2 = spawnCreatures(seed, 0, 0, Biome::Taiga);
    EXPECT_TRUE(sameSpawns(a1, a2));
    EXPECT_TRUE(sameSpawns(b1, b2));
}

static void test_spawn_bounds_and_tables() {
    std::cout << "[TEST] test_spawn_bounds_and_tables...\n";
    std::size_t total = 0;
    for (Biome f : kAllFamilies) {
        for (int gx = -10; gx <= 10; ++gx) {
            for (int gy = -10; gy <= 10; ++gy) {
                const auto spawns = spawnCreatures(99u, gx, gy, f);
                EXPECT_TRUE(static_cast<int>(spawns.size()) <= kMaxPerChunk);
                total += spawns.size();
                for (const auto& s : spawns) {
                    EXPECT_TRUE(s.x >= 0.0 && s.x < kChunkM);
                    EXPECT_TRUE(s.y >= 0.0 && s.y < kChunkM);
                    EXPECT_TRUE(s.heading >= 0.0 && s.heading < 360.0);
                    // Bear is territorial forest/taiga only; Heron is wetland only.
                    if (s.kind == CreatureKind::Bear) {
                        EXPECT_TRUE(f == Biome::TemperateForest || f == Biome::Taiga ||
                                    f == Biome::OldGrowthForest || f == Biome::ColdRainforest);
                    }
                    if (s.kind == CreatureKind::Heron) {
                        EXPECT_TRUE(f == Biome::Swamp || f == Biome::Marsh || f == Biome::WarmRainforest);
                    }
                }
            }
        }
    }
    EXPECT_TRUE(total > 0);
}

static void test_mind_for_kind() {
    std::cout << "[TEST] test_mind_for_kind...\n";
    EXPECT_TRUE(mindFor(CreatureKind::Bear).territorial);
    EXPECT_FALSE(mindFor(CreatureKind::Deer).territorial);
    EXPECT_FALSE(mindFor(CreatureKind::Fox).territorial);
    EXPECT_FALSE(mindFor(CreatureKind::Heron).territorial);
}

static void test_transitions_reachable() {
    std::cout << "[TEST] test_transitions_reachable...\n";
    CreatureMind timid;
    CreatureMind bear = mindFor(CreatureKind::Bear);

    EXPECT_EQ(stepCreature(CreatureState::Idle, 40.0, 0.1, timid), CreatureState::Idle);
    EXPECT_EQ(stepCreature(CreatureState::Idle, 25.0, 0.1, timid), CreatureState::Notice);
    EXPECT_EQ(stepCreature(CreatureState::Notice, 15.0, 0.1, timid), CreatureState::Watch);
    EXPECT_EQ(stepCreature(CreatureState::Notice, 5.0, 0.1, timid), CreatureState::Watch);
    EXPECT_EQ(stepCreature(CreatureState::Watch, 25.0, 0.1, timid), CreatureState::Watch);
    EXPECT_EQ(stepCreature(CreatureState::Watch, 5.0, 0.1, timid), CreatureState::Retreat);
    EXPECT_EQ(stepCreature(CreatureState::Watch, 5.0, 0.1, bear), CreatureState::Warn);
}

static void test_far_return_to_idle() {
    std::cout << "[TEST] test_far_return_to_idle...\n";
    CreatureMind m;
    CreatureState s = CreatureState::Watch;
    // 9.5 s beyond kLoseM: still Watch.
    for (int i = 0; i < 19; ++i) s = stepCreature(s, 40.0, 0.5, m);
    EXPECT_EQ(s, CreatureState::Watch);
    // Reaching 10 s: Idle.
    s = stepCreature(s, 40.0, 0.5, m);
    EXPECT_EQ(s, CreatureState::Idle);

    // Retreat also returns to Idle, and a return inside kLoseM resets the timer.
    CreatureMind m2;
    CreatureState r = CreatureState::Retreat;
    for (int i = 0; i < 8; ++i) r = stepCreature(r, 40.0, 1.0, m2);
    r = stepCreature(r, 20.0, 1.0, m2);
    EXPECT_EQ(m2.farS, 0.0);
    for (int i = 0; i < 9; ++i) r = stepCreature(r, 40.0, 1.0, m2);
    EXPECT_EQ(r, CreatureState::Retreat);
    r = stepCreature(r, 40.0, 1.0, m2);
    EXPECT_EQ(r, CreatureState::Idle);
}

static void test_no_approach_or_attack() {
    std::cout << "[TEST] test_no_approach_or_attack...\n";
    EXPECT_EQ(static_cast<int>(CreatureState::Idle), 0);
    EXPECT_EQ(static_cast<int>(CreatureState::Warn), 4);

    const double dists[] = {0.0, 5.0, 12.0, 20.0, 33.0};
    for (double d : dists) {
        CreatureMind timid;
        EXPECT_EQ(stepCreature(CreatureState::Retreat, d, 0.1, timid), CreatureState::Retreat);
        CreatureMind bear = mindFor(CreatureKind::Bear);
        EXPECT_EQ(stepCreature(CreatureState::Warn, d, 0.1, bear), CreatureState::Warn);
    }
    // Retreat and Warn never re-enter Watch or Notice on approach.
    CreatureMind m;
    EXPECT_EQ(stepCreature(CreatureState::Retreat, 12.0, 0.1, m), CreatureState::Retreat);
}

static void test_spawn_count_cap() {
    std::cout << "[TEST] test_spawn_count_cap...\n";
    EXPECT_EQ(kMaxPerChunk, 3);
}

static void test_strange_gated_by_unreal() {
    std::cout << "[TEST] test_strange_gated_by_unreal...\n";
    std::size_t offStrange = 0;
    std::size_t onStrange = 0;
    std::size_t onTotal = 0;
    for (int i = 0; i < 5000; ++i) {
        const Biome f = kAllFamilies[i % (sizeof(kAllFamilies) / sizeof(kAllFamilies[0]))];
        const int gx = i % 100 - 50;
        const int gy = i / 100 - 25;
        for (const auto& s : spawnCreatures(7777u, gx, gy, f)) {
            if (isStrange(s.kind)) ++offStrange;
        }
        for (const auto& s : spawnCreatures(7777u, gx, gy, f, false)) {
            if (isStrange(s.kind)) ++offStrange;
        }
        for (const auto& s : spawnCreatures(7777u, gx, gy, f, true)) {
            ++onTotal;
            if (isStrange(s.kind)) ++onStrange;
            EXPECT_TRUE(s.x >= 0.0 && s.x < kChunkM);
            EXPECT_TRUE(s.y >= 0.0 && s.y < kChunkM);
            EXPECT_TRUE(s.heading >= 0.0 && s.heading < 360.0);
        }
    }
    EXPECT_EQ(offStrange, static_cast<std::size_t>(0));
    EXPECT_TRUE(onTotal > 0);
    EXPECT_TRUE(onStrange > 0);
    // About half of unreal spawns are strange: accept 40%..60%.
    EXPECT_TRUE(onStrange * 10 >= onTotal * 4 && onStrange * 10 <= onTotal * 6);
}

static void test_determinism_unreal() {
    std::cout << "[TEST] test_determinism_unreal...\n";
    for (Biome f : kAllFamilies) {
        EXPECT_TRUE(sameSpawns(spawnCreatures(42u, 3, -7, f, true), spawnCreatures(42u, 3, -7, f, true)));
    }
    EXPECT_TRUE(sameSpawns(spawnCreatures(42u, 3, -7, Biome::Taiga, false), spawnCreatures(42u, 3, -7, Biome::Taiga)));
}

static void test_strange_minds() {
    std::cout << "[TEST] test_strange_minds...\n";
    EXPECT_FALSE(mindFor(CreatureKind::MothStag).territorial);
    EXPECT_FALSE(mindFor(CreatureKind::GlassHare).territorial);
    EXPECT_FALSE(mindFor(CreatureKind::LanternOwl).territorial);
    EXPECT_TRUE(mindFor(CreatureKind::StoneTortoise).territorial);
    EXPECT_TRUE(mindFor(CreatureKind::ShadowFox).territorial);
    EXPECT_FALSE(isStrange(CreatureKind::Heron));
    EXPECT_TRUE(isStrange(CreatureKind::MothStag));
    EXPECT_TRUE(isStrange(CreatureKind::ShadowFox));

    // Timid strange kinds retreat, territorial ones warn. Neither approaches.
    CreatureMind timid = mindFor(CreatureKind::GlassHare);
    EXPECT_EQ(stepCreature(CreatureState::Watch, 5.0, 0.1, timid), CreatureState::Retreat);
    CreatureMind territorial = mindFor(CreatureKind::ShadowFox);
    EXPECT_EQ(stepCreature(CreatureState::Watch, 5.0, 0.1, territorial), CreatureState::Warn);
    EXPECT_EQ(stepCreature(CreatureState::Retreat, 12.0, 0.1, timid), CreatureState::Retreat);
    EXPECT_EQ(stepCreature(CreatureState::Warn, 12.0, 0.1, territorial), CreatureState::Warn);
}

int main() {
    test_determinism();
    test_chunk_order_independence();
    test_spawn_bounds_and_tables();
    test_mind_for_kind();
    test_transitions_reachable();
    test_far_return_to_idle();
    test_no_approach_or_attack();
    test_spawn_count_cap();
    test_strange_gated_by_unreal();
    test_determinism_unreal();
    test_strange_minds();

    if (gFailures == 0) {
        std::cout << "PASS: " << gTestCount << " fauna checks\n";
        return 0;
    }
    std::cout << "FAIL: " << gFailures << " of " << gTestCount << " fauna checks\n";
    return 1;
}
