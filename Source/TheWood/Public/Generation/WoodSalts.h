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
// Region unreal flag, p=0.10 (describe()).
inline constexpr std::uint32_t RegionUnreal=716;
// Region ruins flag, p=1/3 (describe()).
inline constexpr std::uint32_t RegionRuins=717;
// Region unreal overlay pick, unreal regions only (unreal::pick()).
inline constexpr std::uint32_t RegionOverlay=718;
// Region epoch seed mix; regionSeed() adds the epoch count to it (epoch>0 only).
inline constexpr std::uint32_t RegionEpoch=0xE90C0000U;
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
// Climate temperature field noise (regionFamily()).
inline constexpr std::uint32_t ClimateTemperature=1009;
// Climate moisture field noise (regionFamily()).
inline constexpr std::uint32_t ClimateMoisture=1013;
// Climate relief noise for rocky highlands (regionFamily()).
inline constexpr std::uint32_t ClimateRelief=1019;

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
// Natural discovery allocation roll, non-ruin cells (planDiscovery()).
inline constexpr std::uint32_t NaturalCell=0x9A7C1U;
// SpringSeep RNG seed mix (generateSpringSeep()).
inline constexpr std::uint32_t SpringSeepRng=0x5EE9U;
// MossyRockHollow RNG seed mix (generateMossyRockHollow()).
inline constexpr std::uint32_t MossyRockHollowRng=0x3055U;
// WindthrowClearing RNG seed mix (generateWindthrowClearing()).
inline constexpr std::uint32_t WindthrowClearingRng=0x71A0U;
// FallenLogColony RNG seed mix (generateFallenLogColony()).
inline constexpr std::uint32_t FallenLogColonyRng=0xF0C1U;
// RidgeOverlook RNG seed mix (generateRidgeOverlook()).
inline constexpr std::uint32_t RidgeOverlookRng=0x0BE7U;
// Ruin extra allocation roll, non-highland ruin cells (planDiscovery()).
inline constexpr std::uint32_t RuinExtraCell=0x4E7A1U;
// DryStoneWallStub RNG seed mix (generateDryStoneWallStub()).
inline constexpr std::uint32_t DryStoneWallStubRng=0x7A11U;
// FoundationStrip RNG seed mix (generateFoundationStrip()).
inline constexpr std::uint32_t FoundationStripRng=0xF0A5U;
// StonePierStump RNG seed mix (generateStonePierStump()).
inline constexpr std::uint32_t StonePierStumpRng=0x91E2U;
// MonolithStanding RNG seed mix (generateMonolithStanding()).
inline constexpr std::uint32_t MonolithStandingRng=0x3A17U;
// Unreal-region allocation roll, unreal cells only (planDiscovery()).
inline constexpr std::uint32_t UnrealCell=0x0E7A1U;
// StaircaseToNowhere RNG seed mix (generateStaircaseToNowhere()).
inline constexpr std::uint32_t StaircaseRng=0x57A1U;
// RustedSword RNG seed mix (generateRustedSword()).
inline constexpr std::uint32_t RustedSwordRng=0x5A0DU;
// StoneChessPiece RNG seed mix (generateStoneChessPiece()).
inline constexpr std::uint32_t StoneChessPieceRng=0xC4E5U;
// BrokenCrown RNG seed mix (generateBrokenCrown()).
inline constexpr std::uint32_t BrokenCrownRng=0xBC0AU;

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
// Tree species weight roll in tree layer (+10).
inline constexpr std::uint32_t LayerSpecies=10;

// Fallen deadwood layer base (layer spacing 10, one lattice cell per 100 m²).
inline constexpr std::uint32_t DeadwoodLayer=140;

} // namespace Salt
} // namespace wood
