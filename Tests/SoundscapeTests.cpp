#include "Generation/WoodSoundscape.h"
#include <cmath>
#include <iostream>
#include <vector>

namespace {
int failures=0;
void check(bool ok,const char* message) { if(!ok) { ++failures; std::cerr<<"FAIL: "<<message<<'\n'; } }
std::vector<float> run(wood::SoundParams p,int frames,int channels=2,uint32_t seed=7) {
 wood::Soundscape s(seed); s.setParams(p);
 std::vector<float> out(static_cast<size_t>(frames)*channels); s.render(out.data(),frames,channels); return out;
}
double rms(const std::vector<float>& v) { double a=0; for(float x:v) a+=double(x)*x; return std::sqrt(a/v.size()); }
}
int main() {
 const wood::SoundParams mid{0.5,0.5,0.5,100};
 const auto base=run(mid,48000);
 bool ok=true; for(float x:base) if(!std::isfinite(x)||x<-1||x>1) ok=false;
 check(ok,"samples finite and within [-1,1]");
 check(base==run(mid,48000),"deterministic for same seed");
 check(base!=run(mid,48000,2,8),"seed changes output");
 check(rms(run({0,0.5,0,100},24000))<1e-6,"silent without wind or water");
 check(rms(run({0.2,0.5,0,100},48000))<rms(run({0.9,0.5,0,100},48000)),"rms rises with wind");
 check(rms(run({0,0.5,0.2,100},48000))<rms(run({0,0.5,0.9,100},48000)),"rms rises with stream proximity");
 check(rms(run({0.6,0.5,0,100},48000))>0.001,"wind audible");
 {
  wood::Soundscape a(7),b(7); a.setParams(mid); b.setParams(mid);
  std::vector<float> x(2*10007),y(2*10007);
  a.render(x.data(),10007,2);
  int done=0; for(int n:{1,63,500,3000,17,6426}) { b.render(y.data()+2*done,n,2); done+=n; }
  check(done==10007&&x==y,"block-size independent");
 }
 {
  auto jump=[](const std::vector<float>& v,float prev) { float w=0; for(size_t i=0;i<v.size();i+=2) { w=std::fmax(w,std::fabs(v[i]-prev)); prev=v[i]; } return w; };
  wood::Soundscape s(3); s.setParams({0,0.2,0,0});
  std::vector<float> a(2*4800),b(2*48000); s.render(a.data(),4800,2);
  s.setParams({1,1,1,0}); s.render(b.data(),48000,2);
  const auto loud=run({1,1,1,0},48000);
  check(jump(b,a[a.size()-2])<=jump(loud,0)*1.05f+0.01f,"param step adds no jump beyond loud steady noise");
 }
 if(failures) return 1;
 std::cout<<"soundscape tests passed\n";
 return 0;
}
