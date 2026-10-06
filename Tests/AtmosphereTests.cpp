#include "Generation/WoodAtmosphere.h"
#include <cmath>
#include <iostream>
#include <limits>
#include <stdexcept>

namespace {
int failures=0;
void check(bool ok,const char* message) { if(!ok) { ++failures; std::cerr<<"FAIL: "<<message<<'\n'; } }
double distance(wood::Atmosphere a,wood::Atmosphere b) {
 return std::abs(a.fogDensity-b.fogDensity)*40+std::abs(a.cloudCover-b.cloudCover)+std::abs(a.windStrength-b.windStrength);
}
}
int main() {
 using wood::atmosphere;
 for(double forest:{0.,0.25,0.5,0.75,1.}) for(int t=0;t<=3600;t+=7) {
  const auto a=atmosphere(forest,-213.5,117.8,t);
  check(a.fogDensity>=0.002&&a.fogDensity<=0.025,"mist remains usable for Unreal fog");
  check(a.cloudCover>=0&&a.cloudCover<=1&&a.windStrength>=0&&a.windStrength<=1,"clouds and wind remain bounded");
  check(distance(a,atmosphere(forest,-213.5,117.8,t))==0,"sampling is reproducible without tick history");
  check(distance(a,atmosphere(forest,-213.499,117.801,t))<0.0001,"weather has no spatial seams");
  check(distance(a,atmosphere(forest,-213.5,117.8,t+1./60))<0.002,"weather never jumps between frames");
 }
 const auto start=atmosphere(0.7,0,0,0);
 check(distance(start,atmosphere(0.7,0,0,400))>0.15,"accelerated seated observation reveals weather changes");
 check(distance(start,atmosphere(0.7,0,0,400))>distance(start,atmosphere(0.7,0,0,20))*2,"accelerated time makes slow weather more apparent");
 for(int t=0;t<1000;t+=13) {
  check(atmosphere(1,20,30,t).fogDensity>atmosphere(0,20,30,t).fogDensity,"forest carries more mist than highland");
  check(distance(atmosphere(0.49999,20,30,t),atmosphere(0.50001,20,30,t))<0.0001,"region blending is continuous");
 }
 const double nan=std::numeric_limits<double>::quiet_NaN();
 const double inf=std::numeric_limits<double>::infinity();
 for(const auto input : {wood::Atmosphere{nan,0,0},wood::Atmosphere{0.5,inf,0},wood::Atmosphere{0.5,0,nan},wood::Atmosphere{-0.1,0,0},wood::Atmosphere{1.1,0,0}}) {
  bool rejected=false;
  try { atmosphere(input.fogDensity,input.cloudCover,input.windStrength,0); } catch(const std::invalid_argument&) { rejected=true; }
  check(rejected,"invalid weather inputs are rejected");
 }
 bool rejected=false;
 try { atmosphere(0.5,0,0,inf); } catch(const std::invalid_argument&) { rejected=true; }
 check(rejected,"nonfinite time is rejected");
 if(!failures) std::cout<<"Atmosphere tests passed\n";
 return failures?1:0;
}
