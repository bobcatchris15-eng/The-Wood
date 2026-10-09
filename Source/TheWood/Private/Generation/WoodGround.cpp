#include "Generation/WoodGround.h"
#include <algorithm>

namespace wood::ground {

GroundShade shade(const wood::Surface& Surface) {
 GroundShade Out{{0.f,0.f,0.f,0.f},0.f,0.f,0.f};
 for(int F=0;F<BiomeCount;++F) {
  const float W=static_cast<float>(Surface.biome[F]);
  const FamilyLook& Look=FamilyLooks[F];
  for(int A=0;A<ArchetypeCount;++A) Out.archetype[A]+=W*Look.archetype[A];
  Out.tintR+=W*Look.tintR;
  Out.tintG+=W*Look.tintG;
  Out.tintB+=W*Look.tintB;
 }
 // Tints are shader multipliers; cap them so no blend can exceed 1.5.
 Out.tintR=std::min(Out.tintR,1.5f);
 Out.tintG=std::min(Out.tintG,1.5f);
 Out.tintB=std::min(Out.tintB,1.5f);
 return Out;
}

} // namespace wood::ground
