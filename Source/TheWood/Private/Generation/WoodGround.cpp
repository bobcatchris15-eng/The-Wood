#include "Generation/WoodGround.h"

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
 return Out;
}

} // namespace wood::ground
