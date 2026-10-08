#include "WoodPreparedChunk.h"

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
 Result.BiomeColors.Reserve(VertexCount);
 for(const auto& P:Chunk.vertices) {
  const auto Surface=World.sample(P.x,P.y);
  const double DX=(World.sample(P.x+.25,P.y).height-World.sample(P.x-.25,P.y).height)/.5;
  const double DY=(World.sample(P.x,P.y+.25).height-World.sample(P.x,P.y-.25).height)/.5;
  Result.Normals.Add(FVector(-DX,-DY,1).GetSafeNormal());
  Result.HabitatUV.Add(FVector2D(Surface.moisture,Surface.slope));
  Result.BiomeColors.Add(FLinearColor(static_cast<float>(Surface.biome[0]),static_cast<float>(Surface.biome[1]),
   static_cast<float>(Surface.biome[2]),static_cast<float>(Surface.biome[3])));
 }
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
 // Buckets: 0-3 kinds, 4 young, 5 prairie, 6+propId props.
 Candidates.SetNum(6+WoodPropCount);
 for(int32 I=0;I<Kinds.Num();++I) {
  if(!Available[I]) continue;
  const auto& Profile=Profiles[I];
  const bool PropMesh=Kinds[I]==wood::Kind::Prop&&Profile.PropId>=0&&Profile.PropId<WoodPropCount;
  Candidates[Profile.Prairie?5:Profile.Young?4:PropMesh?6+Profile.PropId:static_cast<int32>(Kinds[I])].Add(I);
 }
 for(const auto& Feature:Chunk.features) {
  int32 Bucket=Feature.young?4:static_cast<int32>(Feature.kind==wood::Kind::Prop?wood::Kind::Rock:Feature.kind);
  if(Feature.prairie && !Candidates[5].IsEmpty()) Bucket=5;
  // Prop features take their propId bucket; an empty bucket falls back to Rock.
  if(Feature.kind==wood::Kind::Prop) {
   const bool HasProp=Feature.propId>=0&&Feature.propId<WoodPropCount&&!Candidates[6+Feature.propId].IsEmpty();
   Bucket=HasProp?6+Feature.propId:static_cast<int32>(wood::Kind::Rock);
  }
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
