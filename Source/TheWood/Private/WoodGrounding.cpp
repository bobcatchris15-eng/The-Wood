#include "WoodGrounding.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"

// Matches core validatePoint (1e6 m) in centimetres; anything past it is garbage, not geometry.
namespace {
constexpr double WoodRootLimitCm=1.0e8;
}

const TArray<FVector>& WoodRootContacts(const UStaticMesh& Asset) {
 check(IsInGameThread());
 static TMap<TWeakObjectPtr<const UStaticMesh>,TArray<FVector>> Cache;
 const TWeakObjectPtr<const UStaticMesh> Key(&Asset);
 if(const auto* Found=Cache.Find(Key)) return *Found;
 TArray<FVector> Contacts;
 const auto* Data=Asset.GetRenderData();
 if(Data && !Data->LODResources.IsEmpty()) {
  const auto& Positions=Data->LODResources[0].VertexBuffers.PositionVertexBuffer;
  if(Positions.GetNumVertices()>0 && Positions.GetVertexData()) {
   double Bottom=DBL_MAX;
   for(uint32 I=0;I<Positions.GetNumVertices();++I) Bottom=FMath::Min(Bottom,static_cast<double>(Positions.VertexPosition(I).Z));
   // Preserve the lower envelope of the root skirt, not the canopy bounding box.
   TMap<FIntPoint,FVector> Bins;
   for(uint32 I=0;I<Positions.GetNumVertices();++I) {
    const FVector P(Positions.VertexPosition(I));
    // Cooked buffers can carry non-finite or wild positions; never let them reach the ground probe.
    if(P.ContainsNaN() || !FMath::IsFinite(P.X) || !FMath::IsFinite(P.Y) || !FMath::IsFinite(P.Z)) continue;
    if(FMath::Abs(P.X)>WoodRootLimitCm || FMath::Abs(P.Y)>WoodRootLimitCm || FMath::Abs(P.Z)>WoodRootLimitCm) continue;
    if(P.Z>Bottom+15) continue;
    const FIntPoint Bin(FMath::FloorToInt(P.X/5),FMath::FloorToInt(P.Y/5));
    FVector* Existing=Bins.Find(Bin);
    if(!Existing || P.Z<Existing->Z) Bins.Add(Bin,P);
   }
   Bins.GenerateValueArray(Contacts);
  }
 }
 // Imported tree meshes must retain CPU positions when cooked. This fallback
 // still compensates an offset origin, but authoring validation rejects it.
 if(Contacts.IsEmpty()) {
  const FBox Box=Asset.GetBoundingBox();
  const double MinZ=Box.IsValid?Box.Min.Z:0.0;
  Contacts.Add(FVector(0,0,FMath::IsFinite(MinZ)&&FMath::Abs(MinZ)<=WoodRootLimitCm?MinZ:0.0));
  UE_LOG(LogTemp,Warning,TEXT("WoodRootContacts: %s has no usable CPU positions; using bounds base"),*Asset.GetName());
 }
 return Cache.Add(Key,MoveTemp(Contacts));
}

FWoodPlacementProfile WoodPlacementProfile(const UStaticMesh& Asset) {
 check(IsInGameThread());
 return FWoodPlacementProfile{WoodRootContacts(Asset),Asset.GetBoundingBox()};
}

FTransform WoodGroundedTransform(const wood::World& World,const wood::Feature& Feature,const UStaticMesh& Asset) {
 return WoodGroundedTransform(World,Feature,WoodPlacementProfile(Asset));
}

FTransform WoodGroundedTransform(const wood::World& World,const wood::Feature& Feature,const FWoodPlacementProfile& Profile) {
 return WoodGroundedTransform(Feature,Profile,[&World](double X,double Y) {return World.terrainHeight(X,Y);});
}

FTransform WoodGroundedTransform(const wood::Feature& Feature,const FWoodPlacementProfile& Profile,TFunctionRef<double(double,double)> GroundHeight) {
 const double X=Feature.position.x*100,Y=Feature.position.y*100;
 // Kit pieces keep their authored z, pitch and roll exactly; no root fit.
 if(Feature.kind==wood::Kind::Kit) return FTransform(FRotator(Feature.pitch,Feature.yaw,Feature.roll),FVector(X,Y,Feature.position.z*100),FVector(Feature.scale));
 const double Lean=Feature.kind==wood::Kind::Tree?FMath::Sin(FMath::DegreesToRadians(Feature.yaw*3))*2.5:0;
 // Tree meshes are authored at 14-18 m with 0.5-0.6 m base radii and flares, so uniform scale gave 1-2 m trunk bases.
 // Girth applies to the horizontal axes only; height keeps the authored proportion. Root fit below uses the same transform.
 constexpr double TreeGirth=0.5;
 const double Girth=Feature.kind==wood::Kind::Tree?TreeGirth:1.0;
 FTransform Result(FRotator(Lean,Feature.yaw,0),FVector(X,Y,GroundHeight(X/100,Y/100)*100),FVector(Feature.scale*Girth,Feature.scale*Girth,Feature.scale));
 if(Feature.kind==wood::Kind::Tree) {
  double Base=DBL_MAX;
  int32 Used=0;
  for(const FVector& Contact:Profile.Roots) {
   if(Contact.ContainsNaN()) continue;
   const FVector Offset=Result.TransformVector(Contact);
   if(!FMath::IsFinite(Offset.X)||!FMath::IsFinite(Offset.Y)||!FMath::IsFinite(Offset.Z)) continue;
   if(FMath::Abs(X+Offset.X)>WoodRootLimitCm||FMath::Abs(Y+Offset.Y)>WoodRootLimitCm) continue;
   Base=FMath::Min(Base,GroundHeight((X+Offset.X)/100,(Y+Offset.Y)/100)*100-Offset.Z);
   ++Used;
  }
  // Five centimetres of soil contact hides the scan's open cut at its base.
  if(Used>0 && FMath::IsFinite(Base)) Result.SetTranslation(FVector(X,Y,Base-5));
 } else if(Feature.kind==wood::Kind::Rock) {
  // Props stay flat at terrain height under the base centre: no root fit, no tilt.
  Result.AddToTranslation(FVector(0,0,-Profile.Bounds.GetSize().Z*Feature.scale*.18));
 }
 return Result;
}
