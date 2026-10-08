#include "Generation/WoodGeneration.h"
#include "Generation/WoodSalts.h"
#include "Generation/WoodHex.h"
#include "Generation/WoodDiscovery.h"
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
Region describe(const Settings& c,int gx,int gy) {
 Region r;
 r.identity=hash(c.seed,gx,gy,Salt::RegionIdentity);
 const auto center=hex::center({gx,gy});
 r.origin={center.x-180,center.y-180,0};r.q=gx;r.r=gy;r.extent=hex::radius*2;
 r.family=static_cast<Biome>(hash(c.seed,gx,gy,Salt::RegionFamily)%4);
 if(gx==0&&gy==0) r.family=Biome::TemperateForest;
 if((gx==1&&gy==0)||(gx==0&&gy==1)) r.family=Biome::DryGrassland;
 if((gx==1&&gy==1)||(gx==1&&gy==-1)) r.family=Biome::RockyHighlands;
 if(gx==0&&gy==-1) r.family=Biome::Taiga;
 if(gx==-1&&gy==0) r.family=Biome::TemperateForest;
 const auto i=static_cast<std::size_t>(r.family);
 constexpr double moisture[]={0.78,0.24,0.38,0.58};
 constexpr double roughness[]={0.22,0.16,0.85,0.36};
 constexpr double temperature[]={16,24,8,-3};
 constexpr double canopy[]={0.96,0.055,0.09,0.70};
 constexpr double exposure[]={0.18,0.86,0.94,0.38};
 r.moisture=moisture[i]; r.roughness=roughness[i]; r.temperature=temperature[i];
 r.canopy=canopy[i]; r.exposure=exposure[i]; r.shelter=1-r.exposure;
 r.phase=random(c.seed,gx,gy,Salt::RegionPhase)*2*pi;
 return r;
}
auto cellWeights(const Settings& c,double x,double y) {return hex::weights(hex::warp({x+180,y+180},c.seed));}
Surface climate(const Settings& c,double x,double y) {
 Surface s; double total=0;
 for(const auto& cell:cellWeights(c,x,y)) {
  if(cell.weight<=0) continue;
  const auto r=describe(c,cell.cell.q,cell.cell.r);const double w=cell.weight;
  total+=w; s.biome[static_cast<std::size_t>(r.family)]+=w;
  s.forest+=w*r.canopy; s.moisture+=w*r.moisture;
  s.temperature+=w*r.temperature; s.exposure+=w*r.exposure;
  s.shelter+=w*r.shelter; s.roughness+=w*r.roughness;
 }
 for(auto& w:s.biome) w/=total;
 s.forest/=total; s.moisture/=total; s.temperature/=total;
 s.exposure/=total; s.shelter/=total; s.roughness/=total;
 return s;
}
double waterLevel(double y) { return 8-0.018*y; }
double channelHalfWidth(const Settings& c,double y) {
 return 1.4+0.5*(1+noise(c.seed+Salt::ChannelWidth,0,y/160));
}
double ground(const Settings& c,double x,double y,double stream,const Surface* cachedClimate=nullptr) {
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
 const auto regionClimate=cachedClimate?*cachedClimate:climate(c,x,y);
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

 const double base=water+3.0+broad+detail+valleyWall+mountainMass+crags+prairie;
 return bank+(base-bank)*smooth((distance-10.0)/25.0);
}
}
World::World(Settings settings):config(settings) {
 if(!std::isfinite(config.chunkSize)||config.chunkSize<=0||config.cells<2||config.cells>256)
  throw std::invalid_argument("Chunk size must be positive and cells must be between 2 and 256");
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
 if(std::abs(x-streamX(y))>=2.0*streamHalfWidth(y)) return 0;
 return std::max(0.0,waterLevel(y)-ground(config,x,y,streamX(y)));
}
Surface World::sample(double x,double y) const {
 validatePoint(x,y);
 Surface s=climate(config,x,y);
 s.height=ground(config,x,y,streamX(y),&s);
 const double dx=(ground(config,x+0.25,y,streamX(y))-ground(config,x-0.25,y,streamX(y)))/0.5;
 const double dy=(ground(config,x,y+0.25,streamX(y+0.25))-ground(config,x,y-0.25,streamX(y-0.25)))/0.5;
 s.slope=std::hypot(dx,dy);
 s.waterHeight=waterLevel(y);
 s.depth=std::abs(x-streamX(y))<streamHalfWidth(y)?std::max(0.0,s.waterHeight-s.height):0;
 s.moisture=std::clamp(s.moisture+0.25*std::exp(-std::abs(x-streamX(y))/12),0.0,1.0);
 return s;
}
Region World::region(int latticeX,int latticeY) const {
 if(std::abs(static_cast<double>(latticeX))>835||std::abs(static_cast<double>(latticeY))>835)
  throw std::invalid_argument("Region outside supported milestone coordinates");
 return describe(config,latticeX,latticeY);
}
std::vector<Region> World::regions(double x,double y) const {
 validatePoint(x,y); std::vector<Region> result;
 for(const auto& cell:cellWeights(config,x,y)) if(cell.weight>0) result.push_back(describe(config,cell.cell.q,cell.cell.r));
 return result;
}
double World::terrainHeight(double x,double y) const {
 validatePoint(x,y);
 const double spacing=config.chunkSize/config.cells;
 const double cellX=std::floor(x/spacing),cellY=std::floor(y/spacing);
 const double x0=cellX*spacing,y0=cellY*spacing,u=x/spacing-cellX,v=y/spacing-cellY;
 const double a=ground(config,x0,y0,streamX(y0));
 const double b=ground(config,x0+spacing,y0,streamX(y0));
 const double c=ground(config,x0,y0+spacing,streamX(y0+spacing));
 if(u+v<=1) return a+(b-a)*u+(c-a)*v;
 const double d=ground(config,x0+spacing,y0+spacing,streamX(y0+spacing));
 return d+(c-d)*(1-u)+(b-d)*(1-v);
}
Chunk World::generate(int x,int y,bool includeFeatures) const {

 if(std::abs(static_cast<double>(x)*config.chunkSize)>999000||std::abs(static_cast<double>(y)*config.chunkSize)>999000)
  throw std::invalid_argument("Chunk outside supported milestone coordinates");
 Chunk chunk; chunk.x=x;chunk.y=y;chunk.cells=config.cells;
 const int n=config.cells;
 for(int row=0;row<=n;++row) for(int col=0;col<=n;++col) {
  const double px=(x+static_cast<double>(col)/n)*config.chunkSize, py=(y+static_cast<double>(row)/n)*config.chunkSize;
  chunk.vertices.push_back({px,py,ground(config,px,py,streamX(py))});
 }
 for(int row=0;row<n;++row) for(int col=0;col<n;++col) {
  const auto i=static_cast<std::uint32_t>(row*(n+1)+col), stride=static_cast<std::uint32_t>(n+1);
  chunk.triangles.insert(chunk.triangles.end(),{i,i+stride,i+1,i+1,i+stride,i+stride+1});
 }
 if(!includeFeatures) return chunk;
 const double minX=x*config.chunkSize,minY=y*config.chunkSize;
 const double maxX=(x+1)*config.chunkSize,maxY=(y+1)*config.chunkSize;
 const double midX=(minX+maxX)*0.5,midY=(minY+maxY)*0.5;
 const auto owner=hex::owner(hex::warp({midX+180,midY+180},config.seed));
 auto heightFn=[this](double hx,double hy){return terrainHeight(hx,hy);};
 auto streamXFn=[this](double sy){return streamX(sy);};
 auto streamHWFn=[this](double sy){return streamHalfWidth(sy);};

 std::vector<DiscoveryReservation> reservations;
 std::vector<DiscoveryPiece> chunkPieces;

 for(int dy=-2;dy<=2;++dy) for(int dx=-2;dx<=2;++dx) {
  if(std::max({std::abs(dx),std::abs(dy),std::abs(dx+dy)})>2) continue;
  const int col=owner.q+dx,row=owner.r+dy;
  const auto r=describe(config,col,row);
  const Vec3 cellCenter{r.origin.x,r.origin.y,terrainHeight(r.origin.x,r.origin.y)};
  const auto cellClimate=sample(r.origin.x,r.origin.y);
  const auto plan=planDiscovery(config.seed,col,row,cellCenter,cellClimate,heightFn,streamXFn,streamHWFn);
  if(!plan.valid) continue;
  if(plan.reservation.innerRadius>0.0||plan.reservation.outerRadius>0.0) {
   reservations.push_back(plan.reservation);
  }
  for(const auto& piece:plan.pieces) {
   if(piece.position.x>=minX&&piece.position.x<maxX&&piece.position.y>=minY&&piece.position.y<maxY) {
    chunkPieces.push_back(piece);
   }
  }
 }

 // Independent global lattices keep layers dense and chunk ownership unambiguous.
 // Full-cell jitter and broad habitat patches conceal the underlying lattice.
 auto layer=[&](double spacing,std::uint32_t salt,int type) {
  const int firstX=static_cast<int>(std::floor(minX/spacing)),firstY=static_cast<int>(std::floor(minY/spacing));
  const int endX=static_cast<int>(std::ceil(maxX/spacing)),endY=static_cast<int>(std::ceil(maxY/spacing));
  for(int gy=firstY;gy<endY;++gy) for(int gx=firstX;gx<endX;++gx) {
   const double px=(gx+random(config.seed,gx,gy,salt))*spacing;
   const double py=(gy+random(config.seed,gx,gy,salt+Salt::LayerJitterY))*spacing;
   if(px<minX||px>=maxX||py<minY||py>=maxY) continue;
   const auto surface=sample(px,py);
   if(surface.depth>0||std::abs(px-streamX(py))<streamHalfWidth(py)+0.5) continue;
   const double choice=random(config.seed,gx,gy,salt+Salt::LayerChoice);
   const double patch=0.5+0.5*noise(config.seed+Salt::PatchCover,px/38,py/38);
   const double routeDistance=std::abs(px-(streamX(py)-7));
   Kind kind; double scale; bool young=false;
   if(type==0) {
    // Dynamic groves and sunlit clearings interrupt the temperate and taiga canopies.
    const double grove=smooth((patch-0.26)/0.36);
    const double density=surface.forest*(0.04+0.78*grove);
    if(surface.slope>=0.7||routeDistance<3.5||choice>density) continue;
    if(isInsideReservation(reservations,px,py,true)) continue;
    kind=Kind::Tree;
    // Loose regeneration patches and a wide spread of multi-tiered cohorts.
    const double regeneration=0.5+0.5*noise(config.seed+Salt::Regeneration,px/55,py/55);
    young=random(config.seed,gx,gy,salt+Salt::LayerYoung)<0.11+0.28*regeneration;
    const double size=random(config.seed,gx,gy,salt+Salt::LayerSize);
    if(young) {
     scale=0.55+size*1.45;
    } else if(size<0.26) {
     // Understory poles and sub-canopy growth
     scale=0.42+size*1.65;
    } else if(size<0.82) {
     // Dominant mature canopy ceiling
     scale=0.86+(size-0.26)*1.40;
    } else {
     // Towering ancient giants
     scale=1.65+(size-0.82)*4.2;
     if(surface.biome[2]>0.3) scale*=(1.0-0.35*surface.biome[2]);
    }
   } else if(type==1) {
    if(surface.slope>=0.7) continue;
    // Two spatial scales form dense colonies separated by leaf-litter pockets.
    const double colony=smooth((0.5+0.5*noise(config.seed+Salt::Colony,px/11,py/11)-0.28)/0.40);
    const double habitatCover=surface.biome[0]+0.80*surface.biome[1]+0.30*surface.biome[2]+0.55*surface.biome[3];
    const double cover=(0.10+0.84*colony)*habitatCover;
    // Low plants preserve an open walking strip without emptying both banks.
    const double routeCover=routeDistance<1.2?0.20:1.0;
    if(choice>cover*routeCover) continue;
    const double fernChance=surface.moisture*(surface.biome[0]*(0.70+0.65*colony)+
                                                0.04*surface.biome[1]+0.08*surface.biome[2]+0.15*surface.biome[3]);
    kind=random(config.seed,gx,gy,salt+Salt::LayerFernChance)<fernChance?Kind::Fern:Kind::Grass;
    const double streamDist=std::abs(px-streamX(py));
    if(streamDist>=streamHalfWidth(py)+0.6&&streamDist<=5.0&&routeDistance>2.2&&random(config.seed,gx,gy,salt+Salt::LayerRockChance)<0.22) {
     kind=Kind::Rock;
     scale=0.55+random(config.seed,gx,gy,salt+Salt::LayerSize)*0.9;
    } else {
     scale=kind==Kind::Fern?(0.42+random(config.seed,gx,gy,salt+Salt::LayerSize)*1.65)*(1-0.25*surface.biome[3]):
                           (0.48+random(config.seed,gx,gy,salt+Salt::LayerSize)*2.05)*(1-0.45*surface.biome[2]);
    }
   } else if(type==3) {
    // Tallgrass prairie: dense, slightly clumped grass confined to grassland cores.
    const double core=smooth((surface.biome[1]-0.65)/0.25);
    const double clump=0.5+0.5*noise(config.seed+Salt::PrairieClump,px/9,py/9);
    if(core<=0||routeDistance<2.2||choice>core*(0.25+0.5*clump)) continue;
    kind=Kind::Grass;
    scale=0.7+random(config.seed,gx,gy,salt+Salt::LayerSize)*0.9;
   } else {
    // Larger rock groups occur in patches, particularly on exposed highlands.
    const double rocky=0.5+0.5*noise(config.seed+Salt::Rocky,px/24,py/24);
    const double abundance=0.045*surface.biome[0]+0.07*surface.biome[1]+0.45*surface.biome[2]+0.08*surface.biome[3];
    const double streamDist=std::abs(px-streamX(py));
    const double halfW=streamHalfWidth(py);
    const double riparian=(streamDist>=halfW*0.65&&streamDist<=6.0&&routeDistance>2.2)?0.38*(0.6+0.4*noise(config.seed+Salt::Riparian,px/12,py/12)):0.0;
    const double totalAbundance=std::max(abundance*smooth((rocky-0.35)/0.35),riparian);
    if(routeDistance<2.5||choice>totalAbundance) continue;
    kind=Kind::Rock;
    const double highlandBoost=surface.biome[2]>0.35?(1.2+1.5*surface.biome[2]):1.0;
    scale=((streamDist<=4.5)?(0.65+random(config.seed,gx,gy,salt+Salt::LayerSize)*1.5):(0.95+random(config.seed,gx,gy,salt+Salt::LayerSize)*2.6))*highlandBoost;
   }
   chunk.features.push_back({kind,{px,py,terrainHeight(px,py)},random(config.seed,gx,gy,salt+Salt::LayerYaw)*360,scale,young});
  }
 };
 layer(8.5,Salt::TreeLayer,0);
 layer(1.5,Salt::GroundCoverLayer,1);
 layer(6,Salt::RockLayer,2);
 layer(1.0,Salt::PrairieLayer,3);
 for(const auto& piece:chunkPieces) {
  const Kind kind=(piece.mesh.find("Fern")!=std::string::npos||piece.name.find("fern")!=std::string::npos)?Kind::Fern:Kind::Rock;
  const double normYaw=std::fmod(std::fmod(piece.yaw,360.0)+360.0,360.0);
  chunk.features.push_back({kind,piece.position,normYaw,piece.scale,false});
 }
 return chunk;
}
Lighting World::lighting(double x,double y,double seconds) const {
 if(!std::isfinite(seconds)) throw std::invalid_argument("Lighting time must be finite");
 Lighting result; double total=0;
 for(const auto& cell:cellWeights(config,x,y)) {
  if(cell.weight<=0) continue;
  const auto r=describe(config,cell.cell.q,cell.cell.r);const double w=cell.weight;
  const double day=0.5+0.5*std::sin(seconds*2*pi/(2400+700*r.roughness)+r.phase);
  total+=w; result.brightness+=w*(0.18+0.82*day);
  result.kelvin+=w*(4300+900*r.exposure+1500*(1-day));
 }
 result.brightness/=total; result.kelvin/=total; return result;
}
void Observation::sit(bool value) { seated=value; if(!value) accelerated=false; }
void Observation::accelerate(bool value) { accelerated=value&&seated; }
void Observation::advance(double value) {
 if(!std::isfinite(value)||value<0) throw std::invalid_argument("Elapsed time must be finite and nonnegative");
 seconds+=value*rate();
}
double Observation::rate() const { return seated&&accelerated?20:1; }
}
