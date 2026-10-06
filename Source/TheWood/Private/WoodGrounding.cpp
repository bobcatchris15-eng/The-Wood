#include "WoodGrounding.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"

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
 if(Contacts.IsEmpty()) Contacts.Add(FVector(0,0,Asset.GetBoundingBox().Min.Z));
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
 const double Lean=Feature.kind==wood::Kind::Tree?FMath::Sin(FMath::DegreesToRadians(Feature.yaw*3))*2.5:0;
 FTransform Result(FRotator(Lean,Feature.yaw,0),FVector(X,Y,GroundHeight(X/100,Y/100)*100),FVector(Feature.scale));
 if(Feature.kind==wood::Kind::Tree) {
  double Base=DBL_MAX;
  for(const FVector& Contact:Profile.Roots) {
   const FVector Offset=Result.TransformVector(Contact);
   Base=FMath::Min(Base,GroundHeight((X+Offset.X)/100,(Y+Offset.Y)/100)*100-Offset.Z);
  }
  // Five centimetres of soil contact hides the scan's open cut at its base.
  if(!Profile.Roots.IsEmpty()) Result.SetTranslation(FVector(X,Y,Base-5));
 } else if(Feature.kind==wood::Kind::Rock) {
  Result.AddToTranslation(FVector(0,0,-Profile.Bounds.GetSize().Z*Feature.scale*.18));
 }
 return Result;
}
