#pragma once
#include "CoreMinimal.h"
#include "Generation/WoodGeneration.h"

class UStaticMesh;

// Immutable value snapshot: create on the game thread, then copy into jobs.
struct FWoodPlacementProfile {
 TArray<FVector> Roots;
 FBox Bounds{ForceInit};
 bool Young=false;
 bool Prairie=false;
 int32 PropId=-1;
 int32 KitId=-1;
 // Tree species (wood::Species index) for Tree meshes; -1 otherwise.
 int32 Species=-1;
};
// Palette Props slots and prop bucket count; prop buckets are 6+propId.
inline constexpr int32 WoodPropCount=4;
// Palette Kit slots (kitId order, WoodKit.h); kit buckets are WoodKitBucketBase+kitId.
inline constexpr int32 WoodKitCount=21;
inline constexpr int32 WoodKitBucketBase=6+WoodPropCount;
// Bucket map (candidate tables, WoodPreparedChunk.cpp): 0-3 kinds, 4 young, 5 prairie, 6-9 props,
// 10-30 kits, 31-35 tree species (WoodSpeciesBucketBase+species), 36 deadwood.
inline constexpr int32 WoodSpeciesCount=wood::kSpeciesCount;
inline constexpr int32 WoodSpeciesBucketBase=WoodKitBucketBase+WoodKitCount;
inline constexpr int32 WoodDeadwoodBucket=WoodSpeciesBucketBase+WoodSpeciesCount;
inline constexpr int32 WoodBucketCount=WoodDeadwoodBucket+1;
// Kit meshes with collision: walls, piers, abutments, boulders. Rubble, debris, fern patch, foundation and stepping stones have none.
// Landmark kits 15-20 (tower, spire, ring base, standing stones) are solid; logs and stump snag are not.
inline bool WoodKitSolid(int32 KitId) { return KitId==0||KitId==2||KitId==3||KitId==7||KitId==9||KitId==10||(KitId>=15&&KitId<=20); }
THEWOOD_API FWoodPlacementProfile WoodPlacementProfile(const UStaticMesh& Asset);

// Cached imported root skirt vertices, in local Unreal centimetres.
THEWOOD_API const TArray<FVector>& WoodRootContacts(const UStaticMesh& Asset);
// Fits all transformed root contacts to the rendered terrain, including negative chunks.
THEWOOD_API FTransform WoodGroundedTransform(const wood::World& World, const wood::Feature& Feature, const UStaticMesh& Asset);
THEWOOD_API FTransform WoodGroundedTransform(const wood::World& World, const wood::Feature& Feature, const FWoodPlacementProfile& Profile);
// A job can provide a cheap triangle sampler over its already-realized chunk.
// GroundHeight takes and returns metres, including contacts beyond chunk edges.
THEWOOD_API FTransform WoodGroundedTransform(const wood::Feature& Feature, const FWoodPlacementProfile& Profile, TFunctionRef<double(double,double)> GroundHeight);
