#pragma once
#include <cstdint>
#include <optional>
#include <string>
#include <utility>
#include <vector>
#include "Generation/WoodMemory.h"
#include "Generation/WoodStreaming.h"

namespace wood::save {

// Highest save schema this build can read. Files with a larger version are rejected.
constexpr int kSupportedVersion = 1;

struct SaveState {
 int version=1;
 std::uint32_t seed=0;
 double playerX=0,playerY=0,playerZ=0,yaw=0,pitch=0;
 double clockSeconds=0;
 bool seated=false,accelerated=false;
 bool enteredWild=false;
 std::vector<streaming::Coord> retainedChunks;
 std::vector<std::pair<memory::RegionKey,std::uint32_t>> epochs;
};

// Compact JSON, fixed key order. Doubles use max_digits10 so parsing restores identical bits.
// Non-finite doubles are written as null and rejected by fromJson.
std::string toJson(const SaveState& state);

// Hand-written parser. Returns nullopt on malformed JSON, type mismatch on a known key,
// out-of-range integers, or version < 1 or > kSupportedVersion.
// Unknown keys are ignored, missing keys keep their defaults, key order is irrelevant.
std::optional<SaveState> fromJson(const std::string& json);

} // namespace wood::save
