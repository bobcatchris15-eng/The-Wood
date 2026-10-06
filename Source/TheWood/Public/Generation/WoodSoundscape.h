#pragma once
#include <cstdint>

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
}
