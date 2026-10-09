#include "Generation/WoodGeneration.h"
#include "Generation/WoodFlora.h"
#include <array>
#include <cmath>
#include <cstdio>
#include <iostream>
#include <set>
#include <vector>

// F1: flora habitat engine. Each family core is a 1 km2 block (8x8 chunks of 128 m) whose centre weight is >= 0.9.
namespace {
int failures=0;
void check(bool ok,const char* text) { if(!ok) { ++failures; std::cerr<<"FAIL: "<<text<<'\n'; } }
using namespace wood;

bool findCore(const World& w,int family,int& bx,int& by) {
 const auto index=static_cast<std::size_t>(family);
 for(int j=-12;j<12;++j) for(int i=-12;i<12;++i) {
  const int cx=i*8, cy=j*8;
  if(w.sample(cx*128.0+512.0,cy*128.0+512.0).biome[index]>=0.9) { bx=cx; by=cy; return true; }
 }
 return false;
}

bool sameFeature(const Feature& a,const Feature& b) {
 return a.kind==b.kind&&a.flora==b.flora&&a.floraMesh==b.floraMesh&&a.tint==b.tint&&a.heightM==b.heightM&&
        a.position.x==b.position.x&&a.position.y==b.position.y&&a.yaw==b.yaw&&a.scale==b.scale;
}
}

