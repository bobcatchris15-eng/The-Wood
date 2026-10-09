#pragma once
#include <cstdint>
#include <optional>
#include "WoodGeneration.h"

// Engine-independent landmark placement. Coordinates and heights are metres.
namespace wood::landmark {

enum class LandmarkKind : int { GiantTree, Spire, Tower, StoneRing, Waterfall };

struct Landmark {
    LandmarkKind kind = LandmarkKind::GiantTree;
    double x = 0, y = 0, z = 0;
    double heightM = 0;
    double footprintRadiusM = 0;
};

// No per-point canopy height API exists; this conservative ceiling stands in for local canopy height.
inline constexpr double kCanopyCeilingM = 40.0;
// Minimum clearance of heightM above the canopy ceiling (metres).
inline constexpr double kVisibilityMarginM = 8.0;
// Maximum walkable step slope (degrees), applied per 2 m grid step.
inline constexpr double kMaxStepSlopeDeg = 38.0;
// Minimum horizontal distance from a non-waterfall landmark to the stream centre line (metres).
inline constexpr double kStreamClearM = 15.0;

// At most one landmark per region; empty for roughly 60% of regions and for regions that fail placement.
std::optional<Landmark> placeLandmark(std::uint32_t seed, int regionQ, int regionR, const World& world);

// True when a 2 m grid path with every step slope <= kMaxStepSlopeDeg links the region centre (x0,y0)
// to the landmark footprint edge, searching a bounded window around the centre.
bool reachableOnFoot(const World& world, double x0, double y0, const Landmark& lm);

} // namespace wood::landmark
