#include "Generation/WoodWeather.h"

#include <algorithm>
#include <cmath>
#include <cstdint>

namespace wood::weather {
namespace {

constexpr std::uint32_t kSaltWeatherWet = 0xCE0001U;
constexpr std::uint32_t kSaltWeatherDur = 0xCE0002U;
constexpr std::uint32_t kSaltWeatherOffset = 0xCE0003U;
constexpr std::uint32_t kSaltWeatherPeak = 0xCE0004U;
constexpr std::uint32_t kSaltWeatherWind = 0xCE0005U;

// One front slot per game hour; a front lives inside its slot.
constexpr double kSlotS = 3600.0;
// Front duration is kFrontMinS + [0, kFrontSpanS): 40 to 60 min.
constexpr double kFrontMinS = 2400.0;
constexpr double kFrontSpanS = 1200.0;
// Intensity and presence ramp at front edges.
constexpr double kRampS = 180.0;
// Wetness rises over kDecayS into a front and falls over kDecayS after it.
constexpr double kDecayS = 900.0;
constexpr double kCalmWindMps = 1.5;
constexpr double kSnowClimateT = 0.25;

// Identical to the project's random(seed,gx,gy,salt) pattern (file-local copy, as in WoodFauna.cpp).
std::uint32_t hash(std::uint32_t seed, int x, int y, std::uint32_t salt) {
    auto h = seed ^ (static_cast<std::uint32_t>(x) * 0x9e3779b9u) ^ (static_cast<std::uint32_t>(y) * 0x85ebca6bu) ^ salt;
    h ^= h >> 16; h *= 0x7feb352du; h ^= h >> 15; h *= 0x846ca68bu; return h ^ (h >> 16);
}
double random(std::uint32_t seed, int x, int y, std::uint32_t salt) {
    return hash(seed, x, y, salt) / 4294967296.0;
}

double clamp01(double v) {
    return std::min(1.0, std::max(0.0, v));
}

// Floor division by 4 so negative cells group into blocks the same way as positive ones.
int floorDiv4(int v) {
    return (v >= 0) ? v / 4 : -((-v + 3) / 4);
}

std::int64_t slotIndex(double t) {
    return static_cast<std::int64_t>(std::floor(t / kSlotS));
}

// Front-local roll: the front index is folded into the seed so each slot draws independent values.
double frontRand(std::uint32_t seed, int bx, int by, std::int64_t k, std::uint32_t salt) {
    const auto kk = static_cast<std::uint32_t>(k);
    return random(seed ^ (kk * 0x27d4eb2fu), bx, by, salt);
}

struct Front {
    bool wet = false;
    double start = 0.0;
    double end = 0.0;
    double peak = 0.0;
    double wind = 0.0;
};

Front frontFor(std::uint32_t seed, int bx, int by, std::int64_t k, double moisture) {
    Front f;
    const double pWet = 0.1 + 0.5 * moisture;
    f.wet = frontRand(seed, bx, by, k, kSaltWeatherWet) < pWet;
    const double dur = kFrontMinS + kFrontSpanS * frontRand(seed, bx, by, k, kSaltWeatherDur);
    const double offset = (kSlotS - dur) * frontRand(seed, bx, by, k, kSaltWeatherOffset);
    f.start = static_cast<double>(k) * kSlotS + offset;
    f.end = f.start + dur;
    f.peak = 0.4 + 0.6 * frontRand(seed, bx, by, k, kSaltWeatherPeak);
    f.wind = 3.0 + 12.0 * frontRand(seed, bx, by, k, kSaltWeatherWind);
    return f;
}

// 0 outside the front, ramps 0 -> 1 over kRampS at each edge, 1 in the body.
double presenceAt(const Front& f, double t) {
    if (t < f.start || t >= f.end) return 0.0;
    const double edge = std::min(t - f.start, f.end - t);
    return clamp01(edge / kRampS);
}

// Wetness level of one front: rises from start over kDecayS, holds, then falls over kDecayS after end.
double wetLevel(const Front& f, double t) {
    if (!f.wet || t < f.start) return 0.0;
    if (t < f.end) return f.peak * clamp01((t - f.start) / kDecayS);
    return f.peak * clamp01(1.0 - (t - f.end) / kDecayS);
}

} // namespace

WeatherSample sampleWeather(std::uint32_t seed, int gx, int gy, double worldClockS, double climateT, double moisture) {
    const double t = worldClockS;
    const double m = clamp01(moisture);
    const int bx = floorDiv4(gx);
    const int by = floorDiv4(gy);
    const std::int64_t k = slotIndex(t);

    // Only the current slot and the previous one can influence wetness (decay is 15 min, slots are 60 min).
    const Front cur = frontFor(seed, bx, by, k, m);
    const Front prev = frontFor(seed, bx, by, k - 1, m);
    const double presence = presenceAt(cur, t);

    WeatherSample s;
    if (cur.wet && presence > 0.0) {
        s.intensity01 = cur.peak * presence;
        s.kind = (climateT < kSnowClimateT) ? Precip::Snow : Precip::Rain;
    } else if (presence > 0.0) {
        s.kind = Precip::Overcast;
    }
    s.wetness01 = std::max(wetLevel(cur, t), wetLevel(prev, t));
    s.windMps = kCalmWindMps + (cur.wind - kCalmWindMps) * presence;
    return s;
}

} // namespace wood::weather
