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

// Strange kinds (MothStag onward) spawn only through the unreal flag of spawnCreatures.
enum class CreatureKind : std::uint8_t {
    Deer, Fox, Hare, Crow, Owl, Elk, Bear, Heron,
    MothStag, GlassHare, LanternOwl, StoneTortoise, ShadowFox
};

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

// Mind for a kind: territorial for Bear, StoneTortoise and ShadowFox.
CreatureMind mindFor(CreatureKind kind);

// True for the strange kinds (MothStag onward).
bool isStrange(CreatureKind kind);

// Pure in (seed, gx, gy, family, unreal). At most kMaxPerChunk entries.
// unreal=true: roughly half of the slots draw a strange kind instead of the family table.
std::vector<CreatureSpawn> spawnCreatures(std::uint32_t seed, int gx, int gy, Biome family, bool unreal = false);

// One transition per call. Distance drives all transitions; dtS accrues the Idle-return timer.
CreatureState stepCreature(CreatureState state, double playerDistM, double dtS, CreatureMind& mind);

} // namespace wood::fauna