int main() {
 const auto& table=flora::table();
 const auto count=static_cast<std::size_t>(flora::kFloraCount);
 check(table.size()==count,"table holds 69 species");

 // Mesh flags: approved species (APPROVED.md) carry their own mesh; unapproved ones fall back or are skipped.
 std::size_t meshes=0, approvedMismatch=0, fallbackRoleMismatch=0, unrealMesh=0;
 for(std::size_t i=0;i<count;++i) {
  const auto& s=table[i];
  meshes+=s.hasMesh?1:0;
  if(s.row.approved!=(s.hasMesh&&s.meshSource==static_cast<int>(i))) ++approvedMismatch;
  if(s.row.unrealOnly&&(s.hasMesh||s.meshSource>=0)) ++unrealMesh;
  if(s.meshSource>=0&&table[static_cast<std::size_t>(s.meshSource)].row.role!=s.row.role) ++fallbackRoleMismatch;
 }
 check(meshes==40,"40 approved species carry a mesh flag");
 check(approvedMismatch==0,"hasMesh is set exactly for approved species, sourced from themselves");
 check(fallbackRoleMismatch==0,"mesh fallbacks stay within the same role");
 check(unrealMesh==0,"unreal-only species carry no physical mesh");

 double worstOverCeiling=0, worstUnderFloor=1e9;
 std::size_t badSpeciesCount=0;
 for(int family=0;family<kFamilyCount;++family) {
  const auto f=static_cast<std::size_t>(family);
  World world({42,128,64});
  int bx=0,by=0;
  if(!findCore(world,family,bx,by)) { check(false,"every family has a 1 km2 core in range"); continue; }

  std::vector<Chunk> chunks;
  for(int cy=by;cy<by+8;++cy) for(int cx=bx;cx<bx+8;++cx) chunks.push_back(world.generate(cx,cy));

  std::set<int> species;
  std::array<std::size_t,flora::kRoleCount> roleCounts{};
  std::size_t outside=0, badMesh=0, badTint=0, badHeight=0;
  for(const auto& c:chunks) for(const auto& feature:c.features) {
   if(feature.flora<0) continue;
   const auto& s=table[static_cast<std::size_t>(feature.flora)];
   species.insert(feature.flora);
   roleCounts[static_cast<std::size_t>(s.row.role)]++;
   const auto site=world.sample(feature.position.x,feature.position.y);
   flora::Site local;
   local.biome=site.biome; local.moisture=site.moisture; local.slope=site.slope; local.forest=site.forest;
   local.streamDist=std::abs(feature.position.x-world.streamX(feature.position.y));
   local.halfWidth=world.streamHalfWidth(feature.position.y);
   if(!flora::viable(s,local,s.row.role)) ++outside;
   if(feature.floraMesh<0||!table[static_cast<std::size_t>(feature.floraMesh)].hasMesh) ++badMesh;
   if(feature.tint<0||feature.tint>3) ++badTint;
   if(feature.heightM<s.row.heightMin-1e-9||feature.heightM>s.row.heightMax+1e-9) ++badHeight;
  }
  check(species.size()>=8,"each family places at least 8 distinct species over 1 km2");
  check(outside==0,"no species placed outside its viability");
  check(badMesh==0,"every placed species renders an approved mesh");
  check(badTint==0,"tint index stays within 0-3");
  check(badHeight==0,"instance height stays within the species range");

  // Density: per-role instances per 100 m2 against the block ceiling. Ceiling = family-blended catalogue density
  // (roleDensity) at each grid point, scaled by the unreal overlay densityScale (neutral 1 outside unreal regions), averaged over the block.
  // Upper bound 1.10x always. 30% floor only where a meshed species of the role is viable over half the block; others are exempt and logged.
  const double area=(8*128.0)*(8*128.0);
  constexpr int grid=32;
  std::array<double,flora::kRoleCount> blockCeiling{};
  std::array<bool,flora::kRoleCount> viableRole{};
  std::array<int,flora::kRoleCount> viableCells{};
  for(int gy=0;gy<grid;++gy) for(int gx=0;gx<grid;++gx) {
   const double px=bx*128.0+(gx+0.5)*(1024.0/grid), py=by*128.0+(gy+0.5)*(1024.0/grid);
   const auto site=world.sample(px,py);
   const double scale=world.overlayAt(px,py).densityScale;
   flora::Site local;
   local.biome=site.biome; local.moisture=site.moisture; local.slope=site.slope; local.forest=site.forest;
   local.streamDist=std::abs(px-world.streamX(py)); local.halfWidth=world.streamHalfWidth(py);
   for(int r=0;r<flora::kRoleCount;++r) blockCeiling[static_cast<std::size_t>(r)]+=flora::roleDensity(site.biome,static_cast<flora::Role>(r))*scale/(grid*grid);
   std::array<bool,flora::kRoleCount> hereViable{};
   for(std::size_t i=0;i<count;++i) {
    const auto& s=table[i];
    if(s.meshSource>=0&&!s.row.deadwood&&!s.row.unrealOnly&&flora::viable(s,local,s.row.role)) hereViable[static_cast<std::size_t>(s.row.role)]=true;
   }
   for(std::size_t r=0;r<flora::kRoleCount;++r) if(hereViable[r]) viableCells[r]++;
  }
  // A role counts as habitat-viable when a meshed species is viable over at least half the block.
  for(std::size_t r=0;r<flora::kRoleCount;++r) viableRole[r]=viableCells[r]*2>=grid*grid;
  std::printf("%s core (%d,%d): %zu species, %zu features\n",flora::kFamilyCodes[f],bx,by,species.size(),[&]{std::size_t n=0; for(const auto& c:chunks) n+=c.features.size(); return n;}());
  for(int r=0;r<flora::kRoleCount;++r) {
   const auto ri=static_cast<std::size_t>(r);
   const double ceiling=blockCeiling[ri];
   const double measured=static_cast<double>(roleCounts[ri])*100.0/area;
   if(ceiling<=0) {
    check(roleCounts[ri]==0,"role with zero ceiling places nothing");
    continue;
   }
   if(!viableRole[ri]) {
    std::printf("  role %d: exempt, no viable meshed species (ceiling %.3f, placed %.3f)\n",r,ceiling,measured);
    check(measured<=ceiling*1.10,"unviable role places nothing above its ceiling");
    continue;
   }
   const double ratio=measured/ceiling;
   if(ratio>worstOverCeiling) worstOverCeiling=ratio;
   if(ratio<worstUnderFloor) worstUnderFloor=ratio;
   std::printf("  role %d: %.3f per 100 m2 vs ceiling %.3f (%.0f%%)\n",r,measured,ceiling,100.0*ratio);
   check(measured<=ceiling*1.10,"role density does not exceed the block ceiling by more than 10 percent");
   check(measured>=0.30*ceiling,"role density is at least 30 percent of the ceiling where a viable meshed species exists");
  }
  badSpeciesCount+=species.size()<8?1:0;

  // Chunk-order independence and determinism for two families: regenerate in reverse order on a fresh world.
  if(family==0||family==kFamilyCount-1) {
   World again({42,128,64});
   for(std::size_t idx=chunks.size();idx-->0;) {
    const int cx=bx+static_cast<int>(idx%8), cy=by+static_cast<int>(idx/8);
    const auto repeat=again.generate(cx,cy);
    bool same=repeat.features.size()==chunks[idx].features.size();
    for(std::size_t k=0;same&&k<repeat.features.size();++k) same=sameFeature(repeat.features[k],chunks[idx].features[k]);
    check(same,"chunk output is independent of generation order");
   }
  }
 }
 std::printf("worst role density ratio: max %.3f of ceiling, min %.3f of ceiling; families below 8 species: %zu\n",worstOverCeiling,worstUnderFloor,badSpeciesCount);

 if(failures) std::cerr<<failures<<" flora checks failed\n";
 else std::cout<<"Flora checks passed\n";
 return failures?1:0;
}
