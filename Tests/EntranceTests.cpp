#include "Generation/WoodGeneration.h"
#include "Generation/WoodEntrance.h"
#include <algorithm>
#include <cstdint>
#include <iostream>
#include <set>
#include <tuple>
#include <vector>

namespace {
int failures=0;
void check(bool ok,const char* message) { if(!ok) { ++failures; std::cerr<<"FAIL: "<<message<<'\n'; } }
using wood::Feature;
using wood::Kind;
using wood::Settings;
using wood::Vec3;
using wood::World;
using Key=std::tuple<int,double,double,int>;
using Placed=std::vector<std::tuple<int,double,double,double,int>>;
const std::uint32_t Seeds[]={0u,42u,98765u};
const int ChunkXs[]={-1,0};
const int ChunkYs[]={-5,-4,-3,-2};

Key keyOf(const Feature& f) { return Key{static_cast<int>(f.kind),f.position.x,f.position.y,f.propId}; }
std::set<Key> fixedKeys() {
 std::set<Key> keys;
 for(const auto& f:wood::entrance::fixedFeatures()) keys.insert(keyOf(f));
 return keys;
}
// Fixed entrance features as placed by one world's zone chunks, sorted for comparison.
Placed placed(const World& world) {
 const auto keys=fixedKeys();
 Placed out;
 for(const int cx:ChunkXs) for(const int cy:ChunkYs) {
  const auto chunk=world.generate(cx,cy);
  for(const auto& f:chunk.features) {
   if(keys.count(keyOf(f))) out.emplace_back(static_cast<int>(f.kind),f.position.x,f.position.y,f.scale,f.propId);
  }
 }
 std::sort(out.begin(),out.end());
 return out;
}
bool sameVec(const Vec3& a,const Vec3& b) { return a.x==b.x&&a.y==b.y&&a.z==b.z; }
bool sameChunk(const wood::Chunk& a,const wood::Chunk& b) {
 if(a.x!=b.x||a.y!=b.y||a.cells!=b.cells) return false;
 if(a.vertices.size()!=b.vertices.size()||a.triangles!=b.triangles||a.features.size()!=b.features.size()) return false;
 for(std::size_t i=0;i<a.vertices.size();++i) if(!sameVec(a.vertices[i],b.vertices[i])) return false;
 for(std::size_t i=0;i<a.features.size();++i) {
  const auto& f=a.features[i]; const auto& g=b.features[i];
  if(f.kind!=g.kind||!sameVec(f.position,g.position)||f.yaw!=g.yaw||f.scale!=g.scale||f.young!=g.young||f.prairie!=g.prairie||f.propId!=g.propId) return false;
 }
 return true;
}

void testFixedAcrossSeeds() {
 const std::size_t expected=wood::entrance::fixedFeatures().size();
 Placed first;
 for(const std::uint32_t seed:Seeds) {
  World world(Settings{seed});
  world.setEntered(false);
  const auto p=placed(world);
  check(p.size()==expected,"every fixed entrance feature is placed in zone chunks");
  if(seed==Seeds[0]) first=p;
  else check(p==first,"fixed entrance features identical across World seeds");
 }
}

void testLotFlat() {
 for(const std::uint32_t seed:Seeds) {
  World world(Settings{seed});
  world.setEntered(false);
  double lo=1e9, hi=-1e9;
  for(double y=-572;y<=-548;y+=1) for(double x=-20;x<=20;x+=1) {
   const double h=world.terrainHeight(x,y);
   lo=std::min(lo,h); hi=std::max(hi,h);
  }
  check(hi-lo<0.05,"lot pad is flat inside 0.05 m");
 }
}

void testPathMargin() {
 const double clearance=wood::entrance::PathHalfWidth+wood::entrance::PathMargin;
 for(const auto& f:wood::entrance::fixedFeatures()) {
  if(f.kind==Kind::Tree) check(wood::entrance::pathDistance(f.position.x,f.position.y)>=clearance,"fixed trees keep path margin");
 }
 for(const std::uint32_t seed:Seeds) {
  World world(Settings{seed});
  world.setEntered(false);
  for(const int cx:ChunkXs) for(const int cy:ChunkYs) {
   for(const auto& f:world.generate(cx,cy).features) {
    if(f.kind==Kind::Tree) check(wood::entrance::pathDistance(f.position.x,f.position.y)>=clearance,"no tree inside path margin");
   }
  }
 }
}

void testLineOfSight() {
 check(wood::entrance::lineOfSightBlocked(Vec3{0,-180,1.7},Vec3{0,-560,0}),"passage screen hides lot from y=-180");
 check(!wood::entrance::lineOfSightBlocked(Vec3{0,-500,1.7},Vec3{0,-560,0}),"lot visible from y=-500 on path");
}

void testOutsideZoneIdentical() {
 World entered(Settings{42});
 World closed(Settings{42});
 closed.setEntered(false);
 const int outside[][2]={{5,0},{-6,3}};
 for(const auto& c:outside) check(sameChunk(entered.generate(c[0],c[1]),closed.generate(c[0],c[1])),"chunk outside zone identical entered vs not entered");
}

void testEnteredIsWilderness() {
 World defaulted(Settings{42});
 World entered(Settings{42});
 entered.setEntered(true);
 check(entered.entered(),"setEntered(true) reports entered");
 check(sameChunk(defaulted.generate(0,-4),entered.generate(0,-4)),"entered chunk identical to default world");
 check(placed(entered).empty(),"entered world has no entrance features");
 const auto a=defaulted.lighting(0,-560,0), b=entered.lighting(0,-560,0);
 check(a.brightness==b.brightness&&a.kelvin==b.kelvin,"entered lighting in zone is wilderness lighting");
}

// Stream is dry on the lot pad and path while not entered; entered worlds keep their stream unchanged.
void testStreamDryInZone() {
 const std::uint32_t streamSeeds[]={0u,42u,98765u,12345u};
 for(const std::uint32_t seed:streamSeeds) {
  World closed(Settings{seed});
  closed.setEntered(false);
  World entered(Settings{seed});
  entered.setEntered(true);
  const World wilderness(Settings{seed});
  for(int gx=-30;gx<=30;++gx) for(int gy=-580;gy<=-220;++gy) {
   const double x=gx, y=gy;
   const bool onLot=wood::entrance::lotDistance(x,y)<=0;
   const bool onPath=wood::entrance::pathDistance(x,y)<=wood::entrance::PathHalfWidth;
   if(onLot||onPath) check(closed.streamDepth(x,y)==0,"stream dry on lot pad and path when not entered");
   check(entered.streamDepth(x,y)==wilderness.streamDepth(x,y),"entered stream unchanged");
  }
 }
}

void testNotEnteredLightingAndTrees() {
 World closed(Settings{42});
 closed.setEntered(false);
 const auto light=closed.lighting(0,-560,0);
 check(light.brightness>=1.0&&light.kelvin==5600,"zone lighting is bright and 5600 K when not entered");
 const auto keys=fixedKeys();
 for(const int cx:ChunkXs) for(const int cy:ChunkYs) {
  for(const auto& f:closed.generate(cx,cy).features) {
   if(f.kind==Kind::Tree&&wood::entrance::inZone(f.position.x,f.position.y)) check(keys.count(keyOf(f))>0,"no habitat trees inside zone when not entered");
  }
 }
}
}

int main() {
 testFixedAcrossSeeds();
 testLotFlat();
 testPathMargin();
 testLineOfSight();
 testOutsideZoneIdentical();
 testEnteredIsWilderness();
 testNotEnteredLightingAndTrees();
 testStreamDryInZone();
 if(failures==0) std::cout<<"Entrance tests passed\n";
 else std::cout<<failures<<" entrance test failures\n";
 return failures==0?0:1;
}
