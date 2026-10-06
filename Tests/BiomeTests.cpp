#include "Generation/WoodGeneration.h"
#include <algorithm>
#include <cmath>
#include <iostream>
int failures=0;
void check(bool ok,const char* text) { if(!ok) { ++failures; if(failures<25) std::cerr<<"FAIL: "<<text<<'\n'; } }
int main() {
 using namespace wood;
 for(unsigned seed:{0u,42u,98765u}) {
  World world({seed,128,64});
  // Removing two-dimensional climatic variation must break this contract.
  const auto south=world.sample(-180,-180),north=world.sample(-180,1300);
  check(std::abs(south.moisture-north.moisture)>0.15,"northward travel discovers a different climate at the same x");
  check(south.forest>0.65,"journey starts in sheltered mature woodland");
 }
 for(unsigned seed:{0u,42u,98765u}) {
  World world({seed,128,64});
  const int coords[4][2]={{0,0},{1,0},{1,1},{0,-1}};
  std::array<std::size_t,4> trees{},ferns{},rocks{},cover{};
  for(int family=0;family<4;++family) {
   const auto r=world.region(coords[family][0],coords[family][1]);
   const auto s=world.sample(r.origin.x,r.origin.y);
   const auto again=world.region(coords[family][0],coords[family][1]);
   check(r.identity==again.identity&&r.origin.x==again.origin.x&&r.origin.y==again.origin.y&&r.phase==again.phase,"regional identities and origins repeat without query history");
   check(static_cast<int>(r.family)==family,"starter neighborhood includes four explicit families");
   check(s.biome[family]>0.65,"each regional origin preserves its ecological identity");
   check(r.extent>1500&&r.extent<4000,"regional influence spans walking-scale terrain");
   const int cx=static_cast<int>(std::floor(r.origin.x/128)),cy=static_cast<int>(std::floor(r.origin.y/128));
   const auto chunk=world.generate(cx,cy),repeat=world.generate(cx,cy);
   const auto east=world.generate(cx+1,cy);
   for(int row=0;row<=64;++row)
    check(chunk.vertices[row*65+64].z==east.vertices[row*65].z,"regional terrain edges agree across all four habitat families");
   check(chunk.features.size()==repeat.features.size(),"far regional placement repeats independently of query order");
   for(std::size_t i=0;i<chunk.features.size();++i) {
    const auto& f=chunk.features[i]; const auto& other=repeat.features[i];
    check(f.kind==other.kind&&f.position.x==other.position.x&&f.position.y==other.position.y&&f.position.z==other.position.z,"far regional feature records remain deterministic");
    check(std::abs(f.position.z-world.terrainHeight(f.position.x,f.position.y))<1e-9,"every ecological layer meets realized terrain");
    trees[family]+=f.kind==Kind::Tree; ferns[family]+=f.kind==Kind::Fern;
    rocks[family]+=f.kind==Kind::Rock; cover[family]+=f.kind==Kind::Grass||f.kind==Kind::Fern;
   }
  }
  check(trees[0]>trees[1]*3&&trees[0]>trees[2]*3,"dry and highland regions have open canopies");
  check(ferns[0]>ferns[1]*3&&ferns[0]>ferns[3]*2,"moist temperate woodland has richer ferns than grassland and taiga");
  check(rocks[2]>rocks[0]*2,"rocky highlands contain denser stone groups");
  check(cover[2]<cover[0]&&cover[3]<cover[0],"highland and taiga ground cover is sparser than moist woodland");
  std::cout<<"Biome seed "<<seed;
  for(int i=0;i<4;++i) std::cout<<" ["<<trees[i]<<" trees,"<<ferns[i]<<" ferns,"<<rocks[i]<<" rocks,"<<cover[i]<<" cover]";
  std::cout<<'\n';
  for(double y:{-98000.0,-3600.0,-180.0,600.0,3300.0,97500.0}) for(double x:{-98200.0,-2400.0,-180.0,600.0,5100.0,98400.0}) {
   const auto s=world.sample(x,y),repeat=world.sample(x,y),next=world.sample(x+0.05,y+0.05);
   double sum=0;
   for(int i=0;i<4;++i) {
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
 if(!failures) std::cout<<"PASS: regional planning, ecology, climate blends, lighting, routes and triangulated grounding\n";
 return failures?1:0;
}
