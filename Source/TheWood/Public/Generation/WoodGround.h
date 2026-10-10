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
 {{0.35f,0.10f,0.f,0.55f},0.70f,0.78f,0.62f}, // Swamp           -> MossDamp 0.55 / ForestLitter 0.35 / Grass 0.10
 {{0.10f,0.60f,0.f,0.30f},0.85f,0.95f,0.70f}, // Marsh           -> Grass 0.60 / MossDamp 0.30 / ForestLitter 0.10
 {{0.5f,0.f,0.f,0.5f},0.72f,0.90f,0.66f}, // WarmRainforest  -> ForestLitter 0.5 / MossDamp 0.5
 {{0.f,1.f,0.f,0.f},0.90f,1.12f,0.85f}, // Prairie         -> Grass; greener tint than DryGrassland
}};

static_assert(FamilyLooks.size()==BiomeCount,"FamilyLooks needs one row per Biome value");
static_assert(BiomeCount==kFamilyCount,"BiomeCount out of sync with kFamilyCount");

struct GroundShade {
 std::array<float,ArchetypeCount> archetype;
 float tintR,tintG,tintB;
};

// Permanent snow/frost cover 0..1 from climate (family weights, temperature) and elevation. Flats take it; the material
// removes it from steep slopes. IcyHills is near-full; Taiga and RockyHighlands only where cold and high.
inline float snowCover(const wood::Surface& S) {
 const auto Clamp01=[](double V){ return V<0.0?0.0:(V>1.0?1.0:V); };
 const double Cold=Clamp01((4.0-S.temperature)/10.0);
 const double Elev=0.6+0.4*Clamp01(S.height/150.0);
 const double Cover=S.biome[static_cast<std::size_t>(wood::Biome::IcyHills)]*0.95
  +(S.biome[static_cast<std::size_t>(wood::Biome::Taiga)]*0.6+S.biome[static_cast<std::size_t>(wood::Biome::RockyHighlands)]*0.7)*Cold*Elev;
 return static_cast<float>(Clamp01(Cover));
}

// Family-weighted sum of archetype rows and tints. Deterministic; no normalisation.
GroundShade shade(const wood::Surface& Surface);

} // namespace wood::ground
