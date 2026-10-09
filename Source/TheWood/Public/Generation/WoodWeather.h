#pragma once

#include <cstdint>

// Engine-free precipitation core. Seconds, metres per second, unit-interval scalars. No Unreal headers.
namespace wood::weather {

enum class Precip : std::uint8_t { Clear, Overcast, Rain, Snow };

struct WeatherSample {
    Precip kind = Precip::Clear;
    double intensity01 = 0.0;
    double wetness01 = 0.0;
    double windMps = 0.0;
};

// Pure in all arguments. worldClockS: game seconds. climateT < 0.25 gives snow, else rain.
// moisture in [0,1] sets precip chance per front (0.1 at 0, 0.6 at 1).
// Fronts are keyed by (seed, gx/4, gy/4, frontIndex), so cells in the same 4x4 block share weather.
WeatherSample sampleWeather(std::uint32_t seed, int gx, int gy, double worldClockS, double climateT, double moisture);

} // namespace wood::weather
