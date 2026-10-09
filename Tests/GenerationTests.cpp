#include "Generation/WoodGeneration.h"
#include "Generation/WoodDiscovery.h"
#include "Generation/WoodHex.h"
#include <cmath>
#include <set>
#include <utility>
#include <cstdint>
#include <cstdio>
#include <cstring>
#include <algorithm>
#include <iostream>
#include <stdexcept>
#include <string>
#include <array>
#include <random>
#include <vector>
int failures=0;
void check(bool ok,const char* message) { if(!ok) { ++failures; std::cerr<<"FAIL: "<<message<<'\n'; } }
bool near(double a,double b) { return std::abs(a-b)<1e-9; }
// 64-bit FNV-1a over raw bit patterns; any output change alters the fingerprint.
struct Fnv1a {
 std::uint64_t h=1469598103934665603ULL;
 void byte(unsigned char b) { h^=b; h*=1099511628211ULL; }
 void u64(std::uint64_t v) { for(int i=0;i<8;++i) byte(static_cast<unsigned char>(v>>(8*i))); }
 void real(double d) { std::uint64_t u; std::memcpy(&u,&d,sizeof u); u64(u); }
 void integer(std::int64_t v) { u64(static_cast<std::uint64_t>(v)); }
};
void hashSurface(Fnv1a& f,const wood::Surface& s) {
 f.real(s.height); f.real(s.forest); f.real(s.moisture); f.real(s.slope); f.real(s.waterHeight); f.real(s.depth);
 for(double b:s.biome) f.real(b);
 f.real(s.temperature); f.real(s.exposure); f.real(s.shelter); f.real(s.roughness);
}
std::uint64_t fingerprintChunk(const wood::World& world,const wood::Chunk& c) {
 Fnv1a f;
 f.integer(c.x); f.integer(c.y); f.integer(c.cells);
 f.integer(static_cast<std::int64_t>(c.vertices.size()));
 for(const auto& v:c.vertices) { f.real(v.x); f.real(v.y); f.real(v.z); hashSurface(f,world.sample(v.x,v.y)); }
 f.integer(static_cast<std::int64_t>(c.triangles.size()));
 for(auto t:c.triangles) f.u64(t);
 f.integer(static_cast<std::int64_t>(c.features.size()));
 for(const auto& p:c.features) {
  f.integer(static_cast<std::int64_t>(p.kind)); f.real(p.position.x); f.real(p.position.y); f.real(p.position.z);
  f.real(p.yaw); f.real(p.scale); f.u64(p.young?1:0); f.u64(p.prairie?1:0);
  // Kit fields hashed only for Kit features, so chunks without kit pieces keep their fingerprints.
  if(p.kind==wood::Kind::Kit) { f.integer(p.kitId); f.real(p.pitch); f.real(p.roll); }
 }
 return f.h;
}
int main() {
 using namespace wood;
 World world({42,128,32});
 auto a=world.generate(0,0), b=world.generate(1,0);
 check(a.vertices.size()==1089,"chunk includes shared edge vertices");
 check(a.triangles.size()==6144,"chunk has complete indexed surface");
 if(a.vertices.size()==1089 && b.vertices.size()==1089) {
  for(int row=0;row<=32;++row) {
   const auto& left=a.vertices[row*33+32]; const auto& right=b.vertices[row*33];
   check(near(left.x,right.x)&&near(left.y,right.y)&&near(left.z,right.z),"neighbor seams agree");
  }
 }
 auto bFirst=world.generate(1,0), aLast=world.generate(0,0);
 check(aLast.features.size()==a.features.size()&&bFirst.features.size()==b.features.size(),"generation order preserves feature counts");
 if(aLast.features.size()==a.features.size()) for(std::size_t i=0;i<a.features.size();++i)
  check(near(a.features[i].position.x,aLast.features[i].position.x)&&near(a.features[i].position.z,aLast.features[i].position.z),"placement repeats for same seed");
 check(!a.features.empty(),"habitats produce vegetation and rocks");
 for(const auto& f:a.features) {
  const auto s=world.sample(f.position.x,f.position.y);
  check(near(f.position.z,world.terrainHeight(f.position.x,f.position.y)),"features are grounded");
  if(f.kind!=Kind::Rock) check(s.depth<=0 && s.slope<0.7,"plants avoid water and steep terrain");
 }
 for(int y=-256;y<256;y+=4) {
  auto s=world.sample(world.streamX(y),y);
  check(s.depth>0&&s.depth<0.65,"continuous stream is shallow enough to wade");
  auto downstream=world.sample(world.streamX(y+4),y+4);
  check(downstream.waterHeight<s.waterHeight,"water flows downhill");
 }
 const auto forestRegion=world.region(0,0),highlandRegion=world.region(1,1);
 check(world.sample(forestRegion.origin.x,forestRegion.origin.y).forest>0.65 &&
       world.sample(highlandRegion.origin.x,highlandRegion.origin.y).forest<0.25,"regional forest blends into open highlands");
 World other({43,128,32});
 check(!near(world.sample(140,70).height,other.sample(140,70).height),"different seeds change terrain away from reserved bank terrace");
 const auto l=world.lighting(0,0,200), l0=world.lighting(-0.001,0,200), l1=world.lighting(0.001,0,200);
 check(l.brightness>0&&l.kelvin>2000,"lighting returns usable illumination");
 check(std::abs(l0.kelvin-l1.kelvin)<1,"regional lighting transition is continuous");
 const auto eastRegion=world.region(1,0);
 check(!near(world.lighting(-180,-180,0).brightness,world.lighting(eastRegion.origin.x,eastRegion.origin.y,0).brightness),"distinct hex regions have independent light phases");
 Observation o; o.accelerate(true); check(near(o.rate(),1),"acceleration requires sitting");
 o.sit(true); o.accelerate(true); o.advance(2); check(near(o.seconds,40),"seated acceleration advances shared world time");
 o.sit(false); check(near(o.rate(),1)&&!o.accelerated,"standing restores normal time");
 bool rejected=false; try { World invalid({1,0,0}); } catch(const std::invalid_argument&) { rejected=true; }
 check(rejected,"invalid generation dimensions rejected");
 // Catch holes at negative chunk coordinates and non-power-of-two chunk sizes.
 for(unsigned seed:{0u,1u,42u,98765u}) {
  World varied({seed,96,24});
  auto west=varied.generate(-1,-1),east=varied.generate(0,-1),north=varied.generate(-1,0);
  for(int i=0;i<=24;++i) {
   check(near(west.vertices[i*25+24].z,east.vertices[i*25].z),"negative east-west seams agree");
   check(near(west.vertices[24*25+i].z,north.vertices[i].z),"negative north-south seams agree");
  }
  for(auto index:west.triangles) check(index<west.vertices.size(),"triangle indices remain in range");
  // The reserved stream-bank route must be walkable, even across seed changes.
  for(int y=-220;y<220;y+=4) {
   const auto route=varied.sample(varied.streamX(y)-7,y);
   check(route.slope<std::tan(38.0*3.141592653589793/180),"reserved bank route is walkable");
  }
 }
 // Layered habitats and the narrow protected bank survive multiple seeds.
 for(unsigned seed:{0u,42u,98765u}) {
  World habitat({seed,128,16});
  std::size_t trees=0,understory=0,highlandTrees=0,total=0,bankDetail=0,forestFerns=0,largeFerns=0;
  for(int cy=-2;cy<2;++cy) for(int cx=-2;cx<2;++cx) {
   const auto chunk=habitat.generate(cx,cy);
   total+=chunk.features.size();
   for(const auto& f:chunk.features) {
    const double routeDistance=std::abs(f.position.x-(habitat.streamX(f.position.y)-7));
    if(f.kind==Kind::Tree||f.kind==Kind::Rock)
     check(routeDistance>2.0,"protected bank route has no trees or rocks");
    if(habitat.sample(f.position.x,f.position.y).biome[0]>0.65) {
     trees+=f.kind==Kind::Tree;
     forestFerns+=f.kind==Kind::Fern;
     largeFerns+=f.kind==Kind::Fern&&f.scale>1.4;
     understory+=f.kind==Kind::Grass||f.kind==Kind::Fern;
    }

    if(std::abs(f.position.x-habitat.streamX(f.position.y))<10) ++bankDetail;
   }
   const auto repeat=habitat.generate(cx,cy);
   check(repeat.features.size()==chunk.features.size(),"multi-seed habitat repeats counts");
   for(std::size_t i=0;i<chunk.features.size();++i) {
    const auto& f=chunk.features[i]; const auto& r=repeat.features[i];
    check(f.kind==r.kind&&near(f.position.x,r.position.x)&&near(f.position.y,r.position.y)&&near(f.scale,r.scale),"multi-seed habitat repeats full placement");
   }
  }
  const auto highland=habitat.region(1,1);
  const auto highlandChunk=habitat.generate(static_cast<int>(std::floor(highland.origin.x/128)),static_cast<int>(std::floor(highland.origin.y/128)));
  for(const auto& f:highlandChunk.features) highlandTrees+=f.kind==Kind::Tree;
  const auto colonyChunk=habitat.generate(-2,0);
  int patches[64]={};
  for(const auto& f:colonyChunk.features) if(f.kind==Kind::Fern||f.kind==Kind::Grass) {
   const int col=static_cast<int>((f.position.x+256)/16),row=static_cast<int>(f.position.y/16);
   if(col>=0&&col<8&&row>=0&&row<8) ++patches[row*8+col];
  }
  const auto range=std::minmax_element(patches,patches+64);
  check(*range.second>2*std::max(1,*range.first),"understory forms dense colonies and open pockets");
  check(trees>200&&understory>6000,"forest canopy and dense understory coexist");
  check(forestFerns>understory/3&&largeFerns>forestFerns/3,"moist forest has substantial mature fern colonies");
  // Compare area-normalized density, rather than assuming x alone defines a biome.
  const auto forestChunk=habitat.generate(-2,-2);
  std::size_t forestChunkTrees=0;
  for(const auto& f:forestChunk.features) forestChunkTrees+=f.kind==Kind::Tree;
  check(highlandTrees<forestChunkTrees/3,"open highlands have substantially fewer trees per equal area");
  check(bankDetail>100,"stream banks retain vegetation outside narrow route");
  check(total<80000,"512 metre habitat stays within feature budget");
  std::cout<<"Habitat seed "<<seed<<": "<<total<<" features, "<<trees<<" forest trees, "<<understory<<" understory, "<<highlandTrees<<" highland trees\n";
 }
 // Repartitioning identical world bounds cannot duplicate or lose a candidate.
 World small({42,96,8}),large({42,192,8});
 auto united=large.generate(-1,-1).features;
 std::vector<Feature> pieces;
 for(int cy=-2;cy<0;++cy) for(int cx=-2;cx<0;++cx) {
  const auto part=small.generate(cx,cy);
  pieces.insert(pieces.end(),part.features.begin(),part.features.end());
 }
 auto order=[](const Feature& a,const Feature& b) {
  if(a.position.x!=b.position.x) return a.position.x<b.position.x;
  if(a.position.y!=b.position.y) return a.position.y<b.position.y;
  if(a.kind!=b.kind) return static_cast<int>(a.kind)<static_cast<int>(b.kind);
  if(a.scale!=b.scale) return a.scale<b.scale;
  return a.yaw<b.yaw;
 };
 std::sort(united.begin(),united.end(),order); std::sort(pieces.begin(),pieces.end(),order);
 check(united.size()==pieces.size(),"chunk repartition preserves candidates at negative boundaries");
 if(united.size()==pieces.size()) for(std::size_t i=0;i<united.size();++i)
  check(united[i].kind==pieces[i].kind&&near(united[i].position.x,pieces[i].position.x)&&near(united[i].position.y,pieces[i].position.y)&&near(united[i].scale,pieces[i].scale),"chunk repartition preserves every layered feature");

 // Verify zero tree overlap with discovery inner reservations across chunks
 for(unsigned seed : {0u, 42u, 98765u}) {
  World testWorld({seed, 128, 16});
  std::vector<DiscoveryReservation> testReservations;
  auto hFn = [&](double hx, double hy) { return testWorld.terrainHeight(hx, hy); };
  auto sXFn = [&](double sy) { return testWorld.streamX(sy); };
  auto sHWFn = [&](double sy) { return testWorld.streamHalfWidth(sy); };
  for(int cy = -3; cy <= 3; ++cy) {
   for(int cx = -3; cx <= 3; ++cx) {
    const auto r = testWorld.region(cx, cy);
    const Vec3 center{r.origin.x, r.origin.y, testWorld.terrainHeight(r.origin.x, r.origin.y)};
    const auto climate = testWorld.sample(r.origin.x, r.origin.y);
    const auto plan = planDiscovery(seed, cx, cy, center, climate, hFn, sXFn, sHWFn, r.ruins);
    if(plan.valid && (plan.reservation.innerRadius > 0.0 || plan.reservation.outerRadius > 0.0)) {
     testReservations.push_back(plan.reservation);
    }
   }
  }
  check(!testReservations.empty(), "discovery reservations planned in test area");
  for(int cy = -2; cy <= 2; ++cy) {
   for(int cx = -2; cx <= 2; ++cx) {
    const auto chunk = testWorld.generate(cx, cy);
    for(const auto& f : chunk.features) {
     if(f.kind == Kind::Tree) {
      check(!isInsideReservation(testReservations, f.position.x, f.position.y, true),
            "zero trees generated inside discovery inner reservation radii");
     }
    }
   }
  }
 }

 // Deterministic feature generation across chunks
 for(unsigned seed : {42u, 12345u}) {
  World wA({seed, 128, 16}), wB({seed, 128, 16});
  for(int cy = -1; cy <= 1; ++cy) {
   for(int cx = -1; cx <= 1; ++cx) {
    const auto chA = wA.generate(cx, cy);
    const auto chB = wB.generate(cx, cy);
    check(chA.features.size() == chB.features.size(), "chunk feature generation is deterministic in count");
    bool match = true;
    for(std::size_t i = 0; i < chA.features.size(); ++i) {
     if(chA.features[i].kind != chB.features[i].kind ||
        !near(chA.features[i].position.x, chB.features[i].position.x) ||
        !near(chA.features[i].position.y, chB.features[i].position.y) ||
        !near(chA.features[i].scale, chB.features[i].scale)) {
      match = false;
      break;
     }
    }
    check(match, "chunk feature generation is deterministic across instances");
   }
  }
 }

 // Smooth stream bank profile: monotone non-increasing from bed centre to waterline.
 {
  bool monotone=near(World::bankProfile(0),1);
  double previous=World::bankProfile(0);
  for(int i=1;i<=100;++i) {
   const double value=World::bankProfile(i/100.0);
   monotone=monotone&&value<=previous+1e-12;
   previous=value;
  }
  check(monotone&&near(World::bankProfile(1),0)&&near(World::bankProfile(1.5),0),"bank profile is monotone from 1 to 0");
 }
 // Stream depth: bed centre near 0.55 m, dry at two half-widths.
 {
  World bankWorld({42,128,32});
  bool centreOk=true, dryOk=true;
  for(int y=-200;y<=200;y+=4) {
   const double sx=bankWorld.streamX(y), hw=bankWorld.streamHalfWidth(y);
   const double centre=bankWorld.streamDepth(sx,y);
   centreOk=centreOk&&centre>=0.5&&centre<=0.6;
   dryOk=dryOk&&near(bankWorld.streamDepth(sx+2.0*hw,y),0);
  }
  check(centreOk,"stream centre depth is within 0.5-0.6 m");
  check(dryOk,"stream depth is zero at two half-widths");
 }
 // Seams: terrain is continuous across chunk boundaries near the stream.
 {
  World seam({42,128,32});
  bool continuous=true;
  for(int k=-2;k<=2;++k) {
   const double bx=k*128.0, by=k*128.0;
   for(int i=-40;i<=40;++i) {
    const double px=seam.streamX(by)+i*0.37;
    continuous=continuous&&std::abs(seam.terrainHeight(px,by-1e-4)-seam.terrainHeight(px,by+1e-4))<1e-3;
    const double py=i*4.1;
    continuous=continuous&&std::abs(seam.terrainHeight(bx-1e-4,py)-seam.terrainHeight(bx+1e-4,py))<1e-3;
   }
  }
  check(continuous,"terrain is continuous across chunk seams near the stream");
 }
 // Nearest discovery: deterministic, inside the search radius, and rejects a non-positive radius.
 {
  World disc({12345,128,64});
  const auto first=disc.nearestDiscovery(-60,-60,900);
  const auto second=disc.nearestDiscovery(-60,-60,900);
  check(first.has_value(),"nearestDiscovery finds a discovery within 900 m of the ruin origin");
  if(first&&second) {
   check(first->x==second->x&&first->y==second->y,"nearestDiscovery is deterministic");
   check(std::hypot(first->x+60,first->y+60)<=900+1e-9,"nearestDiscovery point lies within the search radius");
  }
  check(!disc.nearestDiscovery(-60,-60,0).has_value(),"nearestDiscovery rejects zero radius");
 }
 // Nearest biome core: deterministic, inside the radius, and meets the requested family weight.
 {
  World core({12345,128,64});
  const auto first=core.nearestBiomeCore(Biome::Taiga,-1002.724,-1605,2000,0.85);
  const auto second=core.nearestBiomeCore(Biome::Taiga,-1002.724,-1605,2000,0.85);
  check(first.has_value(),"nearestBiomeCore finds a Taiga core within 2000 m of the Taiga review view");
  if(first&&second) {
   check(first->x==second->x&&first->y==second->y,"nearestBiomeCore is deterministic");
   check(std::hypot(first->x+1002.724,first->y+1605)<=2000+1e-9,"nearestBiomeCore point lies within the search radius");
   check(core.sample(first->x,first->y).biome[static_cast<std::size_t>(Biome::Taiga)]>=0.85,"nearestBiomeCore point meets the minimum Taiga weight");
  }
  check(!core.nearestBiomeCore(Biome::Taiga,-1002.724,-1605,0,0.85).has_value(),"nearestBiomeCore rejects zero radius");
 }
 // Independent region flags over 10,000 cells: unreal p=0.10, ruins p=1/3, co-occurrence equals the product.
 {
  World flags({42,128,32});
  int unreal=0,ruins=0,both=0,total=0;
  for(int q=-50;q<50;++q) for(int r=-50;r<50;++r) {
   const auto g=flags.region(q,r);
   ++total; unreal+=g.unreal; ruins+=g.ruins; both+=(g.unreal&&g.ruins);
  }
  const double pu=static_cast<double>(unreal)/total, pr=static_cast<double>(ruins)/total, pb=static_cast<double>(both)/total;
  check(total==10000,"region flag sample covers 10000 cells");
  check(pu>=0.09&&pu<=0.11,"unreal region fraction is about one tenth");
  check(pr>=0.323&&pr<=0.343,"ruins region fraction is about one third");
  check(std::abs(pb-pu*pr)<=0.01,"unreal and ruins region flags are independent");
 }
 // Regional family field: adjacency contract, shares, order independence, origin cells fixed.
 {
  const int span=60,lo=-30;
  const int dirs[6][2]={{1,0},{1,-1},{0,-1},{-1,0},{-1,1},{0,1}};
  const int fixed[7][3]={{0,0,0},{1,0,1},{0,1,1},{1,1,2},{1,-1,2},{0,-1,3},{-1,0,0}};
  for(unsigned seed:{0u,42u,98765u}) {
   World world({seed,128,64});
   std::vector<Biome> fam(span*span);
   std::array<std::size_t,4> shares{};
   for(int q=0;q<span;++q) for(int r=0;r<span;++r) {
    fam[q*span+r]=world.region(q+lo,r+lo).family;
    ++shares[static_cast<std::size_t>(fam[q*span+r])];
   }
   bool adjacentOk=true;
   for(int q=0;q<span;++q) for(int r=0;r<span;++r) for(const auto& d:dirs) {
    const int nq=q+d[0],nr=r+d[1];
    if(nq<0||nr<0||nq>=span||nr>=span) continue;
    if(!allowedAdjacent(fam[q*span+r],fam[nq*span+nr])) adjacentOk=false;
   }
   check(adjacentOk,"no adjacent region pair violates allowedAdjacent over 60x60 window");
   for(std::size_t i=0;i<4;++i) check(shares[i]>=0.08*span*span,"each region family holds at least 8 percent of the 60x60 window");
   for(const auto& f:fixed) check(world.region(f[0],f[1]).family==static_cast<Biome>(f[2]),"origin-cell families unchanged");
   std::vector<int> order(span*span);
   for(int i=0;i<span*span;++i) order[i]=i;
   std::mt19937 rng(7u);
   std::shuffle(order.begin(),order.end(),rng);
   World shuffled({seed,128,64});
   bool orderOk=true;
   for(int idx:order) {
    const int q=idx/span,r=idx%span;
    if(shuffled.region(q+lo,r+lo).family!=fam[idx]) orderOk=false;
   }
   check(orderOk,"region family is identical when cells are computed in shuffled order");
  }
  check(!allowedAdjacent(Biome::DryGrassland,Biome::Taiga)&&!allowedAdjacent(Biome::Taiga,Biome::DryGrassland),"DryGrassland and Taiga are forbidden neighbours");
  check(allowedAdjacent(Biome::TemperateForest,Biome::Taiga)&&allowedAdjacent(Biome::RockyHighlands,Biome::DryGrassland),"other family pairs are allowed neighbours");
 }
 bool badTime=false; try { o.advance(-1); } catch(const std::invalid_argument&) { badTime=true; }
 check(badTime,"negative elapsed time rejected");
 // Golden output as of 8446d11. Update ONLY for intentional generation changes.
 {
  struct GoldenCase { unsigned seed; int x,y; bool features; std::uint64_t expected; };
  const GoldenCase cases[]={
   {0,0,0,true,0x67757b2508650af7ULL},{0,3,-2,true,0xc76a569e534166adULL},{0,-5,7,true,0xcecd8eb66220e387ULL},{0,12,12,true,0xf99ce6e5d4eae079ULL},{0,0,0,false,0x5999df15b6cbaef8ULL},
   {42,0,0,true,0xc08cf1e2f1ae1fa5ULL},{42,3,-2,true,0xfd2f56462206480fULL},{42,-5,7,true,0xd422751e936420a5ULL},{42,12,12,true,0xb792a76f92d87c37ULL},{42,0,0,false,0xbc40aa921da47d78ULL},
   {98765,0,0,true,0xeec638392fa85ba7ULL}, // changed in U1: chunk lies in an unreal region (overlay density)
   {98765,3,-2,true,0x8fa5118bb65e0c9dULL}, // changed in U1: chunk lies in an unreal region (overlay density)
   {98765,-5,7,true,0xeaa24c98d7486d7bULL},{98765,12,12,true,0x4458cc110da81ba0ULL},{98765,0,0,false,0x893f568f384c0dbfULL},
  };
  for(const auto& gc:cases) {
   World w({gc.seed,128,32});
   const std::uint64_t h=fingerprintChunk(w,w.generate(gc.x,gc.y,gc.features));
   std::printf("golden seed=%u chunk=(%d,%d) features=%d hash=0x%016llx\n",gc.seed,gc.x,gc.y,gc.features?1:0,static_cast<unsigned long long>(h));
   check(h==gc.expected,"generation output matches golden fingerprint");
  }
 }
 // Forgotten regions: epoch 1 on the owner of chunk (3,-2) regenerates that chunk; a distant epoch-0 chunk stays identical.
 {
  const auto ownerOfChunk=[](int cx,int cy,std::uint32_t seed) {
   return hex::owner(hex::warp({(cx+0.5)*128.0+180,(cy+0.5)*128.0+180},seed));
  };
  const auto target=ownerOfChunk(3,-2,42);
  const auto epochFn=[target](int q,int r)->std::uint32_t { return (q==target.q&&r==target.r)?1u:0u; };
  World base({42,128,32}), forgot({42,128,32}), zeroed({42,128,32});
  forgot.setEpochs(epochFn);
  zeroed.setEpochs([](int,int)->std::uint32_t { return 0u; });
  check(fingerprintChunk(base,base.generate(0,0))==fingerprintChunk(zeroed,zeroed.generate(0,0)),"epoch-0 setEpochs output matches default output");
  const auto before=base.generate(3,-2), after=forgot.generate(3,-2);
  std::set<std::pair<double,double>> kept;
  for(const auto& f:after.features) kept.insert({f.position.x,f.position.y});
  std::size_t moved=0;
  for(const auto& f:before.features) moved+=kept.count({f.position.x,f.position.y})==0;
  const double movedShare=before.features.empty()?0.0:static_cast<double>(moved)/static_cast<double>(before.features.size());
  std::printf("forgotten chunk (3,-2): %zu of %zu features moved (%.1f%%)\n",moved,before.features.size(),100*movedShare);
  check(movedShare>0.30,"forgotten chunk moves more than 30 percent of features");
  check(fingerprintChunk(base,before)!=fingerprintChunk(forgot,after),"forgotten chunk fingerprint differs");
  bool found=false;
  for(int cy=-40;cy<=40&&!found;++cy) for(int cx=-40;cx<=40&&!found;++cx) {
   const auto o=ownerOfChunk(cx,cy,42);
   const int dq=o.q-target.q, dr=o.r-target.r;
   if(std::max({std::abs(dq),std::abs(dr),std::abs(dq+dr)})<5) continue;
   found=true;
   check(fingerprintChunk(base,base.generate(cx,cy))==fingerprintChunk(forgot,forgot.generate(cx,cy)),"chunk owned by distant epoch-0 regions is byte-identical");
  }
  check(found,"distant epoch-0 chunk exists");
  // Order independence: 8 fixed-seed shuffles of a 3x3 chunk block, full features, per-chunk fingerprints vs in-order run.
  std::vector<std::pair<int,int>> block;
  for(int cy=-3;cy<=-1;++cy) for(int cx=2;cx<=4;++cx) block.push_back({cx,cy});
  std::vector<std::uint64_t> expected;
  for(const auto& c:block) expected.push_back(fingerprintChunk(forgot,forgot.generate(c.first,c.second,true)));
  std::vector<std::size_t> order(block.size());
  for(std::size_t i=0;i<order.size();++i) order[i]=i;
  std::mt19937 rng(11u);
  std::size_t shuffleMismatch=0;
  for(int s=0;s<2;++s) {
   std::shuffle(order.begin(),order.end(),rng);
   for(std::size_t idx:order) {
    if(fingerprintChunk(forgot,forgot.generate(block[idx].first,block[idx].second,true))!=expected[idx]) ++shuffleMismatch;
   }
  }
  check(shuffleMismatch==0,"epoch-set generation is identical across 8 shuffled chunk orders");
 }
 if(failures) return 1;
 std::cout<<"PASS: generation, hydrology, placement, lighting and observation contracts\n";
}
