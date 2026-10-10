#pragma once
#include <algorithm>
#include <array>
#include <cmath>
#include <cstddef>
#include <cstdint>
#include "Generation/WoodGeneration.h"

// Flora habitat engine. Rows transcribed from Docs/FloraCatalog.md: 65 biome flora plus 4 unreal-only species (kFloraCount=69).
// Header-only: the build scripts compile explicit .cpp lists, so a new translation unit would touch every test script.
// Density and weight arrays are indexed by wood::Biome (TF DG RH TG OG CR IH SV SW MA WR PR).
namespace wood {
namespace flora {

enum class Role : int { Canopy, Subcanopy, Shrub, Fern, Grass, Reed, Flower, Aquatic, Moss, Fungus };
inline constexpr int kRoleCount=10;
inline constexpr int kFloraCount=69;
// Biome codes in Biome enum order.
inline constexpr const char* kFamilyCodes[kFamilyCount]={"TF","DG","RH","TG","OG","CR","IH","SV","SW","MA","WR","PR"};

// Catalogue per-biome density ceilings, instances per 100 m2; columns in Role order.
inline constexpr double kRoleDensity[kFamilyCount][kRoleCount]={
 {1.5,1.0,3,4,6,0,2,0,3,1},          // TF
 {0.3,0,2,0.2,20,0,3,0,0.5,0},       // DG
 {0.6,0.4,4,0.5,12,0,2,0,3,0},       // RH
 {2.0,0.5,4,1,6,0,1,0.2,6,0},        // TG
 {1.5,1.0,3,6,4,0.5,2,0,5,2},        // OG
 {2.0,1.5,6,8,3,0.5,1,0.2,8,2},      // CR
 {0.5,0.2,2,0,3,0,1,0,3,0},          // IH
 {0.4,0,3,0,22,0,2,0,0,0},           // SV
 {1.5,0.5,5,2,3,10,1,4,4,1},         // SW
 {0.4,0.3,4,1,8,20,4,6,1,1},         // MA
 {2.5,2.5,8,6,2,2,3,0.5,0.5,2},      // WR
 {0.1,0,2,1,25,0,6,0,0,0}            // PR
};

// One catalogue row. shade: 0 low, 1 med, 2 high. biomes: "TF2 DG1 RH3" density weights per family.
struct Row {
 const char* id; Role role; int shade; bool water;
 double moistMin, moistMax, slopeMax, heightMin, heightMax;
 const char* biomes; int speciesEnum; bool approved; bool deadwood; bool unrealOnly;
};

inline constexpr Row kRows[kFloraCount]={
 // canopy
 {"pine_open",Role::Canopy,0,false,0.2,0.7,0.8,15,30,"TF2 DG1 RH3",0,true,false,false},
 {"oak_broadleaf",Role::Canopy,1,false,0.4,0.7,0.5,15,25,"TF4 OG3 DG2 SV1",1,true,false,false},
 {"broadleaf_giant",Role::Canopy,2,false,0.5,0.8,0.4,30,45,"OG4",2,true,false,false},
 {"spruce_conifer",Role::Canopy,2,false,0.4,0.8,0.9,20,35,"TG4 OG3 CR2 TF2",3,true,false,false},
 {"evergreen_broad",Role::Canopy,2,false,0.6,0.9,0.5,18,28,"CR4 WR2",4,true,false,false},
 {"deadwood_snag",Role::Canopy,0,false,0.2,0.9,0.9,6,20,"TF1 TG2 SW1",-1,true,true,false},
 {"acacia_flat",Role::Canopy,0,false,0.1,0.4,0.4,6,12,"SV4",5,true,false,false},
 {"baldcypress",Role::Canopy,1,true,0.9,1.0,0.1,20,30,"SW4 MA2",6,true,false,false},
 {"larch_sparse",Role::Canopy,0,false,0.3,0.6,1.0,12,20,"TG2 IH1",-1,true,false,false},
 {"cottonwood_river",Role::Canopy,1,true,0.7,1.0,0.2,20,30,"MA2 SW1",-1,true,false,false},
 {"emergent_fig",Role::Canopy,1,false,0.7,1.0,0.4,25,40,"WR4",-1,true,false,false},
 // subcanopy
 {"birch_pale",Role::Subcanopy,1,false,0.4,0.7,0.6,10,18,"TF2",-1,true,false,false},
 {"krummholz_pine",Role::Subcanopy,0,false,0.3,0.7,1.0,1,3,"RH2 IH2 TG1",10,true,false,false},
 {"understory_laurel",Role::Subcanopy,2,false,0.6,0.9,0.5,5,10,"WR3 CR2 OG2",-1,true,false,false},
 // shrub
 {"juniper_low",Role::Shrub,1,false,0.2,0.5,1.0,0.5,1.5,"RH2 DG2 TG2 IH1",-1,true,false,false},
 {"heather_dwarf",Role::Shrub,1,false,0.4,0.7,1.0,0.3,0.8,"RH1 TG2 IH1",-1,true,false,false},
 {"hazel_coppice",Role::Shrub,1,false,0.4,0.7,0.5,2,5,"TF3 OG1",-1,true,false,false},
 {"thorn_scrub",Role::Shrub,0,false,0.1,0.4,0.4,1,3,"SV3 DG2",-1,true,false,false},
 {"willow_shrub",Role::Shrub,1,true,0.8,1.0,0.1,2,6,"MA3 SW2",-1,true,false,false},
 {"sumac_scrub",Role::Shrub,0,false,0.2,0.5,0.5,1,3,"SV2 PR2 DG1",-1,true,false,false},
 {"salal_understory",Role::Shrub,2,false,0.6,0.9,0.5,0.5,1.5,"CR3 OG1",-1,true,false,false},
 {"bilberry_low",Role::Shrub,1,false,0.5,0.8,0.6,0.3,0.6,"TG2 CR2 IH1",-1,true,false,false},
 {"alder_thicket",Role::Shrub,1,true,0.7,1.0,0.3,3,6,"SW2 MA2 CR1",-1,true,false,false},
 {"sagebrush_grey",Role::Shrub,0,false,0.1,0.3,0.8,0.5,1.2,"DG3 RH1",-1,true,false,false},
 {"liana_cluster",Role::Shrub,1,false,0.6,0.9,0.5,1,4,"WR2",-1,true,false,false},
 {"understory_ginger",Role::Shrub,2,false,0.7,0.9,0.4,0.8,1.5,"WR3",-1,true,false,false},
 {"prickly_pear",Role::Shrub,0,false,0.1,0.3,0.5,0.5,1.5,"DG1 SV2",-1,true,false,false},
 // fern
 {"fern_02",Role::Fern,2,false,0.5,0.9,0.6,0.6,1.5,"TF3 OG3 CR3 WR2 SW1",-1,false,false,false},
 {"bracken",Role::Fern,0,false,0.3,0.6,0.5,0.8,2,"TF2 OG1 PR2 DG1",-1,true,false,false},
 {"tree_fern",Role::Fern,2,false,0.7,0.95,0.4,3,7,"WR3 CR2",-1,true,false,false},
 {"royal_fern",Role::Fern,1,true,0.8,1.0,0.1,1,2,"SW2 MA2",-1,true,false,false},
 {"lady_fern",Role::Fern,2,false,0.5,0.8,0.6,0.4,0.9,"TF2 CR2 OG1",-1,true,false,false},
 {"rock_fern",Role::Fern,1,false,0.3,0.6,1.0,0.1,0.3,"RH1 TG1",-1,true,false,false},
 // grass
 {"grass_medium_01",Role::Grass,0,false,0.3,0.7,0.6,0.4,0.9,"DG3 PR2 TF2 OG1",-1,false,false,false},
 {"grass_medium_02",Role::Grass,0,false,0.2,0.6,0.5,0.5,1,"DG3 SV2 PR2 MA1",-1,false,false,false},
 {"grass_bermuda_01",Role::Grass,0,false,0.1,0.5,0.5,0.2,0.5,"SV3 DG2 PR1",-1,false,false,false},
 {"prairie_bunchgrass",Role::Grass,0,false,0.2,0.5,0.8,0.6,1.2,"PR4 DG2 RH1",9,true,false,false},
 {"alpine_tussock",Role::Grass,0,false,0.3,0.7,1.0,0.1,0.4,"RH2 IH2 TG1",-1,true,false,false},
 {"wet_sedge",Role::Grass,1,true,0.8,1.0,0.1,0.3,0.8,"MA3 SW1",-1,true,false,false},
 {"shade_grass",Role::Grass,2,false,0.5,0.8,0.5,0.2,0.5,"OG2 TF1",-1,true,false,false},
 {"frost_fescue",Role::Grass,0,false,0.3,0.6,1.0,0.1,0.3,"IH2 RH1",-1,true,false,false},
 // reed
 {"common_reed",Role::Reed,0,true,0.9,1.0,0.1,2,3.5,"MA4 SW2",-1,true,false,false},
 {"cattail",Role::Reed,0,true,0.9,1.0,0.1,1.5,2.5,"MA3 SW2",8,false,false,false},
 {"horsetail",Role::Reed,2,true,0.7,1.0,0.3,0.3,1.0,"MA2 OG1",-1,true,false,false},
 {"bamboo_stand",Role::Reed,1,false,0.7,0.9,0.4,4,8,"WR2",-1,true,false,false},
 // flower
 {"meadow_flower_mix",Role::Flower,0,false,0.3,0.6,0.8,0.2,0.6,"PR4 DG2 SV1 RH1 TF1",-1,true,false,false},
 {"lupine",Role::Flower,0,false,0.3,0.6,0.6,0.6,1.0,"PR2 RH1",-1,true,false,false},
 {"arctic_poppy",Role::Flower,0,false,0.2,0.5,1.0,0.1,0.3,"IH2 TG1 RH1",-1,true,false,false},
 {"swamp_iris",Role::Flower,1,true,0.9,1.0,0.1,0.5,1.0,"SW1 MA2",-1,true,false,false},
 {"heliconia_bloom",Role::Flower,1,false,0.7,0.9,0.4,1,2,"WR2",-1,true,false,false},
 {"forest_anemone",Role::Flower,2,false,0.4,0.7,0.5,0.1,0.3,"TF2 OG2",-1,true,false,false},
 {"savanna_sunflower",Role::Flower,0,false,0.1,0.4,0.5,0.6,1.4,"SV2 DG1 PR1",-1,true,false,false},
 {"cotton_grass",Role::Flower,0,true,0.8,1.0,0.3,0.3,0.5,"MA2 TG1",-1,true,false,false},
 {"frost_saxifrage",Role::Flower,0,false,0.2,0.5,1.0,0.05,0.15,"IH1 RH1",-1,true,false,false},
 // aquatic
 {"water_lily",Role::Aquatic,0,true,1.0,1.0,0.1,0,0.2,"SW2 MA3",-1,true,false,false},
 {"duckweed_mat",Role::Aquatic,1,true,1.0,1.0,0.1,0,0,"MA2",-1,true,false,false},
 {"pondweed",Role::Aquatic,1,true,1.0,1.0,0.5,0,0.5,"MA1 SW1 TG1",-1,true,false,false},
 // moss
 {"feather_moss",Role::Moss,2,false,0.6,0.9,0.6,0.02,0.05,"TF2 CR3",-1,true,false,false},
 {"sphagnum_hummock",Role::Moss,1,true,0.9,1.0,0.1,0.05,0.2,"TG2 SW2 CR1",-1,true,false,false},
 {"lichen_crust",Role::Moss,1,false,0.2,0.6,1.0,0.01,0.05,"RH2 IH2 TG2",-1,true,false,false},
 {"ground_moss_carpet",Role::Moss,2,false,0.7,0.95,0.5,0.02,0.06,"CR3 OG2",-1,true,false,false},
 {"rock_moss_patch",Role::Moss,2,false,0.6,0.9,1.0,0.05,0.2,"RH2 CR1",-1,true,false,false},
 // fungus
 {"bracket_fungus",Role::Fungus,2,false,0.6,0.9,0.5,0.05,0.3,"OG2 TF1 CR1",-1,true,false,false},
 {"puffball_cluster",Role::Fungus,1,false,0.5,0.8,0.4,0.05,0.2,"TF1",-1,true,false,false},
 {"ground_fungus_patch",Role::Fungus,2,false,0.7,1.0,0.2,0.05,0.15,"OG1 SW1 WR1",-1,true,false,false},
 // unreal-only (LeafPools overlay; no physical biome weight)
 {"shadebell",Role::Shrub,2,false,0.6,0.9,0.5,0.8,2,"",-1,false,false,true},
 {"lanternbrush",Role::Reed,1,true,0.8,1.0,0.3,1,2.5,"",-1,false,false,true},
 {"glassfinger",Role::Fern,1,false,0.3,0.7,1.0,0.3,1,"",-1,false,false,true},
 {"embercrown",Role::Subcanopy,1,false,0.6,0.9,0.4,4,8,"",-1,false,false,true}
};

// Derived per-species record. meshSource is the table index whose approved mesh is rendered (self when approved,
// else the same-role approved species with the greatest shared-biome overlap); -1 means skipped.
struct FloraSpecies {
 Row row{};
 std::array<double,kFamilyCount> weight{};
 bool hasMesh=false;
 int meshSource=-1;
};

inline void parseBiomes(const char* text,std::array<double,kFamilyCount>& out) {
 for(const char* p=text;*p!='\0';) {
  if(*p==' ') { ++p; continue; }
  const char a=p[0], b=p[1];
  p+=2;
  double value=0;
  while(*p>='0'&&*p<='9') { value=value*10.0+static_cast<double>(*p-'0'); ++p; }
  for(std::size_t f=0;f<kFamilyCount;++f) if(kFamilyCodes[f][0]==a&&kFamilyCodes[f][1]==b) out[f]=value;
 }
}

inline std::array<FloraSpecies,kFloraCount> buildTable() {
 std::array<FloraSpecies,kFloraCount> t{};
 for(std::size_t i=0;i<kFloraCount;++i) {
  t[i].row=kRows[i];
  parseBiomes(kRows[i].biomes,t[i].weight);
 }
 for(std::size_t i=0;i<kFloraCount;++i) {
  const Row& r=t[i].row;
  if(r.unrealOnly) continue;
  if(r.approved) { t[i].hasMesh=true; t[i].meshSource=static_cast<int>(i); continue; }
  int best=-1;
  double bestOverlap=0, bestMoist=1e9;
  const double mid=(r.moistMin+r.moistMax)*0.5;
  for(std::size_t j=0;j<kFloraCount;++j) {
   const Row& c=t[j].row;
   if(!c.approved||c.deadwood||c.unrealOnly||c.role!=r.role) continue;
   double overlap=0;
   for(std::size_t f=0;f<kFamilyCount;++f) overlap+=std::min(t[i].weight[f],t[j].weight[f]);
   if(overlap<=0) continue;
   const double dm=std::abs(mid-(c.moistMin+c.moistMax)*0.5);
   if(best<0||overlap>bestOverlap||(overlap==bestOverlap&&dm<bestMoist)) {
    best=static_cast<int>(j); bestOverlap=overlap; bestMoist=dm;
   }
  }
  t[i].meshSource=best;
 }
 return t;
}

inline const std::array<FloraSpecies,kFloraCount>& table() {
 static const std::array<FloraSpecies,kFloraCount> t=buildTable();
 return t;
}

// Local conditions at a candidate point, all taken from Surface and the hydrology fields.
struct Site {
 std::array<double,kFamilyCount> biome{};
 double moisture=0, slope=0, forest=0, streamDist=1e9, halfWidth=0;
};

// Understory roles are gated by canopy closure; trees are not.
inline bool understoryRole(Role role) { return role!=Role::Canopy&&role!=Role::Subcanopy; }

inline double blendWeight(const FloraSpecies& s,const std::array<double,kFamilyCount>& biome) {
 double w=0;
 for(std::size_t f=0;f<kFamilyCount;++f) w+=biome[f]*s.weight[f];
 return w;
}

// Soft tolerances: moisture +-0.10 and slope +0.10 beyond the catalogue range, since family moisture is a regional mean.
inline bool viable(const FloraSpecies& s,const Site& site,Role role) {
 if(s.row.role!=role||s.meshSource<0||s.row.deadwood||s.row.unrealOnly) return false;
 if(blendWeight(s,site.biome)<=0) return false;
 if(site.moisture<s.row.moistMin-0.1||site.moisture>s.row.moistMax+0.1) return false;
 if(site.slope>s.row.slopeMax+0.1) return false;
 if(understoryRole(role)) {
  const int need=site.forest>0.85?2:(site.forest>0.5?1:0);
  if(s.row.shade<need) return false;
 }
 const bool wetBasin=site.biome[static_cast<std::size_t>(Biome::Marsh)]+site.biome[static_cast<std::size_t>(Biome::Swamp)]>=0.5;
 if(s.row.water&&!wetBasin&&site.streamDist>6.0) return false;
 return true;
}

// Weighted pick among viable species of one role; roll in [0,1). Returns table index or -1.
inline int pick(const Site& site,Role role,double roll) {
 const auto& t=table();
 std::array<double,kFloraCount> w{};
 double total=0;
 for(std::size_t i=0;i<kFloraCount;++i) {
  if(!viable(t[i],site,role)) continue;
  w[i]=blendWeight(t[i],site.biome);
  total+=w[i];
 }
 if(total<=0) return -1;
 double target=roll*total;
 int last=-1;
 for(std::size_t i=0;i<kFloraCount;++i) {
  if(w[i]<=0) continue;
  last=static_cast<int>(i);
  if(target<w[i]) return last;
  target-=w[i];
 }
 return last;
}

// Ceiling for one role at a point: family-blended catalogue density, instances per 100 m2.
inline double roleDensity(const std::array<double,kFamilyCount>& biome,Role role) {
 double d=0;
 for(std::size_t f=0;f<kFamilyCount;++f) d+=biome[f]*kRoleDensity[f][static_cast<std::size_t>(role)];
 return d;
}

}
}
