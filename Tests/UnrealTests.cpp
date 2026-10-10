#include "Generation/WoodGeneration.h"
#include "Generation/WoodUnreal.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <map>
#include <vector>
int failures=0;
void check(bool ok,const char* text) { if(!ok) { ++failures; if(failures<25) std::cerr<<"FAIL: "<<text<<'\n'; } }

namespace {
// Walks 3 km through (x0,y0) along +x at 1 m steps; returns max EV and Kelvin change per 10 m at two times.
void lightingWalk(const wood::World& world,double x0,double y0,double& maxEV,double& maxKelvin,int& active,int& ordinary) {
 const int samples=3001;
 active=0; ordinary=0; maxEV=0; maxKelvin=0;
 for(int i=0;i<samples;++i) { if(world.overlayAt(x0-1500+i,y0).active) ++active; else ++ordinary; }
 for(const double seconds:{200.0,1650.0}) {
  std::vector<double> ev(samples),kelvin(samples);
  for(int i=0;i<samples;++i) {
   const auto l=world.lighting(x0-1500+i,y0,seconds);
   ev[i]=std::log2(l.brightness); kelvin[i]=l.kelvin;
  }
  for(int i=0;i+10<samples;++i) {
   maxEV=std::max(maxEV,std::abs(ev[i+10]-ev[i]));
   maxKelvin=std::max(maxKelvin,std::abs(kelvin[i+10]-kelvin[i]));
  }
 }
}
}

int main() {
 using namespace wood;
 using unreal::Overlay;
 World world({42,128,64});

 // Overlay pick: deterministic, never None, and the region records the same value.
 std::map<int,int> counts;
 int unrealSeen=0, ordinarySeen=0, mismatch=0, nonDeterministic=0, ordinaryNotNone=0;
 for(int q=-300;q<=300&&unrealSeen<2000;++q) for(int r=-300;r<=300&&unrealSeen<2000;++r) {
  const Region reg=world.region(q,r);
  if(!reg.unreal) {
   if(reg.overlay!=Overlay::None) ++ordinaryNotNone;
   ++ordinarySeen;
   continue;
  }
  ++unrealSeen;
  const Overlay picked=unreal::pick(reg.identity,reg.family);
  if(picked!=reg.overlay) ++mismatch;
  if(unreal::pick(reg.identity,reg.family)!=picked) ++nonDeterministic;
  if(picked==Overlay::None) ++mismatch;
  ++counts[static_cast<int>(picked)];
 }
 std::cout<<"Overlay distribution over "<<unrealSeen<<" unreal regions:";
 for(int k=0;k<=5;++k) std::cout<<' '<<counts[k];
 std::cout<<'\n';
 check(unrealSeen==2000,"found 2000 unreal regions in the search window");
 check(mismatch==0,"region overlay matches unreal::pick and is never None when unreal");
 check(nonDeterministic==0,"overlay pick is deterministic");
 check(ordinaryNotNone==0,"ordinary regions carry Overlay::None");
 check(counts[0]==0,"no unreal region picks None");
 for(int k=1;k<=5;++k) check(counts[k]>=200,"every overlay appears in at least 200 of 2000 unreal regions");

 // Overlay parameter table: None is identity; ExcessivelyFungal is the large-scale core.
 const auto none=unreal::params(Overlay::None);
 check(none.featureScale==1.0&&none.densityScale==1.0&&none.lightBrightness==1.0&&none.lightKelvinShift==0.0,"None overlay is identity");
 check(unreal::params(Overlay::ExcessivelyFungal).featureScale>=1.8,"fungal overlay scales features at least 1.8x");
 check(none.fungusScale==1.0,"None overlay leaves fungi unscaled");
 check(unreal::params(Overlay::ExcessivelyFungal).fungusScale==3.0,"fungal overlay boosts fungus ground cover x3");
 for(const Overlay o:{Overlay::LuminousMoss,Overlay::UnnaturallyDark,Overlay::PaleEnchanted,Overlay::GlassyMineral}) check(unreal::params(o).fungusScale==1.0,"only the fungal overlay boosts fungi");

 // Feature scale inside a large-scale core versus ordinary ground.
 bool foundCore=false; double peakScale=0;
 for(int q=-300;q<=300&&!foundCore;++q) for(int r=-300;r<=300&&!foundCore;++r) {
  const Region reg=world.region(q,r);
  if(!reg.unreal||reg.overlay!=Overlay::ExcessivelyFungal) continue;
  foundCore=true;
  for(double dy=-400;dy<=400;dy+=25) for(double dx=-400;dx<=400;dx+=25) {
   peakScale=std::max(peakScale,world.overlayAt(reg.origin.x+dx,reg.origin.y+dy).featureScale);
  }
 }
 check(foundCore,"found an excessively fungal unreal region");
 check(peakScale>=1.8,"feature scale multiplier inside fungal core is at least 1.8x ordinary");
 std::cout<<"Fungal core peak feature scale multiplier "<<peakScale<<'\n';

 // Ordinary ground: neutral and inactive wherever no unreal cell has weight.
 bool checkedOrdinary=false;
 for(int q=-300;q<=300&&!checkedOrdinary;++q) for(int r=-300;r<=300&&!checkedOrdinary;++r) {
  const Region reg=world.region(q,r);
  if(reg.unreal) continue;
  const auto f=world.overlayAt(reg.origin.x,reg.origin.y);
  if(f.active) continue;
  checkedOrdinary=true;
  check(f.featureScale==1.0&&f.densityScale==1.0&&f.lightBrightness==1.0&&f.lightKelvinShift==0.0,"inactive overlay field is neutral");
 }
 check(checkedOrdinary,"found an ordinary region with no unreal influence");

 // Lighting continuity across an unreal boundary: walk through an unreal region and out past its edge.
 bool crossed=false;
 for(int q=-300;q<=300&&!crossed;++q) for(int r=-300;r<=300&&!crossed;++r) {
  const Region reg=world.region(q,r);
  if(!reg.unreal) continue;
  double maxEV=0,maxKelvin=0; int active=0,ordinary=0;
  lightingWalk(world,reg.origin.x,reg.origin.y,maxEV,maxKelvin,active,ordinary);
  if(active==0||ordinary==0) continue;
  crossed=true;
  std::cout<<"Unreal lighting walk: active "<<active<<", ordinary "<<ordinary<<", max dEV/10m "<<maxEV<<", max dKelvin/10m "<<maxKelvin<<'\n';
  check(maxEV<=0.25,"unreal boundary changes exposure at most 0.25 EV per 10 m walking");
  check(maxKelvin<=150,"unreal boundary changes colour temperature at most 150 K per 10 m walking");
 }
 check(crossed,"found a 3 km walk that crosses an unreal boundary");

 if(!failures) std::cout<<"PASS: unreal overlay pick, distribution, feature scale, lighting continuity\n";
 return failures?1:0;
}
