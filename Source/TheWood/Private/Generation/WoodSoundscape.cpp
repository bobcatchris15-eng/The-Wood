#include "Generation/WoodSoundscape.h"
#include <algorithm>
#include <cmath>

namespace wood {
namespace {
const double Pi=3.14159265358979323846;
double clamp01(double v) { return v<0?0:(v>1?1:v); }
double fin(double v,double fallback) { return std::isfinite(v)?v:fallback; }
}
Soundscape::Soundscape(uint32_t seed,double sampleRate) : rng(seed?seed:1u), rate(sampleRate>1000?sampleRate:48000) {}
double Soundscape::noise() {
 rng^=rng<<13; rng^=rng>>17; rng^=rng<<5;
 return static_cast<double>(rng)/2147483648.0-1.0;
}
void Soundscape::setParams(const SoundParams& p) {
 target.windStrength=clamp01(fin(p.windStrength,target.windStrength));
 target.forestWeight=clamp01(fin(p.forestWeight,target.forestWeight));
 target.streamProximity=clamp01(fin(p.streamProximity,target.streamProximity));
 target.seconds=std::max(0.,fin(p.seconds,target.seconds));
 if(!primed) { cur=target; primed=true; }
}
void Soundscape::render(float* out,int frames,int channels) {
 if(!out||frames<=0) return;
 channels=std::max(1,std::min(2,channels));
 const double smooth=1-std::exp(-1/(0.05*rate));
 const double dt=1/rate;
 for(int i=0;i<frames;++i) {
  cur.windStrength+=(target.windStrength-cur.windStrength)*smooth;
  cur.forestWeight+=(target.forestWeight-cur.forestWeight)*smooth;
  cur.streamProximity+=(target.streamProximity-cur.streamProximity)*smooth;
  cur.seconds+=(target.seconds-cur.seconds)*smooth;
  burbleT+=dt;
  // Slow gusts follow the shared observation clock, so accelerated time speeds them up.
  const double g=0.5+0.5*std::sin(cur.seconds*0.45)*std::sin(cur.seconds*0.17+1.3);
  const double gust=0.45+0.55*(0.5*g+0.5*(0.5+0.5*std::sin(cur.seconds*0.083)));
  const double windGain=0.35*std::pow(cur.windStrength,1.3)*gust;
  // Leafier forest: brighter, with more rustle; open ground: low whoosh.
  const double cutoff=260+900*cur.windStrength+1600*cur.forestWeight;
  const double a=1-std::exp(-2*Pi*cutoff/rate);
  const double rustle=0.3*cur.forestWeight*cur.windStrength;
  const double b1=1-std::exp(-2*Pi*1800/rate), b2=1-std::exp(-2*Pi*350/rate);
  const double burble=std::pow(clamp01(0.5+0.5*std::sin(burbleT*2*Pi*5.3)*std::sin(burbleT*2*Pi*8.9+0.7)+0.25*std::sin(burbleT*2*Pi*13.1)),1.5);
  const double streamGain=0.3*cur.streamProximity*(0.4+0.6*burble);
  for(int c=0;c<channels;++c) {
   Voice& v=voice[c];
   const double n=noise();
   v.w1+=(n-v.w1)*a; v.w2+=(v.w1-v.w2)*a;
   double wind=v.w2*3.0+rustle*(n-v.w1);
   v.s1+=(noise()-v.s1)*b1; v.s2+=(v.s1-v.s2)*b2;
   const double stream=(v.s1-v.s2)*3.0;
   double s=wind*windGain+stream*streamGain;
   s=std::tanh(s);
   if(!std::isfinite(s)) s=0;
   out[i*channels+c]=static_cast<float>(std::max(-1.0,std::min(1.0,s)));
  }
 }
}
}
