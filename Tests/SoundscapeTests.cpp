#include "Generation/WoodSoundscape.h"
#include <algorithm>
#include <array>
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
 {
  // Stream emitters: 12 m lattice, chunk-owned, no duplicates across seams, deterministic.
  const wood::World world(wood::Settings{});
  std::vector<wood::SoundEmitter> all;
  bool inChunks=true, deterministic=true, gainsOk=true;
  for(int gx=-3;gx<=2;++gx) for(int gy=-2;gy<=1;++gy) {
   const auto e=wood::streamEmitters(world,gx,gy);
   const auto again=wood::streamEmitters(world,gx,gy);
   deterministic=deterministic&&e.size()==again.size();
   for(size_t i=0;i<e.size()&&i<again.size();++i) deterministic=deterministic&&e[i].x==again[i].x&&e[i].y==again[i].y&&e[i].gain==again[i].gain;
   for(const auto& s:e) {
    inChunks=inChunks&&s.x>=gx*128.0&&s.x<(gx+1)*128.0&&s.y>=gy*128.0&&s.y<(gy+1)*128.0;
    gainsOk=gainsOk&&std::isfinite(s.gain)&&s.gain>=0&&s.gain<=1;
    all.push_back(s);
   }
  }
  check(deterministic,"stream emitters deterministic");
  check(inChunks,"stream emitters lie inside their chunk");
  check(gainsOk,"stream emitter gains finite in [0,1]");
  bool lattice=true;
  for(const auto& s:all) lattice=lattice&&std::fabs(std::fmod(s.y,12.0))<1e-9&&std::fabs(s.x-world.streamX(s.y))<1e-9;
  check(lattice,"stream emitters on 12 m centreline lattice");
  std::sort(all.begin(),all.end(),[](const wood::SoundEmitter& a,const wood::SoundEmitter& b){ return a.y<b.y; });
  bool unique=true;
  for(size_t i=1;i<all.size();++i) unique=unique&&all[i].y!=all[i-1].y;
  check(unique,"no duplicate stream emitters at chunk seams");
  // y in [-256,256) holds lattice points k*12 for k=-21..21: 43 emitters, all x inside chunks -3..2.
  check(all.size()==43,"stream emitter count matches lattice over covered rows");
 }
 {
  using wood::weather::WeatherSample;
  using wood::weather::Precip;
  auto sample=[](Precip k,double in,double wet,double wind) { WeatherSample s; s.kind=k; s.intensity01=in; s.wetness01=wet; s.windMps=wind; return s; };
  check(std::fabs(wood::weatherLayers(sample(Precip::Rain,0.3,0,0)).rain-0.3)<1e-12,"rain gain equals intensity in Rain");
  check(wood::weatherLayers(sample(Precip::Clear,0.8,0,0)).rain==0,"no rain gain outside Rain");
  check(wood::weatherLayers(sample(Precip::Snow,0.8,0,0)).rain==0,"no rain gain in Snow");
  check(wood::weatherLayers(sample(Precip::Rain,0.8,0,0)).rain>wood::weatherLayers(sample(Precip::Rain,0.2,0,0)).rain,"rain gain rises with intensity");
  check(std::fabs(wood::weatherLayers(sample(Precip::Snow,1,0,0)).birdsong-0.5)<1e-12,"snow halves birdsong at full intensity");
  check(std::fabs(wood::weatherLayers(sample(Precip::Snow,1,0,0)).ambient-0.5)<1e-12,"snow halves ambient at full intensity");
  check(wood::weatherLayers(sample(Precip::Clear,1,0,0)).birdsong==1,"clear sky leaves birdsong ungained");
  check(wood::weatherLayers(sample(Precip::Rain,1,0,0)).birdsong<wood::weatherLayers(sample(Precip::Clear,1,0,0)).birdsong,"rain reduces birdsong");
  check(wood::weatherLayers(sample(Precip::Clear,0,0,0)).wind==0,"wind gain zero at 0 m/s");
  check(std::fabs(wood::weatherLayers(sample(Precip::Clear,0,0,6)).wind-0.5)<1e-12,"wind gain half at 6 m/s");
  check(wood::weatherLayers(sample(Precip::Clear,0,0,12)).wind==1,"wind gain one at 12 m/s");
  check(wood::weatherLayers(sample(Precip::Clear,0,0,30)).wind==1,"wind gain clamped above 12 m/s");
  check(std::fabs(wood::weatherLayers(sample(Precip::Clear,0,0.7,0)).drip-0.7)<1e-12,"canopy drip follows wetness after rain");
  check(wood::weatherLayers(sample(Precip::Rain,0,0.7,0)).drip==0,"no canopy drip during Rain");
  check(wood::weatherLayers(sample(Precip::Clear,0,0,0)).drip==0,"no canopy drip when dry");
 }
 {
  std::array<double,wood::kFamilyCount> forest{}, icy{}, none{};
  forest[static_cast<int>(wood::Biome::TemperateForest)]=1;
  icy[static_cast<int>(wood::Biome::IcyHills)]=1;
  check(wood::faunaCallGain(forest,0.5)>wood::faunaCallGain(forest,0.0),"fauna calls louder at noon than midnight");
  check(wood::faunaCallGain(forest,0.25)>wood::faunaCallGain(forest,0.5),"fauna calls peak at dawn above midday");
  check(wood::faunaCallGain(forest,0.8)>wood::faunaCallGain(forest,0.5),"fauna calls peak at dusk above midday");
  check(wood::faunaCallGain(forest,0.5)>wood::faunaCallGain(icy,0.5),"forest calls louder than icy highlands");
  check(std::fabs(wood::faunaCallGain(forest,1.5)-wood::faunaCallGain(forest,0.5))<1e-12,"day phase wraps");
  check(wood::faunaCallGain(none,0.5)==0,"no family weight gives no calls");
  bool bounded=true;
  for(double p=0;p<=1.0;p+=0.05) { const double g=wood::faunaCallGain(forest,p); bounded=bounded&&g>=0&&g<=1; }
  check(bounded,"fauna call gain within [0,1]");
 }
 if(failures) return 1;
 std::cout<<"soundscape tests passed\n";
 return 0;
}
