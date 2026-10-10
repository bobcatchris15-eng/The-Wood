#include "WoodPreparedChunk.h"
#include "Generation/WoodGround.h"

FWoodPreparedChunk WoodPrepareChunk(const wood::World& World,int X,int Y,
 const TArray<wood::Kind>& Kinds,const TArray<FWoodPlacementProfile>& Profiles,
 const TArray<bool>& Available,bool Details) {
 check(Kinds.Num()==Profiles.Num() && Kinds.Num()==Available.Num());
 FWoodPreparedChunk Result;
 Result.Chunk=World.generate(X,Y,Details);
 const auto& Chunk=Result.Chunk;
 const int32 VertexCount=static_cast<int32>(Chunk.vertices.size());
 Result.Normals.Reserve(VertexCount);
 Result.HabitatUV.Reserve(VertexCount);
 Result.BiomeColors.Reserve(VertexCount); Result.Tints.Reserve(VertexCount); for(const auto& P:Chunk.vertices) {
  const auto Surface=World.sample(P.x,P.y);
  const double DX=(World.sample(P.x+.25,P.y).height-World.sample(P.x-.25,P.y).height)/.5;
  const double DY=(World.sample(P.x,P.y+.25).height-World.sample(P.x,P.y-.25).height)/.5;
  Result.Normals.Add(FVector(-DX,-DY,1).GetSafeNormal());
  Result.HabitatUV.Add(FVector2D(Surface.moisture,Surface.slope));
  const auto Ground=wood::ground::shade(Surface);
  Result.BiomeColors.Add(FLinearColor(Ground.archetype[0],Ground.archetype[1],Ground.archetype[2],Ground.archetype[3]));
  Result.Tints.Add(FLinearColor(Ground.tintR,Ground.tintG,Ground.tintB,wood::ground::snowCover(Surface))); }
 Result.Placements.SetNum(Kinds.Num());
 if(!Details || Chunk.features.empty()) return Result;
 const double Size=World.settings().chunkSize,Step=Size/Chunk.cells;
 const auto Height=[&](double PX,double PY) {
  const double LX=(PX-Chunk.x*Size)/Step,LY=(PY-Chunk.y*Size)/Step;
  if(LX<0 || LY<0 || LX>=Chunk.cells || LY>=Chunk.cells) return World.terrainHeight(PX,PY);
  const int32 C=FMath::FloorToInt(LX),R=FMath::FloorToInt(LY);
  const double U=LX-C,V=LY-R;
  const auto Z=[&](int32 Col,int32 Row) {return Chunk.vertices[Row*(Chunk.cells+1)+Col].z;};
  return U+V<=1?Z(C,R)+(Z(C+1,R)-Z(C,R))*U+(Z(C,R+1)-Z(C,R))*V:
   Z(C+1,R+1)+(Z(C,R+1)-Z(C+1,R+1))*(1-U)+(Z(C+1,R)-Z(C+1,R+1))*(1-V);
 };
 // Candidate tables are immutable within the job, avoiding allocation per plant.
 TArray<TArray<int32>> Candidates;
 // Buckets (WoodGrounding.h map): 0-3 kinds, 4 young, 5 prairie, 6-9 props, 10-20 kits, 21-25 tree species, 26 deadwood.
 Candidates.SetNum(WoodBucketCount);
 for(int32 I=0;I<Kinds.Num();++I) {
  if(!Available[I]) continue;
  const auto& Profile=Profiles[I];
  const bool PropMesh=Kinds[I]==wood::Kind::Prop&&Profile.PropId>=0&&Profile.PropId<WoodPropCount;
  // Kind::Kit (5) is not a raw bucket: kit meshes take WoodKitBucketBase+kitId, else Rock.
  const bool KitMesh=Kinds[I]==wood::Kind::Kit&&Profile.KitId>=0&&Profile.KitId<WoodKitCount;
  // Tree meshes with a species take WoodSpeciesBucketBase+species; Kind::Deadwood (6) is not a raw bucket, it takes WoodDeadwoodBucket.
  const bool SpeciesMesh=Kinds[I]==wood::Kind::Tree&&Profile.Species>=0&&Profile.Species<WoodSpeciesCount;
  const bool DeadwoodMesh=Kinds[I]==wood::Kind::Deadwood;
  const int32 Raw=Kinds[I]==wood::Kind::Kit?static_cast<int32>(wood::Kind::Rock):static_cast<int32>(Kinds[I]);
  Candidates[Profile.Prairie?5:Profile.Young?4:PropMesh?6+Profile.PropId:KitMesh?WoodKitBucketBase+Profile.KitId:
   SpeciesMesh?WoodSpeciesBucketBase+Profile.Species:DeadwoodMesh?WoodDeadwoodBucket:Raw].Add(I);
 }
 for(const auto& Feature:Chunk.features) {
  // Flora features render through the per-species flora components (WoodWorldStreaming.cpp SpawnFlora), not the buckets.
  if(Feature.flora>=0&&Feature.floraMesh>=0) continue;
  int32 Bucket=Feature.young?4:static_cast<int32>(Feature.kind==wood::Kind::Prop?wood::Kind::Rock:Feature.kind);
  if(Feature.prairie && !Candidates[5].IsEmpty()) Bucket=5;
  // Prop features take their propId bucket; an empty bucket falls back to Rock.
  if(Feature.kind==wood::Kind::Prop) {
   const bool HasProp=Feature.propId>=0&&Feature.propId<WoodPropCount&&!Candidates[6+Feature.propId].IsEmpty();
   Bucket=HasProp?6+Feature.propId:static_cast<int32>(wood::Kind::Rock);
  }
  // Kit features take their kitId bucket; an empty bucket falls back to Rock.
  if(Feature.kind==wood::Kind::Kit) {
   const bool HasKit=Feature.kitId>=0&&Feature.kitId<WoodKitCount&&!Candidates[WoodKitBucketBase+Feature.kitId].IsEmpty();
   Bucket=HasKit?WoodKitBucketBase+Feature.kitId:static_cast<int32>(wood::Kind::Rock);
  }
  // Mature trees take their species bucket; an empty species bucket keeps the Tree bucket. Saplings keep the young bucket.
  if(Feature.kind==wood::Kind::Tree&&!Feature.young) {
   const bool HasSpecies=Feature.species>=0&&Feature.species<WoodSpeciesCount&&!Candidates[WoodSpeciesBucketBase+Feature.species].IsEmpty();
   if(HasSpecies) Bucket=WoodSpeciesBucketBase+Feature.species;
  }
  // Deadwood features take the deadwood bucket (its raw Kind value would alias the prop buckets).
  if(Feature.kind==wood::Kind::Deadwood) Bucket=WoodDeadwoodBucket;
  const auto& Matches=Candidates[Bucket];
  if(Matches.IsEmpty()) continue;
  const int32 NumMatches=Matches.Num();
  const int32 RawVariant=static_cast<int32>(Feature.yaw*19)%NumMatches;
  const int32 Variant=RawVariant<0?RawVariant+NumMatches:RawVariant;
  const int32 I=Matches[Variant];
  Result.Placements[I].Add(WoodGroundedTransform(Feature,Profiles[I],Height));
 }
 return Result;
}
