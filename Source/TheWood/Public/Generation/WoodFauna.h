#pragma once

#include <cstdint>
#include <vector>

// Engine-free fauna core. Metres and degrees only. No Unreal headers.
namespace wood {
enum class Biome : int;
}

namespace wood::fauna {

// Chunk side length in metres. Spawn x/y are chunk-local in [0, kChunkM).
inline constexpr double kChunkM = 64.0;
inline constexpr int kMaxPerChunk = 3;

// Player-distance thresholds, metres.
inline constexpr double kNoticeM = 30.0;
inline constexpr double kWatchM = 18.0;
inline constexpr double kRetreatM = 8.0;
inline constexpr double kLoseM = 35.0;
// Seconds beyond kLoseM before a creature returns to Idle.
inline constexpr double kLoseS = 10.0;

enum class CreatureKind : std::uint8_t { Deer, Fox, Hare, Crow, Owl, Elk, Bear, Heron };

// Idle -> Notice -> Watch -> Retreat (timid) | Warn (territorial). Never approaches, never attacks.
enum class CreatureState : std::uint8_t { Idle, Notice, Watch, Retreat, Warn };

struct CreatureSpawn {
    CreatureKind kind;
    double x;       // chunk-local metres
    double y;       // chunk-local metres
    double heading; // degrees [0, 360)
};

struct CreatureMind {
    bool territorial = false; // true: Watch -> Warn instead of Retreat
    double farS = 0.0;        // accumulated seconds beyond kLoseM
};

// Mind for a kind: territorial only for Bear.
CreatureMind mindFor(CreatureKind kind);

// Pure in (seed, gx, gy, family). At most kMaxPerChunk entries.
std::vector<CreatureSpawn> spawnCreatures(std::uint32_t seed, int gx, int gy, Biome family);

// One transition per call. Distance drives all transitions; dtS accrues the Idle-return timer.
CreatureState stepCreature(CreatureState state, double playerDistM, double dtS, CreatureMind& mind);

} // namespace wood::fauna
