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
