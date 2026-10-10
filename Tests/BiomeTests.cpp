#include "Generation/WoodGeneration.h"
#include "Generation/WoodFlora.h"
#include <algorithm>
#include <cmath>
#include <iostream>
#include <utility>
#include <vector>
int failures=0;
void check(bool ok,const char* text) { if(!ok) { ++failures; if(failures<25) std::cerr<<"FAIL: "<<text<<'\n'; } }
int main() {
 using namespace wood;
 for(unsigned seed:{0u,42u,98765u}) {
  World world({seed,128,64});
  // Removing two-dimensional climatic variation must break this contract.
  const auto south=world.sample(-180,-180),north=world.sample(-180,985);
  check(std::abs(south.moisture-north.moisture)>0.15,"northward travel discovers a different climate at the same x");
  check(south.forest>0.65,"journey starts in sheltered mature woodland");
 }
 for(unsigned seed:{0u,42u,98765u}) {
  World world({seed,128,64});
  // Starter neighbourhood holds the four explicit families; OldGrowth and ColdRainforest are climate-driven.
  const int coords[4][2]={{0,0},{1,0},{1,1},{0,-1}};
  std::array<std::size_t,kFamilyCount> trees{},ferns{},rocks{},cover{},canopy{};
  for(int family=0;family<4;++family) {
   const auto r=world.region(coords[family][0],coords[family][1]);
   const auto s=world.sample(r.origin.x,r.origin.y);
   const auto again=world.region(coords[family][0],coords[family][1]);
   check(r.identity==again.identity&&r.origin.x==again.origin.x&&r.origin.y==again.origin.y&&r.phase==again.phase,"regional identities and origins repeat without query history");
   check(static_cast<int>(r.family)==family,"starter neighborhood includes four explicit families");
   check(s.biome[family]>0.65,"each regional origin preserves its ecological identity");
   check(r.extent>1000&&r.extent<3000,"regional influence spans walking-scale terrain");
   const int cx=static_cast<int>(std::floor(r.origin.x/128)),cy=static_cast<int>(std::floor(r.origin.y/128));
   // Canopy window: 5x5 chunks (640 m) centred on the family core chunk nearest the origin (720 m regions outgrow one chunk).
   {
    int coreX=cx,coreY=cy;
    bool found=false;
    for(int dy=-1;dy<=1&&!found;++dy) for(int dx=-1;dx<=1&&!found;++dx)
     if(world.sample((cx+dx)*128+64.0,(cy+dy)*128+64.0).biome[family]>=0.9) { coreX=cx+dx; coreY=cy+dy; found=true; }
    for(int dy=-2;dy<=2;++dy) for(int dx=-2;dx<=2;++dx)
     for(const auto& f:world.generate(coreX+dx,coreY+dy).features) canopy[family]+=f.kind==Kind::Tree;
   }
   const auto chunk=world.generate(cx,cy),repeat=world.generate(cx,cy);
   const auto east=world.generate(cx+1,cy);
   for(int row=0;row<=64;++row)
    check(chunk.vertices[row*65+64].z==east.vertices[row*65].z,"regional terrain edges agree across all four habitat families");
   check(chunk.features.size()==repeat.features.size(),"far regional placement repeats independently of query order");
   for(std::size_t i=0;i<chunk.features.size();++i) {
    const auto& f=chunk.features[i]; const auto& other=repeat.features[i];
    check(f.kind==other.kind&&f.position.x==other.position.x&&f.position.y==other.position.y&&f.position.z==other.position.z,"far regional feature records remain deterministic");
    {
     const double terrainZ=world.terrainHeight(f.position.x,f.position.y);
     if(f.kind==Kind::Kit) {
      // Structural kit pieces bed 0.10-0.25 m into terrain; they may not float above it.
      check(f.position.z<=terrainZ+1e-6 && terrainZ-f.position.z<=0.25,"structural kit meets realized terrain (bedded, not floating)");
     } else {
      check(std::abs(f.position.z-terrainZ)<1e-9,"every ecological layer meets realized terrain");
     }
    }
    trees[family]+=f.kind==Kind::Tree; ferns[family]+=f.kind==Kind::Fern;
    rocks[family]+=f.kind==Kind::Rock; cover[family]+=f.kind==Kind::Grass||f.kind==Kind::Fern;
   }
  }
  // 720 m regions: measured highland canopy 2.3-3.0x below temperate woodland (5x5 window); grassland 7-10x below.
  check(canopy[0]>canopy[1]*3&&canopy[0]>canopy[2]*2,"dry and highland regions have open canopies");
  check(ferns[0]>ferns[1]*3&&ferns[0]>ferns[3]*2,"moist temperate woodland has richer ferns than grassland and taiga");
  check(rocks[2]>rocks[0]*2,"rocky highlands contain denser stone groups");
  // F1: catalogue ceilings give highlands more total ground cover than woodland (grass 12 vs 6 per 100 m2), so the
  // assertion is on fern-kind placement, which the catalogue makes sparser in highlands (fern 0.5 vs 4).
  check(ferns[2]<ferns[0],"highland fern placement is sparser than moist woodland");
  std::cout<<"Biome seed "<<seed<<" canopy "<<canopy[0]<<","<<canopy[1]<<","<<canopy[2]<<","<<canopy[3];
  for(int i=0;i<kFamilyCount;++i) std::cout<<" ["<<trees[i]<<" trees,"<<ferns[i]<<" ferns,"<<rocks[i]<<" rocks,"<<cover[i]<<" cover]";
  std::cout<<'\n';
  for(double y:{-98000.0,-3600.0,-180.0,600.0,3300.0,97500.0}) for(double x:{-98200.0,-2400.0,-180.0,600.0,5100.0,98400.0}) {
   const auto s=world.sample(x,y),repeat=world.sample(x,y),next=world.sample(x+0.05,y+0.05);
   double sum=0;
   for(int i=0;i<kFamilyCount;++i) {
    sum+=s.biome[i]; check(s.biome[i]>=0&&s.biome[i]<=1,"biome weights are bounded");
    check(s.biome[i]==repeat.biome[i],"climate queries remain deterministic at far negative and positive coordinates");
    check(std::abs(s.biome[i]-next.biome[i])<0.001,"regional weights blend continuously");
   }
   check(std::abs(sum-1)<1e-12,"neighbor influences form a normalized partition");
   check(std::abs(s.moisture-next.moisture)<0.002&&std::abs(s.temperature-next.temperature)<0.01,"climate has no abrupt boundary changes");
   check(!world.regions(x,y).empty(),"every supported coordinate has neighboring regional influences");
  }
  // Each descriptor's independent lighting cycle must participate in the blend.
  const double lightX=600,lightY=580,seconds=700;
  double weight=0,brightness=0,kelvin=0;
  for(const auto& r:world.regions(lightX,lightY)) {
   const double dx=lightX-r.origin.x,dy=lightY-r.origin.y;
   const double q=std::max(0.0,1-(dx*dx+dy*dy)/(1550.0*1550.0));
   const double w=q*q*q*q;
   const double period=2400+700*r.roughness;
   const double day=0.5+0.5*std::sin(seconds*2*3.14159265358979323846/period+r.phase);
   weight+=w; brightness+=w*(0.18+0.82*day);
   kelvin+=w*(4300+900*r.exposure+1500*(1-day));
  }
  const auto light=world.lighting(lightX,lightY,seconds);
  check(std::abs(light.brightness-brightness/weight)<1e-12&&std::abs(light.kelvin-kelvin/weight)<1e-9,"lighting blends independent regional phase and cycle inputs");
  const auto fullChunk=world.generate(-1,2),terrainOnly=world.generate(-1,2,false);
  check(terrainOnly.features.empty(),"terrain-only requests skip all habitat placement");
  check(fullChunk.triangles==terrainOnly.triangles&&fullChunk.vertices.size()==terrainOnly.vertices.size(),"terrain-only requests preserve indexed topology");
  for(std::size_t i=0;i<fullChunk.vertices.size();++i)
   check(fullChunk.vertices[i].x==terrainOnly.vertices[i].x&&fullChunk.vertices[i].y==terrainOnly.vertices[i].y&&fullChunk.vertices[i].z==terrainOnly.vertices[i].z,"terrain-only requests preserve exact ground vertices");
  double minWidth=3,maxWidth=0;
  for(int y=-4000;y<=4000;y+=7) {
   const double width=world.streamHalfWidth(y);
   minWidth=std::min(minWidth,width); maxWidth=std::max(maxWidth,width);
   check(width>=1.4&&width<=2.4,"stream width stays within the intended gentle-rill range");
   check(width==world.streamHalfWidth(y),"stream width repeats without sampling history");
   check(std::abs(world.streamHalfWidth(y+1)-width)<0.015,"stream width changes gently along its connected channel");
   for(double bank:{-1.,0.,1.}) {
    const double x=world.streamX(y)+bank*width*0.92;
    const auto wet=world.sample(x,y);
    check(wet.depth>0&&wet.depth<0.65,"water ribbon stays wet and shallow across varying width");
    check(world.terrainHeight(x,y)<wet.waterHeight-0.005,"rendered water ribbon lies above actual terrain triangles");
   }
   const auto outside=world.sample(world.streamX(y)+width+0.1,y);
   check(outside.depth==0,"depth query uses the same channel width as water presentation");
  }
  check(maxWidth-minWidth>0.5,"stream width visibly varies rather than remaining constant");
  for(int y=-12000;y<=12000;y+=83) {
   const auto channel=world.sample(world.streamX(y),y),route=world.sample(world.streamX(y)-7,y);
   check(channel.depth>0&&channel.depth<0.65,"stream stays shallow and connected across distant regions");
   check(route.slope<0.7,"reserved bank route remains traversable in all families");
  }
  for(int cy:{-25,-1,0,19}) for(int cx:{-21,-1,0,23}) {
   const auto chunk=world.generate(cx,cy);
   for(int row=0;row<64;row+=13) for(int col=0;col<64;col+=11) for(double u:{0.2,0.8}) for(double v:{0.2,0.8}) {
    const auto& a=chunk.vertices[row*65+col]; const auto& b=chunk.vertices[row*65+col+1];
    const auto& c=chunk.vertices[(row+1)*65+col]; const auto& d=chunk.vertices[(row+1)*65+col+1];
    const double expected=u+v<=1?a.z+(b.z-a.z)*u+(c.z-a.z)*v:
                                  d.z+(c.z-d.z)*(1-u)+(b.z-d.z)*(1-v);
    check(std::abs(world.terrainHeight(a.x+2*u,a.y+2*v)-expected)<1e-9,"ground query follows both actual mesh triangles including negative cells");
   }
  }
 }
 {
  wood::World world({42,128,64});double minTree=100,maxTree=0,minFern=100,maxFern=0;int trees=0,young=0;
  for(int y=-3;y<=1;++y) for(int x=-3;x<=1;++x) for(const auto& f:world.generate(x,y).features) {
   if(f.kind==wood::Kind::Tree) {++trees;young+=f.young;minTree=std::min(minTree,f.scale);maxTree=std::max(maxTree,f.scale);}
   if(f.kind==wood::Kind::Fern) {minFern=std::min(minFern,f.scale);maxFern=std::max(maxFern,f.scale);}
  }
  check(young>trees/10&&young<trees/2,"young and established tree cohorts coexist");
  check(minTree<.5&&maxTree>1.2,"trees include intermediate and mature sizes");
  check(minFern<.6&&maxFern>1.5,"understory includes small new growth and full sized plants");
 }
 {
  // Grassland core density: grass lattice count inside a 100 m x 100 m square centred on the grassland origin.
  World world({98765,128,64});
  const auto g=world.region(1,0);
  const double half=50.0;
  const int cx0=static_cast<int>(std::floor((g.origin.x-half)/128)),cx1=static_cast<int>(std::floor((g.origin.x+half)/128));
  const int cy0=static_cast<int>(std::floor((g.origin.y-half)/128)),cy1=static_cast<int>(std::floor((g.origin.y+half)/128));
  std::size_t grass=0;
  for(int cy=cy0;cy<=cy1;++cy) for(int cx=cx0;cx<=cx1;++cx)
   for(const auto& f:world.generate(cx,cy).features) {
    if(f.kind!=Kind::Grass) continue;
    if(std::abs(f.position.x-g.origin.x)>half||std::abs(f.position.y-g.origin.y)>half) continue;
    ++grass;
   }
  const double grassPer100=grass*100.0/((2*half)*(2*half));
  // Pre-change baseline measured on seed 98765 before the prairie layer: 15.59 grass per 100 m2 (raw 1559).
  const double grassBaseline=15.59;
  std::cout<<"Grassland core grass per 100 m2: "<<grassPer100<<" (raw "<<grass<<")\n";
  check(world.sample(g.origin.x,g.origin.y).biome[1]>0.65,"grassland core origin is grassland-dominant");
  check(grassPer100>=3.5*grassBaseline,"grassland core grass density is at least 3.5x the pre-change baseline");
 }
 {
  // Spec lighting continuity: 3 km straight walk (y=0, x=-1500..1500) sampled every 1 m at two fixed times.
  wood::World world({42,128,64});
  const int samples=3001;
  const double x0=-1500.0,y0=0.0;
  auto regionKey=[&](double x,double y) {
   std::vector<std::pair<double,double>> key;
   for(const auto& r:world.regions(x,y)) key.emplace_back(r.origin.x,r.origin.y);
   std::sort(key.begin(),key.end());
   return key;
  };
  std::size_t boundaries=0;
  for(int i=1;i<samples;++i) boundaries+=regionKey(x0+i,y0)!=regionKey(x0+i-1,y0);
  double maxEV=0,maxKelvin=0;
  for(const double seconds:{200.0,1650.0}) {
   std::vector<double> ev(samples),kelvin(samples);
   for(int i=0;i<samples;++i) {
    const auto l=world.lighting(x0+i,y0,seconds);
    ev[i]=std::log2(l.brightness); kelvin[i]=l.kelvin;
   }
   for(int i=0;i+10<samples;++i) {
    maxEV=std::max(maxEV,std::abs(ev[i+10]-ev[i]));
    maxKelvin=std::max(maxKelvin,std::abs(kelvin[i+10]-kelvin[i]));
   }
  }
  std::cout<<"Lighting walk: region boundaries "<<boundaries<<", max dEV/10m "<<maxEV<<", max dKelvin/10m "<<maxKelvin<<'\n';
  check(boundaries>=2,"lighting walk crosses at least two region boundaries");
  // 0.25 EV per 10 m = ~0.1 EV/s at the 420 cm/s walk speed: a gradual drift auto-exposure absorbs, not a visible jump.
  check(maxEV<=0.25,"exposure drifts at most 0.25 EV per 10 m walking (~0.1 EV/s), no exposure jumps");
  check(maxKelvin<=150,"colour temperature changes at most 150 K per 10 m walking");
 }
 {
  // Taiga core low cover: grass plus fern count inside a 100 m x 100 m square centred on the taiga origin.
  World world({98765,128,64});
  const auto t=world.region(0,-1);
  const double half=50.0;
  const int cx0=static_cast<int>(std::floor((t.origin.x-half)/128)),cx1=static_cast<int>(std::floor((t.origin.x+half)/128));
  const int cy0=static_cast<int>(std::floor((t.origin.y-half)/128)),cy1=static_cast<int>(std::floor((t.origin.y+half)/128));
  std::size_t cover=0;
  for(int cy=cy0;cy<=cy1;++cy) for(int cx=cx0;cx<=cx1;++cx)
   for(const auto& f:world.generate(cx,cy).features) {
    if(f.kind!=Kind::Grass&&f.kind!=Kind::Fern) continue;
    if(std::abs(f.position.x-t.origin.x)>half||std::abs(f.position.y-t.origin.y)>half) continue;
    ++cover;
   }
  const double coverPer100=cover*100.0/((2*half)*(2*half));
  // Catalogue ground-cover ceiling for pure Taiga (Shrub, Fern, Grass, Reed, Flower, Aquatic, Moss, Fungus; all counted as Grass/Fern kinds).
  // Moss is routed through the ground-cover layer only, so cover is judged against the ceiling, not a carpet multiple.
  double catalogueCover=0;
  for(const auto role:{flora::Role::Shrub,flora::Role::Fern,flora::Role::Grass,flora::Role::Reed,flora::Role::Flower,flora::Role::Aquatic,flora::Role::Moss,flora::Role::Fungus})
   catalogueCover+=flora::kRoleDensity[3][static_cast<std::size_t>(role)];
  std::cout<<"Taiga core cover per 100 m2: "<<coverPer100<<" (raw "<<cover<<"), catalogue ground-cover ceiling "<<catalogueCover<<"\n";
  check(world.sample(t.origin.x,t.origin.y).biome[3]>0.65,"taiga core origin is taiga-dominant");
  check(coverPer100>=0.5*catalogueCover,"taiga core cover is at least half the catalogue ground-cover ceiling");
 }
 // T1c: tree species shares and deadwood by family core. A core chunk has its centre weight >= 0.9 in one family.
 {
  const auto coreChunks=[](const World& w,Biome family) {
   std::vector<std::pair<int,int>> out;
   const auto index=static_cast<std::size_t>(family);
   for(int cy=-20;cy<20;++cy) for(int cx=-20;cx<20;++cx)
    if(w.sample(cx*128+64.0,cy*128+64.0).biome[index]>=0.9) out.push_back({cx,cy});
   return out;
  };
  // F1: every placed tree is a flora species with catalogue weight in the core's family; no species outside viability.
  const Biome treeFamilies[]={Biome::TemperateForest,Biome::OldGrowthForest};
  for(const Biome family:treeFamilies) {
   std::size_t trees=0,outside=0;
   std::array<std::size_t,flora::kFloraCount> counts{};
   // Viability at the tree's own site (the same gate placement uses). Family weight alone is too strict: blended cores admit neighbour-family species.
   const auto viableAt=[](const World& w,const auto& f) {
    const auto site=w.sample(f.position.x,f.position.y);
    flora::Site local;
    local.biome=site.biome; local.moisture=site.moisture; local.slope=site.slope; local.forest=site.forest;
    local.streamDist=std::abs(f.position.x-w.streamX(f.position.y)); local.halfWidth=w.streamHalfWidth(f.position.y);
    const auto& s=flora::table()[static_cast<std::size_t>(f.flora)];
    return flora::viable(s,local,s.row.role);
   };
   for(unsigned seed:{0u,42u,98765u}) {
    World world({seed,128,64});
    const auto cores=coreChunks(world,family);
    for(std::size_t k=0;k<cores.size()&&k<4;++k)
     for(const auto& f:world.generate(cores[k].first,cores[k].second).features) {
      if(f.kind!=Kind::Tree) continue;
      ++trees;
      if(f.flora<0||!viableAt(world,f)) ++outside;
      else ++counts[static_cast<std::size_t>(f.flora)];
     }
   }
   std::size_t distinct=0;
   for(const auto c:counts) distinct+=c>0?1:0;
   check(trees>=500,"species sample holds at least 500 trees per family core");
   check(outside==0,"every placed tree is a flora species viable in its family");
   check(distinct>=2,"family core places at least two tree species");
  }
  std::size_t oldGrowthChunks=0,oldGrowthLogs=0,dryChunks=0,dryLogs=0;
  for(unsigned seed:{0u,42u,98765u}) {
   World world({seed,128,64});
   const auto oldCores=coreChunks(world,Biome::OldGrowthForest);
   for(std::size_t k=0;k<oldCores.size()&&k<4;++k) {
    ++oldGrowthChunks;
    for(const auto& f:world.generate(oldCores[k].first,oldCores[k].second).features) oldGrowthLogs+=f.kind==Kind::Deadwood;
   }
   const auto dryCores=coreChunks(world,Biome::DryGrassland);
   for(std::size_t k=0;k<dryCores.size()&&k<4;++k) {
    ++dryChunks;
    // Pure core only: a log at a position with any other family weight carries that family's (small) density.
    for(const auto& f:world.generate(dryCores[k].first,dryCores[k].second).features) {
     if(f.kind!=Kind::Deadwood) continue;
     if(world.sample(f.position.x,f.position.y).biome[static_cast<std::size_t>(Biome::DryGrassland)]>=0.999) ++dryLogs;
    }
   }
  }
  check(oldGrowthChunks>0,"OldGrowth core chunks exist in the sampled window");
  check(oldGrowthLogs>0,"deadwood present in OldGrowth core");
  check(dryChunks>0,"DryGrassland core chunks exist in the sampled window");
  check(dryLogs==0,"deadwood absent from DryGrassland core");
  std::cout<<"Deadwood core logs: OldGrowth "<<oldGrowthLogs<<" over "<<oldGrowthChunks<<" chunks, DryGrassland "<<dryLogs<<" over "<<dryChunks<<" chunks\n";
 }
 {
  // Prairie: moister half of the DryGrassland window. Tall grass >=1.5x DryGrassland, broadleaf <=0.2x TemperateForest, continuous border.
  // Located through hex region centres (bounded lattice scan, heap vectors only), not a dense world-sample grid.
  const auto coreChunks=[](const World& w,Biome family) {
   std::vector<std::pair<int,int>> out;
   const auto index=static_cast<std::size_t>(family);
   for(int q=-10;q<=10;++q) for(int r=-10;r<=10;++r) {
    const auto reg=w.region(q,r);
    if(reg.family!=family) continue;
    const int cx=static_cast<int>(std::floor(reg.origin.x/128)),cy=static_cast<int>(std::floor(reg.origin.y/128));
    for(int dy=-1;dy<=1;++dy) for(int dx=-1;dx<=1;++dx)
     if(w.sample((cx+dx)*128+64.0,(cy+dy)*128+64.0).biome[index]>=0.9) { out.push_back({cx+dx,cy+dy}); dx=2; dy=2; }
   }
   return out;
  };
  const auto p=static_cast<std::size_t>(Biome::Prairie),d=static_cast<std::size_t>(Biome::DryGrassland);
  std::size_t prairieChunks=0,prairieSampled=0,dryChunksSampled=0,temperateChunksSampled=0;
  std::size_t prairieTall=0,dryTall=0,prairieBroad=0,temperateBroad=0,border=0;
  for(unsigned seed:{0u,42u,98765u}) {
   World world({seed,128,64});
   const auto prairieCores=coreChunks(world,Biome::Prairie);
   const auto dryCores=coreChunks(world,Biome::DryGrassland);
   const auto temperateCores=coreChunks(world,Biome::TemperateForest);
   prairieChunks+=prairieCores.size();
   for(std::size_t k=0;k<prairieCores.size()&&k<4;++k) {
    ++prairieSampled;
    for(const auto& f:world.generate(prairieCores[k].first,prairieCores[k].second).features) {
     prairieTall+=f.kind==Kind::Grass&&f.prairie;
     prairieBroad+=f.kind==Kind::Tree&&f.species==static_cast<int>(Species::Broadleaf);
    }
   }
   for(std::size_t k=0;k<dryCores.size()&&k<4;++k) {
    ++dryChunksSampled;
    for(const auto& f:world.generate(dryCores[k].first,dryCores[k].second).features) dryTall+=f.kind==Kind::Grass&&f.prairie;
   }
   for(std::size_t k=0;k<temperateCores.size()&&k<4;++k) {
    ++temperateChunksSampled;
    for(const auto& f:world.generate(temperateCores[k].first,temperateCores[k].second).features)
     temperateBroad+=f.kind==Kind::Tree&&f.species==static_cast<int>(Species::Broadleaf);
   }
   for(double y=-8000;y<=8000;y+=250) for(double x=-8000;x<=8000;x+=250) {
    const auto s=world.sample(x,y),next=world.sample(x+0.5,y);
    if(s.biome[p]<=0.02||s.biome[d]<=0.02) continue;
    ++border;
    check(std::abs(s.biome[p]-next.biome[p])<0.02&&std::abs(s.biome[d]-next.biome[d])<0.02,"Prairie and DryGrassland blend weights are continuous across their border");
   }
  }
  check(prairieChunks>0,"Prairie core chunks exist in the sampled window");
  check(border>0,"Prairie and DryGrassland share a sampled border");
  const double prairieTallPer=prairieSampled?double(prairieTall)/double(prairieSampled):0;
  const double dryTallPer=dryChunksSampled?double(dryTall)/double(dryChunksSampled):0;
  const double prairieBroadPer=prairieSampled?double(prairieBroad)/double(prairieSampled):0;
  const double temperateBroadPer=temperateChunksSampled?double(temperateBroad)/double(temperateChunksSampled):0;
  std::cout<<"Prairie tall grass per chunk "<<prairieTallPer<<" vs DryGrassland "<<dryTallPer<<"; broadleaf per chunk "<<prairieBroadPer<<" vs temperate "<<temperateBroadPer<<" (border samples "<<border<<")\n";
  check(dryTallPer>0&&prairieTallPer>=1.5*dryTallPer,"Prairie tall grass density is at least 1.5x DryGrassland");
  check(temperateBroadPer>0&&prairieBroadPer<=0.2*temperateBroadPer,"Prairie broadleaf trees are at most 0.2x TemperateForest");
 }
 if(!failures) std::cout<<"PASS: regional planning, ecology, climate blends, lighting, routes and triangulated grounding\n";
 return failures?1:0;
}
