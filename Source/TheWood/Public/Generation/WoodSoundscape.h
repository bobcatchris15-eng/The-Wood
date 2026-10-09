#pragma once
#include <array>
#include <cstdint>
#include <vector>
#include "Generation/WoodGeneration.h"
#include "Generation/WoodWeather.h"

namespace wood {
struct SoundParams { double windStrength=0, forestWeight=0, streamProximity=0, seconds=0; };
// Deterministic synth: wind (filtered noise, slow gusts) + stream (band-limited burble).
// Params are smoothed per-sample; output is always finite and within [-1,1].
class Soundscape {
public:
 explicit Soundscape(uint32_t seed=1, double sampleRate=48000);
 // First call snaps to the target; later calls glide. Non-finite inputs are ignored; values are clamped.
 void setParams(const SoundParams& target);
 // Interleaved; channels is 1 or 2 (others clamp). Never throws or allocates.
 void render(float* out, int frames, int channels);
private:
 struct Voice { double w1=0, w2=0, s1=0, s2=0, s3=0; };
 uint32_t rng;
 double rate;
 SoundParams target, cur;
 double gustT=0, burbleT=0;
 bool primed=false;
 Voice voice[2];
 double noise();
};

// Spatial stream emitter in metres. gain in [0,1] from local depth and slope.
struct SoundEmitter { double x=0, y=0, gain=0; };
// Emitters on a global 12 m lattice along the stream centreline (y = k*12), kept when the point lies in chunk (gx,gy).
// Chunk ownership is half-open, so each emitter belongs to exactly one chunk. Deterministic.
std::vector<SoundEmitter> streamEmitters(const wood::World& world, int gx, int gy);

// Per-layer gains in [0,1] from one weather sample. birdsong is a multiplier for fauna calls.
struct LayerGains { double rain=0, wind=0, drip=0, birdsong=1, ambient=1; };
// rain: Rain only, = intensity. wind: windMps/12 clamped. drip: wetness01 outside precipitation.
// Snow lowers birdsong and ambient up to 50%; Rain lowers birdsong up to 60%.
LayerGains weatherLayers(const weather::WeatherSample& sample);

// Fauna call gain in [0,1] from biome family weights (Biome enum order, sum to one) and day phase
// (0 = midnight, 0.5 = noon; wrapped). Peaks at dawn and dusk, quieter at midday and night.
double faunaCallGain(const std::array<double,kFamilyCount>& familyWeights, double dayPhase01);
}
