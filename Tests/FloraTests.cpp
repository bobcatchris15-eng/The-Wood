#include "Generation/WoodGeneration.h"
#include "Generation/WoodFlora.h"
#include <array>
#include <cmath>
#include <cstdio>
#include <cstring>
#include <iostream>
#include <iterator>
#include <set>
#include <vector>

// F1: flora habitat engine. Each family core is a 1 km2 block (8x8 chunks of 128 m) whose centre weight is >= 0.9.
namespace {
int failures=0;
void check(bool ok,const char* text) { if(!ok) { ++failures; std::cerr<<"FAIL: "<<text<<'\n'; } }
using namespace wood;

// Family cores spread over the lattice: one core chunk per hex region of the family, evenly picked up to `want`.
// A core chunk is the region origin chunk or a neighbour whose centre weight for the family is >= 0.9.
std::vector<std::pair<int,int>> familyCores(const World& w,int family,std::size_t want) {
 const auto index=static_cast<std::size_t>(family);
 std::vector<std::pair<int,int>> all;
 for(int q=-40;q<=40;++q) for(int r=-40;r<=40;++r) {
  const auto reg=w.region(q,r);
  if(static_cast<int>(reg.family)!=family) continue;
  const int cx=static_cast<int>(std::floor(reg.origin.x/128)),cy=static_cast<int>(std::floor(reg.origin.y/128));
  bool found=false;
  for(int dy=-1;dy<=1&&!found;++dy) for(int dx=-1;dx<=1&&!found;++dx)
   if(w.sample((cx+dx)*128+64.0,(cy+dy)*128+64.0).biome[index]>=0.9) { all.push_back({cx+dx,cy+dy}); found=true; }
 }
 if(all.size()<want) return all;
 std::vector<std::pair<int,int>> out;
 for(std::size_t k=0;k<want;++k) out.push_back(all[k*all.size()/want]);
 return out;
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
 std::size_t meshes=0, approvedMismatch=0, fallbackRoleMismatch=0, unrealMesh=0, unrealProxyBad=0;
 for(std::size_t i=0;i<count;++i) {
  const auto& s=table[i];
  meshes+=s.hasMesh?1:0;
  if(s.row.approved!=(s.hasMesh&&s.meshSource==static_cast<int>(i))) ++approvedMismatch;
  if(s.row.unrealOnly&&s.hasMesh) ++unrealMesh;
  if(s.row.unrealOnly&&(s.meshSource<0||table[static_cast<std::size_t>(s.meshSource)].row.role!=s.row.role||!table[static_cast<std::size_t>(s.meshSource)].hasMesh)) ++unrealProxyBad;
  if(s.meshSource>=0&&table[static_cast<std::size_t>(s.meshSource)].row.role!=s.row.role) ++fallbackRoleMismatch;
 }
 check(meshes==60,"60 approved species carry a mesh flag");
 check(approvedMismatch==0,"hasMesh is set exactly for approved species, sourced from themselves");
 check(fallbackRoleMismatch==0,"mesh fallbacks stay within the same role");
 check(unrealMesh==0,"unreal-only species carry no physical mesh of their own");
 check(unrealProxyBad==0,"unreal-only species render a same-role approved proxy mesh (LeafPools material applied by adapter)");

 // Approval list hard-coded from ArtSource/Authored/Flora/APPROVED.md, final state (later redo rows supersede rejections).
 // Batches: canopy_a, shrub_a, flower(all 9), canopy_b, grass, fern, wetfungi, shrub_b, conifer, shrub_c, redo. Keep in sync with that file.
 static const char* const kApprovedNames[]={
  "oak_broadleaf","broadleaf_giant","evergreen_broad","deadwood_snag",
  "hazel_coppice","sumac_scrub","salal_understory","heather_dwarf",
  "meadow_flower_mix","lupine","arctic_poppy","swamp_iris","heliconia_bloom","forest_anemone","savanna_sunflower","cotton_grass","frost_saxifrage",
  "acacia_flat","birch_pale","emergent_fig","cottonwood_river","understory_laurel",
  "prairie_bunchgrass","wet_sedge","frost_fescue","common_reed","bamboo_stand",
  "bracken","tree_fern","royal_fern","rock_fern","feather_moss","ground_moss_carpet","rock_moss_patch","lichen_crust","sphagnum_hummock",
  "water_lily","ground_fungus_patch","puffball_cluster","pondweed",
  "understory_ginger","liana_cluster",
  "pine_open","spruce_conifer","larch_sparse","krummholz_pine",
  "willow_shrub","thorn_scrub","juniper_low","bilberry_low","alder_thicket","sagebrush_grey","prickly_pear",
  "baldcypress","lady_fern","alpine_tussock","shade_grass","horsetail","bracket_fungus","duckweed_mat"
 };
 std::size_t namedUnflagged=0, approvedFlags=0;
 for(std::size_t i=0;i<count;++i) if(table[i].row.approved) ++approvedFlags;
 for(const char* name: kApprovedNames) {
  bool flagged=false, found=false;
  for(std::size_t i=0;i<count;++i) if(std::strcmp(table[i].row.id,name)==0) { found=true; flagged=table[i].row.approved; }
  if(!found||!flagged) { ++namedUnflagged; std::cerr<<"  not approved: "<<name<<'\n'; }
 }
 check(namedUnflagged==0,"every species named approved in APPROVED.md has approved=true");
 check(approvedFlags==std::size(kApprovedNames),"approved flag count equals APPROVED.md list (60)");

 double worstOverCeiling=0, worstUnderFloor=1e9;
 std::size_t badSpeciesCount=0, unrealPlaced=0;
 for(int family=0;family<kFamilyCount;++family) {
  const auto f=static_cast<std::size_t>(family);
  World world({42,128,64});
  // 32 family cores, one per region, spread over the lattice: 32 x 128 m chunks = 0.52 km2 of sampled ground per family.
  constexpr std::size_t kCores=32;
  const auto cores=familyCores(world,family,kCores);
  if(cores.size()<kCores) { check(false,"every family has 32 core chunks in range"); continue; }

  std::vector<Chunk> chunks;
  for(const auto& core:cores) chunks.push_back(world.generate(core.first,core.second));

  std::set<int> species;
  std::array<std::size_t,flora::kRoleCount> roleCounts{};
  std::size_t outside=0, badMesh=0, badTint=0, badHeight=0, unrealOutside=0;
  for(const auto& c:chunks) for(const auto& feature:c.features) {
   if(feature.flora<0) continue;
   const auto& s=table[static_cast<std::size_t>(feature.flora)];
   species.insert(feature.flora);
   roleCounts[static_cast<std::size_t>(s.row.role)]++;
   const auto site=world.sample(feature.position.x,feature.position.y);
   const auto ov=world.overlayAt(feature.position.x,feature.position.y);
   flora::Site local;
   local.biome=site.biome; local.moisture=site.moisture; local.slope=site.slope; local.forest=site.forest;
   local.streamDist=std::abs(feature.position.x-world.streamX(feature.position.y));
   local.halfWidth=world.streamHalfWidth(feature.position.y);
   local.unreal=ov.unrealWeight;
   if(s.row.unrealOnly) { ++unrealPlaced; if(!ov.active) ++unrealOutside; }
   if(!flora::viable(s,local,s.row.role)) ++outside;
   if(feature.floraMesh<0||!table[static_cast<std::size_t>(feature.floraMesh)].hasMesh) ++badMesh;
   if(feature.tint<0||feature.tint>3) ++badTint;
   if(feature.heightM<s.row.heightMin-1e-9||feature.heightM>s.row.heightMax+1e-9) ++badHeight;
  }
  check(unrealOutside==0,"unreal-only species are placed only where unreal overlay has weight");
  check(species.size()>=7,"each family places at least 7 distinct species over its 32 cores (WR catalogue-limited at 7)");
  check(outside==0,"no species placed outside its viability");
  check(badMesh==0,"every placed species renders an approved mesh");
  check(badTint==0,"tint index stays within 0-3");
  check(badHeight==0,"instance height stays within the species range");

  // Density: per-role instances per 100 m2 against the sampled ceiling. Ceiling = family-blended catalogue density
  // (roleDensity) at each grid point, scaled by the unreal overlay densityScale (neutral 1 outside unreal regions), averaged over the sampled cells.
  // Upper bound 1.10x always. 30% floor only where a meshed species of the role is viable over half the sampled cells; others are exempt and logged.
  const double area=static_cast<double>(cores.size())*128.0*128.0;
  constexpr int cellsPerChunk=64; // 8x8 cells of 16 m per 128 m chunk
  const std::size_t sampledCells=cores.size()*cellsPerChunk;
  std::array<double,flora::kRoleCount> blockCeiling{};
  std::array<bool,flora::kRoleCount> viableRole{};
  std::array<int,flora::kRoleCount> viableCells{};
  for(const auto& core:cores) for(int gy=0;gy<8;++gy) for(int gx=0;gx<8;++gx) {
   const double px=core.first*128.0+(gx+0.5)*16.0, py=core.second*128.0+(gy+0.5)*16.0;
   const auto site=world.sample(px,py);
   const auto ov=world.overlayAt(px,py);
   const double scale=ov.densityScale;
   flora::Site local;
   local.biome=site.biome; local.moisture=site.moisture; local.slope=site.slope; local.forest=site.forest;
   local.streamDist=std::abs(px-world.streamX(py)); local.halfWidth=world.streamHalfWidth(py);
   for(int r=0;r<flora::kRoleCount;++r) blockCeiling[static_cast<std::size_t>(r)]+=flora::roleDensity(site.biome,static_cast<flora::Role>(r))*scale*(r==static_cast<int>(flora::Role::Fungus)?ov.fungusScale:1.0)/sampledCells;
   std::array<bool,flora::kRoleCount> hereViable{};
   for(std::size_t i=0;i<count;++i) {
    const auto& s=table[i];
    if(s.meshSource>=0&&!s.row.deadwood&&!s.row.unrealOnly&&flora::viable(s,local,s.row.role)) hereViable[static_cast<std::size_t>(s.row.role)]=true;
   }
   for(std::size_t r=0;r<flora::kRoleCount;++r) if(hereViable[r]) viableCells[r]++;
  }
  // A role counts as habitat-viable when a meshed species is viable over at least half the block.
  for(std::size_t r=0;r<flora::kRoleCount;++r) viableRole[r]=viableCells[r]*2>=sampledCells;
  std::printf("%s: %zu cores, %zu species, %zu features\n",flora::kFamilyCodes[f],cores.size(),species.size(),[&]{std::size_t n=0; for(const auto& c:chunks) n+=c.features.size(); return n;}());
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
    const int cx=cores[idx].first, cy=cores[idx].second;
    const auto repeat=again.generate(cx,cy);
    bool same=repeat.features.size()==chunks[idx].features.size();
    for(std::size_t k=0;same&&k<repeat.features.size();++k) same=sameFeature(repeat.features[k],chunks[idx].features[k]);
    check(same,"chunk output is independent of generation order");
   }
  }
 }
 check(unrealPlaced>0,"unreal-only species are placed somewhere across the family cores");
 std::printf("unreal-only features placed: %zu\n",unrealPlaced);
 std::printf("worst role density ratio: max %.3f of ceiling, min %.3f of ceiling; families below 8 species: %zu\n",worstOverCeiling,worstUnderFloor,badSpeciesCount);

 if(failures) std::cerr<<failures<<" flora checks failed\n";
 else std::cout<<"Flora checks passed\n";
 return failures?1:0;
}
