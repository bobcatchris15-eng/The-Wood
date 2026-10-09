#pragma once
#include <string>
#include <string_view>

// Masonry kit: discovery mesh name -> kitId. kitId indexes palette Kit array (BootstrapEditor import order).
namespace wood::kit {
struct Entry { std::string_view mesh; int id; };
inline constexpr Entry table[]={
 {"SM_DryStone_Wall",0},
 {"SM_DryStone_Rubble",1},
 {"SM_StonePier",2},
 {"SM_StonePier_Ruined",3},
 {"SM_FoundationCourse",4},
 {"SM_MasonryDebris",5},
 {"SM_FernPatch",6},
 {"SM_BridgeAbutment",7},
 {"SM_RiverSteppingStone",8},
 {"SM_GraniteMonolith",9},
 {"SM_TalusRock",10},
};
inline constexpr int count=11;
// Returns kitId for a known kit mesh name, -1 otherwise.
inline int kitIdFor(const std::string& mesh) {
 for(const auto& e:table) if(mesh==e.mesh) return e.id;
 return -1;
}
}
