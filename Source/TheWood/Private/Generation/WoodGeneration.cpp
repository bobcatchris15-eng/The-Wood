#include "Generation/WoodGeneration.h"
#include <set>
#include "Generation/WoodSalts.h"
#include "Generation/WoodHex.h"
#include "Generation/WoodDiscovery.h"
#include "Generation/WoodEntrance.h"
#include "Generation/WoodKit.h"
#include "Generation/WoodUnreal.h"
#include "Generation/WoodFlora.h"
#include <algorithm>
#include <cmath>
#include <stdexcept>

namespace wood {
namespace {
constexpr double pi=3.14159265358979323846;
double smooth(double value) { value=std::clamp(value,0.0,1.0); return value*value*(3-2*value); }
std::uint32_t hash(std::uint32_t seed,int x,int y,std::uint32_t salt) {
 auto h=seed ^ (static_cast<std::uint32_t>(x)*0x9e3779b9u) ^ (static_cast<std::uint32_t>(y)*0x85ebca6bu) ^ salt;
 h^=h>>16; h*=0x7feb352du; h^=h>>15; h*=0x846ca68bu; return h^(h>>16);
}
double random(std::uint32_t seed,int x,int y,std::uint32_t salt) { return hash(seed,x,y,salt)/4294967296.0; }
double noise(std::uint32_t seed,double x,double y) {
 const int ix=static_cast<int>(std::floor(x)), iy=static_cast<int>(std::floor(y));
 const double u=smooth(x-ix),v=smooth(y-iy);
 const double a=random(seed,ix,iy,Salt::NoiseLattice),b=random(seed,ix+1,iy,Salt::NoiseLattice),c=random(seed,ix,iy+1,Salt::NoiseLattice),d=random(seed,ix+1,iy+1,Salt::NoiseLattice);
 return ((a+(b-a)*u)*(1-v)+(c+(d-c)*u)*v)*2-1;
}

void validatePoint(double x,double y) {
 if(!std::isfinite(x)||!std::isfinite(y)||std::abs(x)>1000000||std::abs(y)>1000000)
  throw std::invalid_argument("Sample outside supported milestone coordinates");
}
struct ClimateField { double temperature01, moisture01; };
// Low-frequency fields sampled at hex centres, wavelength ~6 cells; outputs in [0,1].
ClimateField climateAt(const World& w,int gx,int gy) {
 const auto seed=w.regionSeed(gx,gy);
 const double x=gx/6.0,y=gy/6.0;
 return {0.5+0.5*noise(seed+Salt::ClimateTemperature,x,y),0.5+0.5*noise(seed+Salt::ClimateMoisture,x,y)};
}
double reliefAt(const World& w,int gx,int gy) { return 0.5+0.5*noise(w.regionSeed(gx,gy)+Salt::ClimateRelief,gx/6.0,gy/6.0); }
std::optional<Biome> originOverride(int gx,int gy) {
 if(gx==0&&gy==0) return Biome::TemperateForest;
 if((gx==1&&gy==0)||(gx==0&&gy==1)) return Biome::DryGrassland;
 if((gx==1&&gy==1)||(gx==1&&gy==-1)) return Biome::RockyHighlands;
 if(gx==0&&gy==-1) return Biome::Taiga;
 if(gx==-1&&gy==0) return Biome::TemperateForest;
 return std::nullopt;
}
constexpr double kMarshReliefSplit=0.22;
Biome tableFamily(const World& w,int gx,int gy) {
 const auto f=climateAt(w,gx,gy);
 // Wet lowlands are checked first so they win over ColdRainforest and OldGrowth.
 // Wetland gate; within it, Marsh is the open low basin (relief split or cool), Swamp the wooded warm remainder.
 if(f.moisture01>=0.66&&reliefAt(w,gx,gy)<=0.40&&f.temperature01>=0.25) {
  if(reliefAt(w,gx,gy)<=kMarshReliefSplit||f.temperature01<0.40) return Biome::Marsh;
  return Biome::Swamp;
 }
 if(f.temperature01>=0.28&&f.temperature01<0.48&&f.moisture01>=0.62) return Biome::ColdRainforest;
 if(f.temperature01>=0.45&&f.moisture01>=0.62&&reliefAt(w,gx,gy)<=0.45) return Biome::OldGrowthForest;
 if(f.temperature01<0.20&&reliefAt(w,gx,gy)>0.50) return Biome::IcyHills;
 if(f.temperature01<0.30) return Biome::Taiga;
 if(f.temperature01>=0.62&&f.moisture01>=0.68) return Biome::WarmRainforest;
 if(f.temperature01>=0.66&&f.moisture01>=0.25&&f.moisture01<0.45) return Biome::Savannah;
 // DryGrassland window is moisture<0.35 over [0,0.35); Prairie takes its moister half (>=0.175).
 if(f.moisture01<0.35) return f.moisture01>=0.175?Biome::Prairie:Biome::DryGrassland;
 if(reliefAt(w,gx,gy)>0.62) return Biome::RockyHighlands;
 return Biome::TemperateForest;
}
// Strict total order on cells by (hash,gx,gy); the lower key yields on a forbidden pair.
bool lowerKey(std::uint32_t h1,int x1,int y1,std::uint32_t h2,int x2,int y2) {
 if(h1!=h2) return h1<h2;
 if(x1!=x2) return x1<x2;
 return y1<y2;
}
Biome regionFamily(const World& w,int gx,int gy) {
 if(const auto fixed=originOverride(gx,gy)) return *fixed;
 const Biome base=tableFamily(w,gx,gy);
 const auto self=hash(w.regionSeed(gx,gy),gx,gy,Salt::RegionFamily);
 for(const auto d:hex::directions) {
  const int nx=gx+d.q,ny=gy+d.r;
  const auto fixed=originOverride(nx,ny);
  const Biome partner=fixed?*fixed:tableFamily(w,nx,ny);
  if(allowedAdjacent(base,partner)) continue;
  // Origin cells are authored and cannot yield, so the free neighbour always does.
  if(fixed) return Biome::TemperateForest;
  if(lowerKey(self,gx,gy,hash(w.regionSeed(nx,ny),nx,ny,Salt::RegionFamily),nx,ny)) return Biome::TemperateForest;
 }
 return base;
}

// Per-family multipliers in Biome order; the four original families are identity (1 or 0).
constexpr std::array<double,kFamilyCount> kTreeScaleMul{{1,1,1,1,1.35,1,0.6,1.2,1.1,1,1.25,1}};
constexpr std::array<double,kFamilyCount> kRockMul{{1,1,1,1,1.5,1,2.0,1,0.3,0.2,0.4,1}};
constexpr std::array<double,kFamilyCount> kLightBrightnessMul{{1,1,1,1,0.8,1,1.15,1.10,0.75,1.0,0.7,1}};
constexpr std::array<double,kFamilyCount> kLightKelvinShift{{0,0,0,0,0,-400,900,500,-300,-100,200,0}};
// Terrain relief multiplier per family: wet basins flatten local relief.
constexpr std::array<double,kFamilyCount> kReliefMul{{1,1,1,1,1,1,1,1,0.35,0.35,1,1}};
// Weight-blended multiplier 1+sum(w*(m-1)); exactly 1 when only identity families carry weight.
double familyMul(const std::array<double,kFamilyCount>& biome,const std::array<double,kFamilyCount>& mul) {
 double m=1;
 for(std::size_t i=0;i<kFamilyCount;++i) m+=biome[i]*(mul[i]-1);
 return m;
}
// T1c: fallen deadwood per 100 m² (one lattice cell), blended by family weights.
constexpr std::array<double,kFamilyCount> kDeadwoodDensity{{0.02,0,0,0.02,0.08,0.06,0,0,0.05,0,0,0}};
double deadwoodDensity(const std::array<double,kFamilyCount>& biome) {
 double d=0;
 for(std::size_t i=0;i<kFamilyCount;++i) d+=biome[i]*kDeadwoodDensity[i];
 return d;
}

Region describe(const World& w,int gx,int gy) {
 const auto seed=w.regionSeed(gx,gy);
 Region r;
 r.identity=hash(seed,gx,gy,Salt::RegionIdentity);
 const auto center=hex::center({gx,gy});
 r.origin={center.x-180,center.y-180,0};r.q=gx;r.r=gy;r.extent=hex::radius*2;
 r.family=regionFamily(w,gx,gy);
 const auto i=static_cast<std::size_t>(r.family);
 constexpr std::array<double,kFamilyCount> moisture{{0.78,0.24,0.38,0.58,0.70,0.92,0.30,0.32,0.88,0.84,0.95,0.50}};
 constexpr std::array<double,kFamilyCount> roughness{{0.22,0.16,0.85,0.36,0.28,0.30,0.80,0.20,0.10,0.08,0.30,0.18}};
 constexpr std::array<double,kFamilyCount> temperature{{16,24,8,-3,15,6,-6,24,14,4,26,22}};
 constexpr std::array<double,kFamilyCount> canopy{{0.96,0.055,0.09,0.70,0.98,0.90,0.30,0.22,0.78,0.15,0.97,0.05}};
 constexpr std::array<double,kFamilyCount> exposure{{0.18,0.86,0.94,0.38,0.14,0.30,0.82,0.40,0.22,0.66,0.12,0.80}};
 static_assert(moisture.size()==kFamilyCount&&roughness.size()==kFamilyCount&&temperature.size()==kFamilyCount&&canopy.size()==kFamilyCount&&exposure.size()==kFamilyCount,"per-family tables need one row per Biome value");
 r.moisture=moisture[i]; r.roughness=roughness[i]; r.temperature=temperature[i];
 r.canopy=canopy[i]; r.exposure=exposure[i]; r.shelter=1-r.exposure;
 r.phase=random(seed,gx,gy,Salt::RegionPhase)*2*pi;
 r.unreal=(hash(seed,gx,gy,Salt::RegionUnreal)%1000)<100;
 r.ruins=(hash(seed,gx,gy,Salt::RegionRuins)%3000)<1000;
 r.overlay=r.unreal?unreal::pick(r.identity,r.family):unreal::Overlay::None;
 return r;
}
auto cellWeights(const Settings& c,double x,double y) {return hex::weights(hex::warp({x+180,y+180},c.seed));}
Surface climate(const World& world,double x,double y) {
 Surface s; double total=0;
 for(const auto& cell:cellWeights(world.settings(),x,y)) {
  if(cell.weight<=0) continue;
  const auto r=describe(world,cell.cell.q,cell.cell.r);const double weight=cell.weight;
  total+=weight; s.biome[static_cast<std::size_t>(r.family)]+=weight;
  s.forest+=weight*r.canopy; s.moisture+=weight*r.moisture;
  s.temperature+=weight*r.temperature; s.exposure+=weight*r.exposure;
  s.shelter+=weight*r.shelter; s.roughness+=weight*r.roughness;
 }
 for(auto& w:s.biome) w/=total;
 s.forest/=total; s.moisture/=total; s.temperature/=total;
 s.exposure/=total; s.shelter/=total; s.roughness/=total;
 return s;
}
// Hex-weighted overlay multipliers. Ordinary cells contribute neutral values, so the field fades across the blend band.
unreal::OverlayField overlayField(const World& world,double x,double y) {
 unreal::OverlayField f;
 double total=0,featureScale=0,densityScale=0,brightness=0,kelvinShift=0,fungusScale=0,unrealW=0;
 bool any=false;
 for(const auto& cell:cellWeights(world.settings(),x,y)) {
  if(cell.weight<=0) continue;
  const auto r=describe(world,cell.cell.q,cell.cell.r);
  const auto p=unreal::params(r.overlay);
  const double w=cell.weight;
  total+=w; featureScale+=w*p.featureScale; densityScale+=w*p.densityScale;
  brightness+=w*p.lightBrightness; kelvinShift+=w*p.lightKelvinShift; fungusScale+=w*p.fungusScale;
  if(r.unreal) unrealW+=w;
  any=any||r.unreal;
 }
 if(!any||total<=0) return f;
 f.featureScale=featureScale/total; f.densityScale=densityScale/total;
 f.lightBrightness=brightness/total; f.lightKelvinShift=kelvinShift/total;
 f.fungusScale=fungusScale/total; f.unrealWeight=unrealW/total; f.active=true;
 return f;
}
double waterLevel(double y) { return 8-0.018*y; }
double channelHalfWidth(const Settings& c,double y) {
 return 1.4+0.5*(1+noise(c.seed+Salt::ChannelWidth,0,y/160));
}
double groundBase(const World& world,double x,double y,double stream,const Surface* cachedClimate=nullptr) {
 const Settings& c=world.settings();
 const double distance=std::abs(x-stream),water=waterLevel(y);
 // A sub-cell bed margin keeps the narrow water surface above the 2m mesh.
 const double bedHalfWidth=channelHalfWidth(c,y)+0.9;
 const double poolDepth=0.34+0.08*noise(c.seed+Salt::PoolDepth,0,y/26.0);
 const double channel=water-poolDepth+(poolDepth+0.04)*std::pow(std::min(distance/bedHalfWidth,1.0),2);
 const double bankWidth=2.2+1.0*(1.0+noise(c.seed+Salt::BankWidth,0,y/32.0));
 const double bankContour=0.45*noise(c.seed+Salt::BankContour,x/6.0,y/6.0)+0.20*noise(c.seed+Salt::BankContourFine,x/14.0,y/14.0);
 const double effectiveDist=std::max(0.0,distance+bankContour*smooth((distance-bedHalfWidth*0.8)/2.0));
 double bank=channel+(water+0.75-channel)*smooth((effectiveDist-bedHalfWidth)/bankWidth);
 if(distance<=bedHalfWidth*0.85) bank=std::min(bank,water-0.01);
 // Smooth channel: bed sloping up to the waterline at u=1.05, then a dry bank rising to the original terrain at u=2.
 const double halfW=channelHalfWidth(c,y);
 const double u=distance/halfW;
 if(u<=1.05) bank=water-0.55*World::bankProfile(u/1.05);
 else if(u<2.0) bank=water+(std::max(bank,water+0.04)-water)*smooth((u-1.05)/0.95);
 // Hydrology owns the continuous low terrace; no climatic query is needed here.
 if(distance<=10) return bank;
 const auto regionClimate=cachedClimate?*cachedClimate:climate(world,x,y);
 const double highlands=regionClimate.biome[2];
 const double grassland=regionClimate.biome[1];
 const double broad=(7+regionClimate.roughness*16)*noise(c.seed,x/190,y/190);
 const double detail=noise(c.seed+Salt::Detail,x/22,y/22)*(0.45+regionClimate.roughness*3.2);

 // Flanking valley wall: climbs out of the low river terrace onto the higher terrain
 const double valleyWall=12.0*smooth((distance-10.0)/60.0);

 // Highlands: towering mountain mass with stepped geological crag bluffs & rocky terraces
 const double mountainMass=highlands*(28.0+46.0*std::pow(0.5+0.5*noise(c.seed+Salt::MountainMass,x/280.0,y/280.0),2));
 const double cragN=0.5+0.5*noise(c.seed+Salt::CragNoise,x/55.0,y/55.0);
 const double cragSteps=std::floor(cragN*3.0)*3.5+3.5*std::pow(cragN*3.0-std::floor(cragN*3.0),3.0);
 const double crags=highlands*(cragSteps+12.0*std::pow(0.5+0.5*noise(c.seed+Salt::CragRelief,x/85.0,y/85.0),3));

 // Grassland: wide, sweeping rolling prairie topography with long open sightlines
 const double prairie=grassland*8.0*noise(c.seed+Salt::Prairie,x/260.0,y/260.0);

 // Weight-blended relief amplitude: exactly 1 unless Swamp or Marsh carry weight, which flatten the basin.
 const double amp=familyMul(regionClimate.biome,kReliefMul);
 const double base=water+3.0+broad*amp+detail*amp+valleyWall*amp+mountainMass*amp+crags*amp+prairie*amp;
 return bank+(base-bank)*smooth((distance-10.0)/25.0);
}
// Stream distance far enough that groundBase sees no channel: the dry, carve-free wilderness height.
constexpr double FarStream=1e6;
// Wilderness base height, blended toward the trailhead entrance inside its zone while not entered.
// The stream carve fades out with entrance::blend, so the lot and path are dry.
double ground(const World& world,double x,double y,double stream,const Surface* cachedClimate=nullptr) {
 const double base=groundBase(world,x,y,stream,cachedClimate);
 if(world.entered()) return base;
 const double w=entrance::blend(x,y);
 if(w<=0) return base;
 const double dry=groundBase(world,x,y,x+FarStream,cachedClimate);
 const double carved=dry+(base-dry)*(1-w);
 const double lotHeight=groundBase(world,entrance::LotX,entrance::LotY,entrance::LotX+FarStream);
 const double shaped=entrance::shapedHeight(x,y,carved,lotHeight);
 return w>=1?shaped:carved+(shaped-carved)*w;
}
}
bool allowedAdjacent(Biome a,Biome b) {
 const auto forbidden=[](Biome x,Biome y){
  return (x==Biome::WarmRainforest&&(y==Biome::IcyHills||y==Biome::Taiga||y==Biome::DryGrassland||y==Biome::Prairie))||
         (x==Biome::Prairie&&(y==Biome::Taiga||y==Biome::ColdRainforest||y==Biome::IcyHills||y==Biome::Marsh))||
         (x==Biome::DryGrassland&&(y==Biome::Taiga||y==Biome::ColdRainforest||y==Biome::IcyHills))||
         (x==Biome::Savannah&&(y==Biome::Taiga||y==Biome::IcyHills||y==Biome::ColdRainforest||y==Biome::Swamp))||
         (x==Biome::Swamp&&(y==Biome::IcyHills)) ||
         (x==Biome::Marsh&&(y==Biome::IcyHills||y==Biome::DryGrassland));
 };
 return !(forbidden(a,b)||forbidden(b,a));
}
World::World(Settings settings):config(settings) {
 if(!std::isfinite(config.chunkSize)||config.chunkSize<=0||config.cells<2||config.cells>256)
  throw std::invalid_argument("Chunk size must be positive and cells must be between 2 and 256");
}
void World::setEpochs(std::function<std::uint32_t(int q,int r)> epochOf) {
 if(!epochOf) epochOf=[](int,int){return std::uint32_t{0};};
 epochOf_=std::move(epochOf);
}
void World::setEntered(bool value) { entered_=value; }
bool World::entered() const { return entered_; }
std::uint32_t World::regionSeed(int q,int r) const {
 const std::uint32_t epoch=epochOf_(q,r);
 return epoch==0?config.seed:hash(config.seed,q,r,Salt::RegionEpoch+epoch);
}
hex::Coord World::regionOwner(double x,double y) const {
 return hex::owner(hex::warp({x+180,y+180},config.seed));
}
double World::streamX(double y) const {
 return 24*std::sin(y/135.0+config.seed*0.01)+9*std::sin(y/52.0+config.seed*0.023)+3.5*std::sin(y/19.0+config.seed*0.047);
}
double World::streamHalfWidth(double y) const {
 validatePoint(0,y); return channelHalfWidth(config,y);
}
double World::bankProfile(double d01) { return 1-smooth(d01); }
double World::streamDepth(double x,double y) const {
 validatePoint(x,y);
 // No water in the entrance zone while not entered: the lot and path stay dry.
 if(!entered_&&entrance::blend(x,y)>0.5) return 0;
 if(std::abs(x-streamX(y))>=2.0*streamHalfWidth(y)) return 0;
 return std::max(0.0,waterLevel(y)-ground(*this,x,y,streamX(y)));
}
Surface World::sample(double x,double y) const {
 validatePoint(x,y);
 Surface s=climate(*this,x,y);
 s.height=ground(*this,x,y,streamX(y),&s);
 const double dx=(ground(*this,x+0.25,y,streamX(y))-ground(*this,x-0.25,y,streamX(y)))/0.5;
 const double dy=(ground(*this,x,y+0.25,streamX(y+0.25))-ground(*this,x,y-0.25,streamX(y-0.25)))/0.5;
 s.slope=std::hypot(dx,dy);
 s.waterHeight=waterLevel(y);
 const bool dryZone=!entered_&&entrance::blend(x,y)>0.5;
 s.depth=(!dryZone&&std::abs(x-streamX(y))<streamHalfWidth(y))?std::max(0.0,s.waterHeight-s.height):0;
 s.moisture=std::clamp(s.moisture+0.25*std::exp(-std::abs(x-streamX(y))/12),0.0,1.0);
 return s;
}
Region World::region(int latticeX,int latticeY) const {
 if(std::abs(static_cast<double>(latticeX))>835||std::abs(static_cast<double>(latticeY))>835)
  throw std::invalid_argument("Region outside supported milestone coordinates");
 return describe(*this,latticeX,latticeY);
}
std::vector<Region> World::regions(double x,double y) const {
 validatePoint(x,y); std::vector<Region> result;
 for(const auto& cell:cellWeights(config,x,y)) if(cell.weight>0) result.push_back(describe(*this,cell.cell.q,cell.cell.r));
 return result;
}
double World::terrainHeight(double x,double y) const {
 validatePoint(x,y);
 const double spacing=config.chunkSize/config.cells;
 const double cellX=std::floor(x/spacing),cellY=std::floor(y/spacing);
 const double x0=cellX*spacing,y0=cellY*spacing,u=x/spacing-cellX,v=y/spacing-cellY;
 const double a=ground(*this,x0,y0,streamX(y0));
 const double b=ground(*this,x0+spacing,y0,streamX(y0));
 const double c=ground(*this,x0,y0+spacing,streamX(y0+spacing));
 if(u+v<=1) return a+(b-a)*u+(c-a)*v;
 const double d=ground(*this,x0+spacing,y0+spacing,streamX(y0+spacing));
 return d+(c-d)*(1-u)+(b-d)*(1-v);
}
void World::forEachDiscoveryNear(int ownerQ,int ownerR,const std::function<void(const DiscoveryPlan&)>& fn) const {
 auto heightFn=[this](double hx,double hy){return terrainHeight(hx,hy);};
 auto streamXFn=[this](double sy){return streamX(sy);};
 auto streamHWFn=[this](double sy){return streamHalfWidth(sy);};
 for(int dy=-2;dy<=2;++dy) for(int dx=-2;dx<=2;++dx) {
  if(std::max({std::abs(dx),std::abs(dy),std::abs(dx+dy)})>2) continue;
  const int col=ownerQ+dx,row=ownerR+dy;
  const auto r=describe(*this,col,row);
  const Vec3 cellCenter{r.origin.x,r.origin.y,terrainHeight(r.origin.x,r.origin.y)};
  const auto cellClimate=sample(r.origin.x,r.origin.y);
  const auto plan=planDiscovery(regionSeed(col,row),col,row,cellCenter,cellClimate,heightFn,streamXFn,streamHWFn,r.ruins,r.unreal);
  if(!plan.valid) continue;
  fn(plan);
 }
}
std::optional<Vec3> World::nearestDiscovery(double x,double y,double radius) const {
 if(!(radius>0.0)) return std::nullopt;
 // Owner cells of a lattice of sample points covering the search square; neighbours are added by forEachDiscoveryNear.
 const double step=config.chunkSize*0.5;
 const int steps=static_cast<int>(std::ceil(radius/step));
 std::set<std::pair<int,int>> owners;
 for(int j=-steps;j<=steps;++j) for(int i=-steps;i<=steps;++i) {
  const auto owner=hex::owner(hex::warp({x+i*step+180,y+j*step+180},config.seed));
  owners.insert({owner.q,owner.r});
 }
 std::optional<Vec3> best;
 double bestD2=radius*radius;
 for(const auto& o:owners) forEachDiscoveryNear(o.first,o.second,[&](const DiscoveryPlan& plan){
  if(!(plan.reservation.outerRadius>0.0)) return;
  const double dx=plan.reservation.center.x-x, dy=plan.reservation.center.y-y;
  const double d2=dx*dx+dy*dy;
  if(d2<=bestD2) {
   bestD2=d2;
   best=plan.reservation.center;
  }
 });
 return best;
}
std::optional<Vec3> World::nearestBiomeCore(Biome family,double x,double y,double radius,double minWeight) const {
 if(!(radius>0.0)||!(minWeight>0.0)) return std::nullopt;
 // Owner cells enumerated exactly as nearestDiscovery; each owner's region origin seeds a 25 m refinement window.
 const double step=config.chunkSize*0.5;
 const int steps=static_cast<int>(std::ceil(radius/step));
 std::set<std::pair<int,int>> owners;
 for(int j=-steps;j<=steps;++j) for(int i=-steps;i<=steps;++i) {
  const auto owner=hex::owner(hex::warp({x+i*step+180,y+j*step+180},config.seed));
  owners.insert({owner.q,owner.r});
 }
 const auto index=static_cast<std::size_t>(family);
 const double grid=25.0, half=500.0;
 const int n=static_cast<int>(std::round(half/grid));
 std::optional<Vec3> best;
 double bestD2=radius*radius;
 for(const auto& o:owners) {
  const auto origin=region(o.first,o.second).origin;
  for(int j=-n;j<=n;++j) for(int i=-n;i<=n;++i) {
   const double px=origin.x+i*grid, py=origin.y+j*grid;
   const double dx=px-x, dy=py-y, d2=dx*dx+dy*dy;
   if(d2>=bestD2) continue;
   if(sample(px,py).biome[index]>=minWeight) {
    bestD2=d2;
    best=Vec3{px,py,0.0};
   }
  }
 }
 return best;
}
stage::RegionStage World::regionStage(int x,int y) const {
 stage::RegionStage s;
 s.minX=x*config.chunkSize; s.minY=y*config.chunkSize;
 s.maxX=(x+1)*config.chunkSize; s.maxY=(y+1)*config.chunkSize;
 const double midX=(s.minX+s.maxX)*0.5,midY=(s.minY+s.maxY)*0.5;
 const auto owner=hex::owner(hex::warp({midX+180,midY+180},config.seed));
 s.ownerQ=owner.q; s.ownerR=owner.r;
 return s;
}
stage::TerrainStage World::terrainStage(int x,int y) const {
 stage::TerrainStage s;
 const int n=config.cells;
 for(int row=0;row<=n;++row) for(int col=0;col<=n;++col) {
  const double px=(x+static_cast<double>(col)/n)*config.chunkSize, py=(y+static_cast<double>(row)/n)*config.chunkSize;
  s.vertices.push_back({px,py,ground(*this,px,py,streamX(py))});
 }
 for(int row=0;row<n;++row) for(int col=0;col<n;++col) {
  const auto i=static_cast<std::uint32_t>(row*(n+1)+col), stride=static_cast<std::uint32_t>(n+1);
  s.triangles.insert(s.triangles.end(),{i,i+stride,i+1,i+1,i+stride,i+stride+1});
 }
 return s;
}
stage::HydrologyStage World::hydrologyStage(const stage::TerrainStage& terrain) const {
 stage::HydrologyStage s;
 const std::size_t columns=static_cast<std::size_t>(config.cells)+1;
 for(std::size_t row=0;row<columns;++row) {
  const double py=terrain.vertices[row*columns].y;
  s.rowStreamX.push_back(streamX(py));
  s.rowHalfWidth.push_back(streamHalfWidth(py));
 }
 return s;
}
stage::StructureStage World::structureStage(const stage::RegionStage& region) const {
 stage::StructureStage s;
 forEachDiscoveryNear(region.ownerQ,region.ownerR,[&](const DiscoveryPlan& plan) {
  if(plan.reservation.innerRadius>0.0||plan.reservation.outerRadius>0.0) {
   s.reservations.push_back(plan.reservation);
  }
  for(const auto& piece:plan.pieces) {
   if(piece.position.x>=region.minX&&piece.position.x<region.maxX&&piece.position.y>=region.minY&&piece.position.y<region.maxY) {
    s.pieces.push_back(piece);
   }
  }
 });
 return s;
}
stage::HabitatStage World::habitatStage(const stage::RegionStage& region,const stage::StructureStage& structure,const stage::HydrologyStage&) const {
 stage::HabitatStage habitat;
 const double minX=region.minX,minY=region.minY,maxX=region.maxX,maxY=region.maxY;
 const auto& reservations=structure.reservations;
 // Independent global lattices keep layers dense and chunk ownership unambiguous.
 // Full-cell jitter and broad habitat patches conceal the underlying lattice.
 auto layer=[&](double spacing,std::uint32_t salt,int type) {
  const int firstX=static_cast<int>(std::floor(minX/spacing)),firstY=static_cast<int>(std::floor(minY/spacing));
  const int endX=static_cast<int>(std::ceil(maxX/spacing)),endY=static_cast<int>(std::ceil(maxY/spacing));
  for(int gy=firstY;gy<endY;++gy) for(int gx=firstX;gx<endX;++gx) {
   // Feature random() seed is the region owning the lattice cell's nominal centre: pure in (gx,gy), config.seed at epoch 0.
   const auto owner=hex::owner(hex::warp({(gx+0.5)*spacing+180,(gy+0.5)*spacing+180},config.seed));
   const std::uint32_t seed=regionSeed(owner.q,owner.r);
   const double px=(gx+random(seed,gx,gy,salt))*spacing;
   const double py=(gy+random(seed,gx,gy,salt+Salt::LayerJitterY))*spacing;
   if(px<minX||px>=maxX||py<minY||py>=maxY) continue;
   if(!entered_&&entrance::inZone(px,py)) continue;
   const auto surface=sample(px,py);
   if(surface.depth>0||std::abs(px-streamX(py))<streamHalfWidth(py)+0.5) continue;
   const double choice=random(seed,gx,gy,salt+Salt::LayerChoice);
   const auto ov=overlayField(*this,px,py);
   const double patch=0.5+0.5*noise(config.seed+Salt::PatchCover,px/38,py/38);
   const double routeDistance=std::abs(px-(streamX(py)-7));
   Kind kind; double scale; bool young=false; int species=static_cast<int>(Species::Pine);
   flora::Site site{surface.biome,surface.moisture,surface.slope,surface.forest,std::abs(px-streamX(py)),streamHalfWidth(py),ov.unrealWeight};
   int floraIndex=-1; double heightM=0;
   if(type==0||type==6) {
    // Canopy and subcanopy trees: a catalogue ceiling per role and family, species from the viability engine.
    const auto role=type==0?flora::Role::Canopy:flora::Role::Subcanopy;
    const double ceiling=flora::roleDensity(surface.biome,role)*ov.densityScale*(0.2+1.6*patch);
    if(choice>std::min(1.0,ceiling*spacing*spacing/100.0)||routeDistance<3.5) continue;
    if(isInsideReservation(reservations,px,py,true)) continue;
    floraIndex=flora::pick(site,role,random(seed,gx,gy,salt+Salt::LayerSpecies));
    if(floraIndex<0) continue;
    const auto& placed=flora::table()[static_cast<std::size_t>(floraIndex)];
    kind=Kind::Tree;
    const int mapped=flora::table()[static_cast<std::size_t>(placed.meshSource)].row.speciesEnum;
    species=mapped>=0?mapped:static_cast<int>(Species::Pine);
    heightM=placed.row.heightMin+(placed.row.heightMax-placed.row.heightMin)*random(seed,gx,gy,salt+Salt::LayerHeight);
    // Loose regeneration patches and a wide spread of multi-tiered cohorts.
    const double regeneration=0.5+0.5*noise(config.seed+Salt::Regeneration,px/55,py/55);
    young=random(seed,gx,gy,salt+Salt::LayerYoung)<0.11+0.28*regeneration;
    const double size=random(seed,gx,gy,salt+Salt::LayerSize);
    if(young) {
     scale=0.55+size*1.45;
    } else if(size<0.26) {
     // Understory poles and sub-canopy growth
     scale=0.42+size*1.65;
    } else if(size<0.98) {
     // Dominant mature canopy ceiling
     scale=0.86+(size-0.26)*1.40;
    } else {
     // Towering ancient giants: rare tail (size>=0.98, about 2% of non-young trees)
     scale=1.65+(size-0.98)*12.5;
     if(surface.biome[2]>0.3) scale*=(1.0-0.35*surface.biome[2]);
    }
    scale*=familyMul(surface.biome,kTreeScaleMul);
   } else if(type==1) {
    // Ground-cover flora: a ceiling per role; the role is chosen in proportion to its ceiling, then a viable species.
    // Moss (taiga carpet included) is placed only here, so each role is counted once against its ceiling.
    const std::array<flora::Role,8> groundRoles{{flora::Role::Shrub,flora::Role::Fern,flora::Role::Grass,flora::Role::Reed,flora::Role::Flower,flora::Role::Moss,flora::Role::Aquatic,flora::Role::Fungus}};
    std::array<double,8> ceilings{};
    double total=0;
    for(std::size_t g=0;g<groundRoles.size();++g) {
     ceilings[g]=flora::roleDensity(surface.biome,groundRoles[g])*ov.densityScale*(0.2+1.6*patch)*(groundRoles[g]==flora::Role::Fungus?ov.fungusScale:1.0);
     total+=ceilings[g];
    }
    // Low plants preserve an open walking strip without emptying both banks.
    const double routeCover=routeDistance<1.2?0.2:1.0;
    if(total<=0||choice>std::min(1.0,total*spacing*spacing/100.0)*routeCover) continue;
    double roleRoll=random(seed,gx,gy,salt+Salt::LayerFloraRole)*total;
    std::size_t g=0;
    while(g+1<groundRoles.size()&&roleRoll>=ceilings[g]) { roleRoll-=ceilings[g]; ++g; }
    floraIndex=flora::pick(site,groundRoles[g],random(seed,gx,gy,salt+Salt::LayerSpecies));
    if(floraIndex<0) continue;
    const auto& placed=flora::table()[static_cast<std::size_t>(floraIndex)];
    kind=placed.row.role==flora::Role::Fern?Kind::Fern:Kind::Grass;
    heightM=placed.row.heightMin+(placed.row.heightMax-placed.row.heightMin)*random(seed,gx,gy,salt+Salt::LayerHeight);
    scale=kind==Kind::Fern?(0.42+random(seed,gx,gy,salt+Salt::LayerSize)*1.65):(0.48+random(seed,gx,gy,salt+Salt::LayerSize)*2.05);
   } else if(type==3) {
    // Tallgrass prairie: dense, slightly clumped grass confined to grassland cores.
    // Savannah grass carries the prairie layer at 0.6 strength.
    // Marsh reeds: the 0.5 base core scaled x1.8 by Marsh weight (prairie clumps as reed proxy).
    // Prairie carries 1.8x the DryGrassland core so tallgrass density is at least 1.5x in pure Prairie.
    const double core=smooth((surface.biome[1]-0.65)/0.25)+0.6*surface.biome[7]+0.9*surface.biome[9]+1.8*surface.biome[11];
    const double clump=0.5+0.5*noise(config.seed+Salt::PrairieClump,px/9,py/9);
    if(core<=0||routeDistance<2.2||choice>core*(0.25+0.5*clump)) continue;
    kind=Kind::Grass;
    scale=0.7+random(seed,gx,gy,salt+Salt::LayerSize)*0.9;
   } else if(type==5) {
    // Fallen logs: one lattice cell per 100 m², kept off walking routes, streams (above) and discovery reservations.
    const double density=deadwoodDensity(surface.biome);
    if(density<=0||routeDistance<2.5||choice>density||isInsideReservation(reservations,px,py,true)) continue;
    kind=Kind::Deadwood;
    scale=0.8+random(seed,gx,gy,salt+Salt::LayerSize)*0.5;
   } else {
    // Larger rock groups occur in patches, particularly on exposed highlands.
    const double rocky=0.5+0.5*noise(config.seed+Salt::Rocky,px/24,py/24);
    const double abundance=0.045*surface.biome[0]+0.07*surface.biome[1]+0.45*surface.biome[2]+0.08*surface.biome[3]+0.05*surface.biome[4]+0.04*surface.biome[5]+0.10*surface.biome[6]+0.02*surface.biome[7]+0.045*surface.biome[8]+0.04*surface.biome[9]+0.07*surface.biome[11];
    const double streamDist=std::abs(px-streamX(py));
    const double halfW=streamHalfWidth(py);
    const double riparian=(streamDist>=halfW*0.65&&streamDist<=6.0&&routeDistance>2.2)?0.38*(0.6+0.4*noise(config.seed+Salt::Riparian,px/12,py/12)):0.0;
    const double totalAbundance=std::max(abundance*smooth((rocky-0.35)/0.35)*familyMul(surface.biome,kRockMul),riparian)*ov.densityScale;
    if(routeDistance<2.5||choice>totalAbundance) continue;
    kind=Kind::Rock;
    const double highlandBoost=surface.biome[2]>0.35?(1.2+1.5*surface.biome[2]):1.0;
    scale=((streamDist<=4.5)?(0.65+random(seed,gx,gy,salt+Salt::LayerSize)*1.5):(0.95+random(seed,gx,gy,salt+Salt::LayerSize)*2.6))*highlandBoost;
   }
   Feature feature{kind,{px,py,terrainHeight(px,py)},random(seed,gx,gy,salt+Salt::LayerYaw)*360,scale*ov.featureScale,young,type==3};
   feature.species=species;
   if(floraIndex>=0) {
    feature.flora=floraIndex;
    feature.floraMesh=flora::table()[static_cast<std::size_t>(floraIndex)].meshSource;
    feature.heightM=heightM;
    feature.tint=static_cast<int>(random(seed,gx,gy,salt+Salt::LayerTint)*4);
   }
   habitat.features.push_back(feature);
  }
 };
 layer(6.0,Salt::TreeLayer,0);
 layer(1.5,Salt::GroundCoverLayer,1);
 layer(6,Salt::RockLayer,2);
 layer(1.0,Salt::PrairieLayer,3);
 layer(10.0,Salt::DeadwoodLayer,5);
 layer(6.0,Salt::SubcanopyLayer,6);
 if(!entered_) for(auto feature:entrance::fixedFeatures()) {
  if(feature.position.x<minX||feature.position.x>=maxX||feature.position.y<minY||feature.position.y>=maxY) continue;
  feature.position.z=terrainHeight(feature.position.x,feature.position.y);
  habitat.features.push_back(feature);
 }
 return habitat;
}
// Generation pipeline, in order: region -> structure -> terrain -> hydrology -> habitat -> presentation.
// region: chunk bounds, hex owner of midpoint (Settings, x, y).
// structure: discovery reservations and pieces (region).
// terrain: vertex heights and triangles (Settings, x, y); needed even when features are skipped.
// hydrology: stream fields per terrain row (terrain).
// habitat: feature layers (region, structure, hydrology).
// presentation: assembles Chunk from terrain, habitat and structure pieces.
Chunk World::generate(int x,int y,bool includeFeatures) const {
 if(std::abs(static_cast<double>(x)*config.chunkSize)>999000||std::abs(static_cast<double>(y)*config.chunkSize)>999000)
  throw std::invalid_argument("Chunk outside supported milestone coordinates");
 const auto terrain=terrainStage(x,y);
 Chunk chunk; chunk.x=x;chunk.y=y;chunk.cells=config.cells;
 chunk.vertices=terrain.vertices; chunk.triangles=terrain.triangles;
 if(!includeFeatures) return chunk;
 const auto region=regionStage(x,y);
 const auto structure=structureStage(region);
 const auto hydrology=hydrologyStage(terrain);
 const auto habitat=habitatStage(region,structure,hydrology);
 chunk.features=habitat.features;
 for(const auto& piece:structure.pieces) {
  const double normYaw=std::fmod(std::fmod(piece.yaw,360.0)+360.0,360.0);
  const int kitId=kit::kitIdFor(piece.mesh);
  if(kitId>=0) {
   Feature feature{Kind::Kit,piece.position,normYaw,piece.scale,false};
   feature.kitId=kitId; feature.pitch=piece.pitch; feature.roll=piece.roll;
   chunk.features.push_back(feature);
   continue;
  }
  const Kind kind=(piece.mesh.find("Fern")!=std::string::npos||piece.name.find("fern")!=std::string::npos)?Kind::Fern:Kind::Rock;
  chunk.features.push_back({kind,piece.position,normYaw,piece.scale,false});
 }
 return chunk;
}
Lighting World::lighting(double x,double y,double seconds) const {
 if(!std::isfinite(seconds)) throw std::invalid_argument("Lighting time must be finite");
 if(!entered_&&entrance::inZone(x,y)) return Lighting{1.0,5600.0};
 Lighting result; double total=0;
 for(const auto& cell:cellWeights(config,x,y)) {
  if(cell.weight<=0) continue;
  const auto r=describe(*this,cell.cell.q,cell.cell.r);const double w=cell.weight;
  const auto fam=static_cast<std::size_t>(r.family);
  const double day=0.5+0.5*std::sin(seconds*2*pi/(2400+700*r.roughness)+r.phase);
  // Ordinary cells use neutral overlay values (x*1.0, x+0.0), so their output is unchanged.
  const auto p=r.unreal?unreal::params(r.overlay):unreal::params(unreal::Overlay::None);
  total+=w; result.brightness+=w*(0.18+0.82*day)*p.lightBrightness*kLightBrightnessMul[fam];
  result.kelvin+=w*(4300+900*r.exposure+1500*(1-day)+p.lightKelvinShift+kLightKelvinShift[fam]);
 }
 result.brightness/=total; result.kelvin/=total; return result;
}
unreal::OverlayField World::overlayAt(double x,double y) const {
 validatePoint(x,y);
 return overlayField(*this,x,y);
}
void Observation::sit(bool value) { seated=value; if(!value) accelerated=false; }
void Observation::accelerate(bool value) { accelerated=value&&seated; }
void Observation::advance(double value) {
 if(!std::isfinite(value)||value<0) throw std::invalid_argument("Elapsed time must be finite and nonnegative");
 seconds+=value*rate();
}
double Observation::rate() const { return seated&&accelerated?20:1; }
}
