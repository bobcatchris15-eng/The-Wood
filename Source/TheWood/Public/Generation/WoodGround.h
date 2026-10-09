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
 {{0.6f,0.f,0.f,0.4f},0.85f,0.82f,0.75f}, // OldGrowthForest -> ForestLitter 0.6 / MossDamp 0.4
 {{0.25f,0.f,0.f,0.75f},0.80f,0.95f,0.82f}, // ColdRainforest  -> MossDamp 0.75 / ForestLitter 0.25
 {{0.f,0.30f,0.55f,0.15f},1.25f,1.28f,1.32f}, // IcyHills        -> Grass 0.30 / RockGravel 0.55 / MossDamp 0.15
 {{0.15f,0.75f,0.10f,0.f},1.10f,1.00f,0.78f}, // Savannah        -> ForestLitter 0.15 / Grass 0.75 / RockGravel 0.10
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
