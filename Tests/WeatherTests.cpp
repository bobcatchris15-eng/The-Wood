#include <cmath>
#include <cstdint>
#include <iostream>

#include "Generation/WoodWeather.h"

using namespace wood::weather;

static int gTestCount = 0;
static int gFailures = 0;

static void check(bool cond, const char* expr, const char* file, int line) {
    ++gTestCount;
    if (!cond) {
        std::cerr << "CHECK FAILED: " << expr << " at " << file << ":" << line << "\n";
        ++gFailures;
    }
}

#define EXPECT_TRUE(expr) check(static_cast<bool>(expr), #expr, __FILE__, __LINE__)
#define EXPECT_EQ(a, b) check((a) == (b), #a " == " #b, __FILE__, __LINE__)

static const double kDayS = 86400.0;

static bool sameSample(const WeatherSample& a, const WeatherSample& b) {
    return a.kind == b.kind && a.intensity01 == b.intensity01 && a.wetness01 == b.wetness01 && a.windMps == b.windMps;
}

static void test_determinism() {
    std::cout << "[TEST] test_determinism...\n";
    for (int i = 0; i < 50; ++i) {
        const double t = static_cast<double>(i) * 977.0;
        EXPECT_TRUE(sameSample(sampleWeather(7u, 2, -3, t, 0.4, 0.6), sampleWeather(7u, 2, -3, t, 0.4, 0.6)));
    }
}

static void test_continuity() {
    std::cout << "[TEST] test_continuity...\n";
    const int cells[][2] = {{0, 0}, {-5, 7}};
    for (const auto& c : cells) {
        WeatherSample prev = sampleWeather(42u, c[0], c[1], 0.0, 0.5, 0.9);
        for (int i = 1; i <= static_cast<int>(kDayS); ++i) {
            const WeatherSample cur = sampleWeather(42u, c[0], c[1], static_cast<double>(i), 0.5, 0.9);
            EXPECT_TRUE(std::fabs(cur.intensity01 - prev.intensity01) < 0.05);
            EXPECT_TRUE(std::fabs(cur.wetness01 - prev.wetness01) < 0.05);
            EXPECT_TRUE(cur.intensity01 >= 0.0 && cur.intensity01 <= 1.0);
            EXPECT_TRUE(cur.wetness01 >= 0.0 && cur.wetness01 <= 1.0);
            prev = cur;
        }
    }
}

static void test_neighbour_coherence() {
    std::cout << "[TEST] test_neighbour_coherence...\n";
    // Cells in the same 4x4 block share fronts, so every sample must match the block's reference cell.
    const int refs[][2] = {{0, 0}, {-4, -4}};
    const int offsets[][2] = {{0, 0}, {1, 2}, {3, 0}, {2, 3}, {3, 3}};
    for (const auto& r : refs) {
        for (int i = 0; i < static_cast<int>(kDayS); i += 60) {
            const double t = static_cast<double>(i);
            const WeatherSample ref = sampleWeather(11u, r[0], r[1], t, 0.5, 0.8);
            for (const auto& o : offsets) {
                EXPECT_TRUE(sameSample(ref, sampleWeather(11u, r[0] + o[0], r[1] + o[1], t, 0.5, 0.8)));
            }
        }
    }
    // Different blocks must not be locked together.
    int diffs = 0;
    for (int i = 0; i < static_cast<int>(kDayS); i += 60) {
        const double t = static_cast<double>(i);
        if (!sameSample(sampleWeather(11u, 0, 0, t, 0.5, 0.8), sampleWeather(11u, 4, 0, t, 0.5, 0.8))) ++diffs;
    }
    EXPECT_TRUE(diffs > 0);
}

static void test_rain_snow_by_climate() {
    std::cout << "[TEST] test_rain_snow_by_climate...\n";
    int cold_precip = 0, cold_rain = 0;
    int warm_precip = 0, warm_snow = 0;
    for (int i = 0; i < static_cast<int>(kDayS); i += 60) {
        const double t = static_cast<double>(i);
        const WeatherSample c = sampleWeather(5u, 0, 0, t, 0.1, 1.0);
        if (c.kind == Precip::Snow || c.kind == Precip::Rain) ++cold_precip;
        if (c.kind == Precip::Rain) ++cold_rain;
        const WeatherSample w = sampleWeather(5u, 0, 0, t, 0.5, 1.0);
        if (w.kind == Precip::Snow || w.kind == Precip::Rain) ++warm_precip;
        if (w.kind == Precip::Snow) ++warm_snow;
    }
    EXPECT_TRUE(cold_precip > 0);
    EXPECT_EQ(cold_rain, 0);
    EXPECT_TRUE(warm_precip > 0);
    EXPECT_EQ(warm_snow, 0);
}

static void test_clock_equivalence() {
    std::cout << "[TEST] test_clock_equivalence...\n";
    // Coarse clock: 1.0 real s at 20x = 20 game s per step. Fine clock: 0.25 real s at 20x = 5 game s per step.
    // Both must agree wherever they land on the same game time.
    double coarseT = 0.0;
    double fineT = 0.0;
    for (int i = 0; i < 4320; ++i) {
        coarseT += 1.0 * 20.0;
        fineT += 4.0 * (0.25 * 20.0);
        EXPECT_TRUE(sameSample(sampleWeather(21u, 3, 9, coarseT, 0.5, 0.7),
                               sampleWeather(21u, 3, 9, fineT, 0.5, 0.7)));
    }
}

static void test_precip_fraction_by_moisture() {
    std::cout << "[TEST] test_precip_fraction_by_moisture...\n";
    // Pooled over 20 seeds to smooth per-seed front luck.
    long dryPrecip = 0, dryTotal = 0;
    long wetPrecip = 0, wetTotal = 0;
    for (std::uint32_t seed = 1; seed <= 20; ++seed) {
        for (int i = 0; i < static_cast<int>(kDayS); i += 60) {
            const double t = static_cast<double>(i);
            const WeatherSample d = sampleWeather(seed, 0, 0, t, 0.5, 0.0);
            ++dryTotal;
            if (d.kind == Precip::Rain || d.kind == Precip::Snow) ++dryPrecip;
            const WeatherSample w = sampleWeather(seed, 0, 0, t, 0.5, 1.0);
            ++wetTotal;
            if (w.kind == Precip::Rain || w.kind == Precip::Snow) ++wetPrecip;
        }
    }
    const double dryFrac = static_cast<double>(dryPrecip) / static_cast<double>(dryTotal);
    const double wetFrac = static_cast<double>(wetPrecip) / static_cast<double>(wetTotal);
    std::cout << "  dry precip fraction " << dryFrac << ", wet precip fraction " << wetFrac << "\n";
    EXPECT_TRUE(dryFrac < 0.2);
    EXPECT_TRUE(wetFrac > 0.4);
}

int main() {
    test_determinism();
    test_continuity();
    test_neighbour_coherence();
    test_rain_snow_by_climate();
    test_clock_equivalence();
    test_precip_fraction_by_moisture();

    if (gFailures == 0) {
        std::cout << "PASS: " << gTestCount << " weather checks\n";
        return 0;
    }
    std::cout << "FAIL: " << gFailures << " of " << gTestCount << " weather checks\n";
    return 1;
}
