#pragma once
#include <array>
#include <cstddef>
#include "Generation/WoodGeneration.h"

namespace wood::ground {

// Vertex RGBA channels are ground archetypes, decoupled from the biome family count.
enum class Archetype : int { ForestLitter=0, Grass=1, RockGravel=2, MossDamp=3 };
inline constexpr int ArchetypeCount=4;
inline constexpr int BiomeCount=kFamilyCount;

struct FamilyLook {
 std::array<float,ArchetypeCount> archetype;
 float tintR,tintG,tintB;
};

// Row index == static_cast<int>(Biome). Existing four families map to identity archetypes with tint (1,1,1).
inline constexpr std::array<FamilyLook,BiomeCount> FamilyLooks{{
 {{1.f,0.f,0.f,0.f},1.f,1.f,1.f}, // TemperateForest -> ForestLitter
 {{0.f,1.f,0.f,0.f},1.f,1.f,1.f}, // DryGrassland    -> Grass
 {{0.f,0.f,1.f,0.f},1.f,1.f,1.f}, // RockyHighlands  -> RockGravel
 {{0.f,0.f,0.f,1.f},1.f,1.f,1.f}, // Taiga           -> MossDamp
}};

static_assert(FamilyLooks.size()==BiomeCount,"FamilyLooks needs one row per Biome value");
static_assert(BiomeCount==kFamilyCount,"BiomeCount out of sync with kFamilyCount");

struct GroundShade {
 std::array<float,ArchetypeCount> archetype;
 float tintR,tintG,tintB;
};

// Family-weighted sum of archetype rows and tints. Deterministic; no normalisation.
GroundShade shade(const wood::Surface& Surface);

} // namespace wood::ground
