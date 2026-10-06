#pragma once

namespace wood {
struct Atmosphere { double fogDensity=0, cloudCover=0, windStrength=0; };
// Coordinates are metres, seconds use the shared observation clock.
// Forest weight must be in [0,1]; all inputs must be finite.
Atmosphere atmosphere(double forestWeight, double x, double y, double seconds);
}
