#include "Generation/WoodFauna.h"
#include "Generation/WoodGeneration.h"

#include <cstddef>

namespace wood::fauna {
namespace {

// Local salts. WoodSalts.h is the shared registry and is not edited by this module.
constexpr std::uint32_t kSaltFaunaCount = 0xFA0001U;
constexpr std::uint32_t kSaltFaunaKind = 0xFA0002U;
constexpr std::uint32_t kSaltFaunaX = 0xFA0003U;
constexpr std::uint32_t kSaltFaunaY = 0xFA0004U;
constexpr std::uint32_t kSaltFaunaHeading = 0xFA0005U;
constexpr std::uint32_t kSaltFaunaStrangeGate = 0xFA0006U;
constexpr std::uint32_t kSaltFaunaStrangeKind = 0xFA0007U;
// Per-slot offset so each creature slot in a chunk draws independent rolls.
constexpr std::uint32_t kSaltFaunaSlotStride = 0x100U;

// Identical to the project's random(seed,gx,gy,salt) in WoodGeneration.cpp (file-local there).
std::uint32_t hash(std::uint32_t seed, int x, int y, std::uint32_t salt) {
    auto h = seed ^ (static_cast<std::uint32_t>(x) * 0x9e3779b9u) ^ (static_cast<std::uint32_t>(y) * 0x85ebca6bu) ^ salt;
    h ^= h >> 16; h *= 0x7feb352du; h ^= h >> 15; h *= 0x846ca68bu; return h ^ (h >> 16);
}
double random(std::uint32_t seed, int x, int y, std::uint32_t salt) {
    return hash(seed, x, y, salt) / 4294967296.0;
}

using K = CreatureKind;

std::vector<CreatureKind> familyTable(Biome family) {
    switch (family) {
    case Biome::TemperateForest: return {K::Deer, K::Fox, K::Hare, K::Crow, K::Owl, K::Bear};
    case Biome::DryGrassland:    return {K::Hare, K::Fox, K::Crow, K::Deer};
    case Biome::RockyHighlands:  return {K::Crow, K::Fox, K::Hare, K::Elk};
    case Biome::Taiga:           return {K::Elk, K::Fox, K::Owl, K::Hare, K::Bear};
    case Biome::OldGrowthForest: return {K::Deer, K::Owl, K::Fox, K::Bear, K::Crow};
    case Biome::ColdRainforest:  return {K::Deer, K::Owl, K::Crow, K::Bear};
    case Biome::IcyHills:        return {K::Hare, K::Fox, K::Owl, K::Crow};
    case Biome::Savannah:        return {K::Deer, K::Hare, K::Crow, K::Fox};
    case Biome::Swamp:           return {K::Heron, K::Crow, K::Hare};
    case Biome::Marsh:           return {K::Heron, K::Crow, K::Hare, K::Deer};
    case Biome::WarmRainforest:  return {K::Owl, K::Crow, K::Heron, K::Deer};
    case Biome::Prairie:         return {K::Hare, K::Hare, K::Fox, K::Crow, K::Crow, K::Deer};
    }
    return {};
}

// Strange kinds: unreal-region only. Used in place of the family table for about half the slots.
std::vector<CreatureKind> strangeTable() {
    return {K::MothStag, K::GlassHare, K::LanternOwl, K::StoneTortoise, K::ShadowFox};
}

} // namespace

CreatureMind mindFor(CreatureKind kind) {
    CreatureMind mind;
    mind.territorial = kind == K::Bear || kind == K::StoneTortoise || kind == K::ShadowFox;
    return mind;
}

bool isStrange(CreatureKind kind) {
    return static_cast<std::uint8_t>(kind) >= static_cast<std::uint8_t>(K::MothStag);
}

std::vector<CreatureSpawn> spawnCreatures(std::uint32_t seed, int gx, int gy, Biome family, bool unreal) {
    std::vector<CreatureSpawn> out;
    const auto table = familyTable(family);
    if (table.empty()) return out;

    // random() is in [0,1), so count is in [0, kMaxPerChunk].
    const int count = static_cast<int>(random(seed, gx, gy, kSaltFaunaCount) * (kMaxPerChunk + 1));
    for (int i = 0; i < count; ++i) {
        const std::uint32_t off = static_cast<std::uint32_t>(i) * kSaltFaunaSlotStride;
        CreatureSpawn s{};
        if (unreal && random(seed, gx, gy, kSaltFaunaStrangeGate + off) < 0.5) {
            const auto strange = strangeTable();
            const auto sidx = static_cast<std::size_t>(random(seed, gx, gy, kSaltFaunaStrangeKind + off) * strange.size());
            s.kind = strange[sidx];
        } else {
            const auto idx = static_cast<std::size_t>(random(seed, gx, gy, kSaltFaunaKind + off) * table.size());
            s.kind = table[idx];
        }
        s.x = random(seed, gx, gy, kSaltFaunaX + off) * kChunkM;
        s.y = random(seed, gx, gy, kSaltFaunaY + off) * kChunkM;
        s.heading = random(seed, gx, gy, kSaltFaunaHeading + off) * 360.0;
        out.push_back(s);
    }
    return out;
}

CreatureState stepCreature(CreatureState state, double playerDistM, double dtS, CreatureMind& mind) {
    if (state == CreatureState::Idle) {
        mind.farS = 0.0;
        return playerDistM < kNoticeM ? CreatureState::Notice : CreatureState::Idle;
    }

    if (playerDistM > kLoseM) {
        mind.farS += dtS;
        if (mind.farS >= kLoseS) {
            mind.farS = 0.0;
            return CreatureState::Idle;
        }
    } else {
        mind.farS = 0.0;
    }

    switch (state) {
    case CreatureState::Notice:
        return playerDistM < kWatchM ? CreatureState::Watch : CreatureState::Notice;
    case CreatureState::Watch:
        if (playerDistM < kRetreatM) return mind.territorial ? CreatureState::Warn : CreatureState::Retreat;
        return CreatureState::Watch;
    case CreatureState::Retreat:
    case CreatureState::Warn:
    case CreatureState::Idle:
        break;
    }
    return state;
}

} // namespace wood::fauna
