#include "Generation/WoodLandmarks.h"

#include <algorithm>
#include <cmath>
#include <cstddef>
#include <vector>

namespace wood::landmark {
namespace {

// Local salts; unique within the landmark stage and not present in WoodSalts.h.
constexpr std::uint32_t kSaltLandmarkPresent = 0x1A4D0001U;
constexpr std::uint32_t kSaltLandmarkKind    = 0x1A4D0002U;
constexpr std::uint32_t kSaltLandmarkOffX    = 0x1A4D0003U;
constexpr std::uint32_t kSaltLandmarkOffY    = 0x1A4D0004U;
constexpr std::uint32_t kSaltLandmarkHeight  = 0x1A4D0005U;
constexpr std::uint32_t kSaltLandmarkPick    = 0x1A4D0006U;
constexpr std::uint32_t kSaltLandmarkStride  = 0x100U;

constexpr double kPi = 3.14159265358979323846;
constexpr double kPresentP = 0.40;
constexpr int kAttempts = 4;
constexpr double kPlaceRadiusM = 90.0;
constexpr double kDiscoveryClearM = 40.0;
constexpr double kWaterfallSlopeTan = 0.36397; // tan(20 deg) rise/run
constexpr double kWaterfallScanM = 150.0;
constexpr double kWaterfallScanStepM = 5.0;

// Grid for reachability: 2 m cells over a +/-120 m window around the region centre.
constexpr double kCellM = 2.0;
constexpr int kHalfCells = 60;
constexpr int kGridN = 2 * kHalfCells + 1;

// Identical in form to the project's random(seed,gx,gy,salt) in WoodGeneration.cpp (file-local there).
std::uint32_t landmarkHash(std::uint32_t seed, int x, int y, std::uint32_t salt) {
    auto h = seed ^ (static_cast<std::uint32_t>(x) * 0x9e3779b9u) ^ (static_cast<std::uint32_t>(y) * 0x85ebca6bu) ^ salt;
    h ^= h >> 16; h *= 0x7feb352du; h ^= h >> 15; h *= 0x846ca68bu; return h ^ (h >> 16);
}
double landmarkRandom(std::uint32_t seed, int x, int y, std::uint32_t salt) {
    return landmarkHash(seed, x, y, salt) / 4294967296.0;
}

double footprintFor(LandmarkKind kind) {
    switch (kind) {
    case LandmarkKind::GiantTree: return 4.0;
    case LandmarkKind::Spire:     return 6.0;
    case LandmarkKind::Tower:     return 5.0;
    case LandmarkKind::StoneRing: return 9.0;
    case LandmarkKind::Waterfall: return 8.0;
    }
    return 4.0;
}

// Family-weighted kind pick. Returns false when the family has no landmark for this roll.
bool chooseKind(Biome family, double roll, LandmarkKind& out) {
    switch (family) {
    case Biome::RockyHighlands:
    case Biome::IcyHills:
        if (roll < 0.45) out = LandmarkKind::Spire;
        else if (roll < 0.80) out = LandmarkKind::Tower;
        else out = LandmarkKind::Waterfall;
        return true;
    case Biome::TemperateForest:
    case Biome::OldGrowthForest:
    case Biome::ColdRainforest:
    case Biome::WarmRainforest:
    case Biome::Taiga:
    case Biome::Swamp:
        out = roll < 0.80 ? LandmarkKind::GiantTree : LandmarkKind::Waterfall;
        return true;
    case Biome::DryGrassland:
    case Biome::Savannah:
        out = LandmarkKind::StoneRing;
        return true;
    case Biome::Marsh:
        out = LandmarkKind::Waterfall;
        return true;
    }
    return false;
}


// Rise/run gradient magnitude from the realized terrain, 2 m central difference.
double gradientAt(const World& world, double x, double y) {
    const double d = 2.0;
    const double gx = (world.terrainHeight(x + d, y) - world.terrainHeight(x - d, y)) / (2.0 * d);
    const double gy = (world.terrainHeight(x, y + d) - world.terrainHeight(x, y - d)) / (2.0 * d);
    return std::sqrt(gx * gx + gy * gy);
}

Landmark makeLandmark(std::uint32_t seed, int q, int r, LandmarkKind kind, int attempt, double x, double y, const World& world) {
    Landmark lm;
    lm.kind = kind;
    lm.x = x;
    lm.y = y;
    lm.z = world.terrainHeight(x, y);
    const std::uint32_t off = static_cast<std::uint32_t>(attempt) * kSaltLandmarkStride;
    lm.heightM = kCanopyCeilingM + kVisibilityMarginM + landmarkRandom(seed, q, r, kSaltLandmarkHeight + off) * 12.0;
    lm.footprintRadiusM = footprintFor(kind);
    return lm;
}

// Non-waterfall candidate: region centre plus a salted offset.
bool offsetSite(std::uint32_t seed, int q, int r, const World& world, const Region& reg, int attempt, double& x, double& y) {
    const std::uint32_t off = static_cast<std::uint32_t>(attempt) * kSaltLandmarkStride;
    const double ox = (landmarkRandom(seed, q, r, kSaltLandmarkOffX + off) * 2.0 - 1.0) * kPlaceRadiusM;
    const double oy = (landmarkRandom(seed, q, r, kSaltLandmarkOffY + off) * 2.0 - 1.0) * kPlaceRadiusM;
    x = reg.origin.x + ox;
    y = reg.origin.y + oy;
    return std::fabs(x - world.streamX(y)) >= kStreamClearM;
}

// Waterfall candidate: the attempt-th qualifying stream row where the stream crosses a slope.
bool waterfallSite(std::uint32_t seed, int q, int r, const World& world, const Region& reg, int attempt, double& x, double& y) {
    std::vector<double> rows;
    for (double yy = reg.origin.y - kWaterfallScanM; yy <= reg.origin.y + kWaterfallScanM; yy += kWaterfallScanStepM) {
        const double sx = world.streamX(yy);
        if (gradientAt(world, sx, yy) >= kWaterfallSlopeTan) rows.push_back(yy);
    }
    if (rows.empty()) return false;
    const std::uint32_t off = static_cast<std::uint32_t>(attempt) * kSaltLandmarkStride;
    const double roll = landmarkRandom(seed, q, r, kSaltLandmarkPick + off);
    const std::size_t idx = std::min(rows.size() - 1, static_cast<std::size_t>(roll * static_cast<double>(rows.size())));
    y = rows[idx];
    x = world.streamX(y);
    return true;
}

} // namespace

bool reachableOnFoot(const World& world, double x0, double y0, const Landmark& lm) {
    std::vector<double> h(static_cast<std::size_t>(kGridN) * kGridN);
    auto idx = [](int i, int j) { return static_cast<std::size_t>(j * kGridN + i); };
    for (int j = 0; j < kGridN; ++j) {
        for (int i = 0; i < kGridN; ++i) {
            h[idx(i, j)] = world.terrainHeight(x0 + (i - kHalfCells) * kCellM, y0 + (j - kHalfCells) * kCellM);
        }
    }
    const double maxTan = std::tan(kMaxStepSlopeDeg * kPi / 180.0);
    std::vector<char> seen(h.size(), 0);
    std::vector<std::size_t> queue;
    queue.reserve(h.size());
    const std::size_t start = idx(kHalfCells, kHalfCells);
    seen[start] = 1;
    queue.push_back(start);
    for (std::size_t qi = 0; qi < queue.size(); ++qi) {
        const std::size_t cur = queue[qi];
        const int ci = static_cast<int>(cur % kGridN);
        const int cj = static_cast<int>(cur / kGridN);
        const double px = x0 + (ci - kHalfCells) * kCellM;
        const double py = y0 + (cj - kHalfCells) * kCellM;
        if (std::hypot(px - lm.x, py - lm.y) <= lm.footprintRadiusM + kCellM) return true;
        for (int dj = -1; dj <= 1; ++dj) {
            for (int di = -1; di <= 1; ++di) {
                if (di == 0 && dj == 0) continue;
                const int ni = ci + di;
                const int nj = cj + dj;
                if (ni < 0 || nj < 0 || ni >= kGridN || nj >= kGridN) continue;
                const std::size_t nidx = idx(ni, nj);
                if (seen[nidx]) continue;
                const double len = kCellM * std::sqrt(static_cast<double>(di * di + dj * dj));
                if (std::fabs(h[nidx] - h[cur]) / len > maxTan) continue;
                seen[nidx] = 1;
                queue.push_back(nidx);
            }
        }
    }
    return false;
}

std::optional<Landmark> placeLandmark(std::uint32_t seed, int regionQ, int regionR, const World& world) {
    if (landmarkRandom(seed, regionQ, regionR, kSaltLandmarkPresent) >= kPresentP) return std::nullopt;

    const Region reg = world.region(regionQ, regionR);
    const double kindRoll = landmarkRandom(seed, regionQ, regionR, kSaltLandmarkKind);
    LandmarkKind kind = LandmarkKind::GiantTree;
    if (!chooseKind(reg.family, kindRoll, kind)) return std::nullopt;

    // A waterfall without a qualifying stream slope falls back to the family's dry primary kind.
    std::vector<LandmarkKind> candidates{kind};
    if (kind == LandmarkKind::Waterfall) {
        if (reg.family == Biome::RockyHighlands || reg.family == Biome::IcyHills) candidates.push_back(LandmarkKind::Spire);
        else if (reg.family != Biome::Marsh) candidates.push_back(LandmarkKind::GiantTree);
    }

    for (const LandmarkKind candidate : candidates) {
        for (int attempt = 0; attempt < kAttempts; ++attempt) {
            double x = 0, y = 0;
            bool ok = false;
            if (candidate == LandmarkKind::Waterfall) {
                ok = waterfallSite(seed, regionQ, regionR, world, reg, attempt, x, y);
            } else {
                ok = offsetSite(seed, regionQ, regionR, world, reg, attempt, x, y);
            }
            if (!ok) continue;
            if (world.nearestDiscovery(x, y, kDiscoveryClearM)) continue;
            const Landmark lm = makeLandmark(seed, regionQ, regionR, candidate, attempt, x, y, world);
            if (reachableOnFoot(world, reg.origin.x, reg.origin.y, lm)) return lm;
        }
    }
    return std::nullopt;
}

} // namespace wood::landmark
