#include "Generation/WoodGround.h"
#include <cassert>
#include <cmath>

using namespace wood;
using namespace wood::ground;

namespace {

bool near(float A,float B) { return std::fabs(A-B)<1e-6f; }

Surface familyOnly(Biome B) {
 Surface S{};
 for(int F=0;F<BiomeCount;++F) S.biome[F]=(F==static_cast<int>(B))?1.0:0.0;
 return S;
}

float archetypeSum(const GroundShade& G) {
 float Sum=0.f;
 for(float V:G.archetype) Sum+=V;
 return Sum;
}

void expectIdentity(const GroundShade& G,int Channel) {
 for(int A=0;A<ArchetypeCount;++A) assert(near(G.archetype[A],A==Channel?1.f:0.f));
 assert(near(G.tintR,1.f) && near(G.tintG,1.f) && near(G.tintB,1.f));
}

} // namespace

int main() {
 // Each existing family alone maps to its identity channel with tint (1,1,1).
 expectIdentity(shade(familyOnly(Biome::TemperateForest)),0);
 expectIdentity(shade(familyOnly(Biome::DryGrassland)),1);
 expectIdentity(shade(familyOnly(Biome::RockyHighlands)),2);
 expectIdentity(shade(familyOnly(Biome::Taiga)),3);

 // New rows: archetype weights sum to one and carry their authored tint.
 {
  const GroundShade Old=shade(familyOnly(Biome::OldGrowthForest));
  assert(near(Old.archetype[0],0.6f) && near(Old.archetype[3],0.4f) && near(Old.archetype[1],0.f) && near(Old.archetype[2],0.f));
  assert(near(archetypeSum(Old),1.f));
  assert(near(Old.tintR,0.85f) && near(Old.tintG,0.82f) && near(Old.tintB,0.75f));
  const GroundShade Rain=shade(familyOnly(Biome::ColdRainforest));
  assert(near(Rain.archetype[0],0.25f) && near(Rain.archetype[3],0.75f) && near(Rain.archetype[1],0.f) && near(Rain.archetype[2],0.f));
  assert(near(archetypeSum(Rain),1.f));
  assert(near(Rain.tintR,0.80f) && near(Rain.tintG,0.95f) && near(Rain.tintB,0.82f));
 }

 // IcyHills and Savannah rows: authored archetype mix and tint, weights sum to one.
 {
  const GroundShade Icy=shade(familyOnly(Biome::IcyHills));
  assert(near(Icy.archetype[0],0.f) && near(Icy.archetype[1],0.30f) && near(Icy.archetype[2],0.55f) && near(Icy.archetype[3],0.15f));
  assert(near(archetypeSum(Icy),1.f));
  assert(near(Icy.tintR,1.25f) && near(Icy.tintG,1.28f) && near(Icy.tintB,1.32f));
  const GroundShade Sav=shade(familyOnly(Biome::Savannah));
  assert(near(Sav.archetype[0],0.15f) && near(Sav.archetype[1],0.75f) && near(Sav.archetype[2],0.10f) && near(Sav.archetype[3],0.f));
  assert(near(archetypeSum(Sav),1.f));
  assert(near(Sav.tintR,1.10f) && near(Sav.tintG,1.00f) && near(Sav.tintB,0.78f));
 }

 // Swamp and Marsh rows: authored archetype mix and tint, weights sum to one.
 {
  const GroundShade Swp=shade(familyOnly(Biome::Swamp));
  assert(near(Swp.archetype[0],0.35f) && near(Swp.archetype[1],0.10f) && near(Swp.archetype[2],0.f) && near(Swp.archetype[3],0.55f));
  assert(near(archetypeSum(Swp),1.f));
  assert(near(Swp.tintR,0.70f) && near(Swp.tintG,0.78f) && near(Swp.tintB,0.62f));
  const GroundShade Mar=shade(familyOnly(Biome::Marsh));
  assert(near(Mar.archetype[0],0.10f) && near(Mar.archetype[1],0.60f) && near(Mar.archetype[2],0.f) && near(Mar.archetype[3],0.30f));
  assert(near(archetypeSum(Mar),1.f));
  assert(near(Mar.tintR,0.85f) && near(Mar.tintG,0.95f) && near(Mar.tintB,0.70f));
 }

 // Blended surface: weights are sum-preserving and archetype sum equals biome sum (1).
 {
  Surface S{};
  S.biome[1]=0.25; S.biome[3]=0.75;
  const GroundShade G=shade(S);
  assert(near(G.archetype[0],0.f));
  assert(near(G.archetype[1],0.25f));
  assert(near(G.archetype[2],0.f));
  assert(near(G.archetype[3],0.75f));
  assert(near(archetypeSum(G),1.f));
  assert(near(G.tintR,1.f) && near(G.tintG,1.f) && near(G.tintB,1.f));
 }

 // Mixed four-way blend stays sum-preserving.
 {
  Surface S{};
  S.biome[0]=0.1; S.biome[1]=0.2; S.biome[2]=0.3; S.biome[3]=0.4;
  const GroundShade G=shade(S);
  assert(near(archetypeSum(G),1.f));
  assert(near(G.archetype[0],0.1f) && near(G.archetype[1],0.2f));
  assert(near(G.archetype[2],0.3f) && near(G.archetype[3],0.4f));
 }

 // Deterministic: same input yields identical output.
 {
  Surface S{};
  S.biome[0]=0.6; S.biome[2]=0.4;
  const GroundShade A=shade(S), B=shade(S);
  for(int I=0;I<ArchetypeCount;++I) assert(A.archetype[I]==B.archetype[I]);
  assert(A.tintR==B.tintR && A.tintG==B.tintG && A.tintB==B.tintB);
 }

 // Table has one row per Biome value.
 static_assert(FamilyLooks.size()==static_cast<std::size_t>(BiomeCount),"row count");
 static_assert(BiomeCount==kFamilyCount,"BiomeCount tracks kFamilyCount");
 return 0;
}
