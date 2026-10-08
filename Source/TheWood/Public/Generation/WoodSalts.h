#pragma once

#include <cstdint>

// New systems must add a unique salt here; never reuse a value.
namespace wood {
namespace Salt {

// Region identity hash (describe()).
inline constexpr std::uint32_t RegionIdentity=701;
// Region biome family pick (describe()).
inline constexpr std::uint32_t RegionFamily=704;
// Region lighting phase (describe()).
inline constexpr std::uint32_t RegionPhase=705;
// Value-noise lattice corner hash (noise()).
inline constexpr std::uint32_t NoiseLattice=1;

// Noise seed offsets: added to Settings seed, one per noise field.
// Channel half-width wobble (channelHalfWidth()).
inline constexpr std::uint32_t ChannelWidth=911;
// Pool depth wobble (ground()).
inline constexpr std::uint32_t PoolDepth=617;
// Bank width wobble (ground()).
inline constexpr std::uint32_t BankWidth=401;
// Coarse bank contour (ground()).
inline constexpr std::uint32_t BankContour=331;
// Fine bank contour (ground()).
inline constexpr std::uint32_t BankContourFine=709;
// Base terrain detail (ground()).
inline constexpr std::uint32_t Detail=17;
// Highland mountain mass (ground()).
inline constexpr std::uint32_t MountainMass=83;
// Highland crag step noise (ground()).
inline constexpr std::uint32_t CragNoise=199;
// Highland crag relief (ground()).
inline constexpr std::uint32_t CragRelief=251;
// Grassland prairie undulation (ground()).
inline constexpr std::uint32_t Prairie=151;
// Habitat patch cover (chunk layers).
inline constexpr std::uint32_t PatchCover=101;
// Tree regeneration patches (chunk layers).
inline constexpr std::uint32_t Regeneration=509;
// Ground-cover colonies (chunk layers).
inline constexpr std::uint32_t Colony=311;
// Rocky patch noise (chunk layers).
inline constexpr std::uint32_t Rocky=207;
// Riparian rock spread (chunk layers).
inline constexpr std::uint32_t Riparian=419;
// Tallgrass prairie clump noise (chunk layers).
inline constexpr std::uint32_t PrairieClump=577;
// Taiga moss carpet patch noise (chunk layers).
inline constexpr std::uint32_t TaigaMoss=613;

// Discovery cell allocation hash (hashCell()).
inline constexpr std::uint32_t DiscoveryCell=0xD15C07U;
// DryStoneShelter RNG seed mix (generateDryStoneShelter()).
inline constexpr std::uint32_t DryStoneShelterRng=0x5D0EU;
// CottageCorner RNG seed mix (generateCottageCorner()).
inline constexpr std::uint32_t CottageCornerRng=0xC077U;
// StreamFootbridge RNG seed mix (generateStreamFootbridge()).
inline constexpr std::uint32_t StreamFootbridgeRng=0xB71DU;
// RidgeTor RNG seed mix (generateRidgeTor()).
inline constexpr std::uint32_t RidgeTorRng=0x708U;

// Chunk placement layer base salts. Each layer adds the offsets below.
// Tree layer base (layer spacing 8.5).
inline constexpr std::uint32_t TreeLayer=20;
// Ground-cover layer base: ferns, grass, rocks (layer spacing 1.5).
inline constexpr std::uint32_t GroundCoverLayer=40;
// Rock layer base (layer spacing 6).
inline constexpr std::uint32_t RockLayer=60;
// Tallgrass prairie layer base (layer spacing 1.0, grassland cores only).
inline constexpr std::uint32_t PrairieLayer=80;
// Taiga moss carpet layer base (layer spacing 1.5, taiga cores only).
inline constexpr std::uint32_t TaigaMossLayer=120;

// Layer offsets, added to a layer base salt.
// Y position jitter (+1).
inline constexpr std::uint32_t LayerJitterY=1;
// Spawn choice roll (+2).
inline constexpr std::uint32_t LayerChoice=2;
// Size roll (+3).
inline constexpr std::uint32_t LayerSize=3;
// Yaw roll (+4).
inline constexpr std::uint32_t LayerYaw=4;
// Fern-versus-grass roll (+5).
inline constexpr std::uint32_t LayerFernChance=5;
// Young-tree roll (+7).
inline constexpr std::uint32_t LayerYoung=7;
// Rock-replacement roll in ground-cover layer (+9).
inline constexpr std::uint32_t LayerRockChance=9;

} // namespace Salt
} // namespace wood
