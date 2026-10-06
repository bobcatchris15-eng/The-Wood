#pragma once
#include "CoreMinimal.h"
#include "Generation/WoodGeneration.h"

class UStaticMesh;

// Immutable value snapshot: create on the game thread, then copy into jobs.
struct FWoodPlacementProfile {
 TArray<FVector> Roots;
 FBox Bounds{ForceInit};
 bool Young=false;
};
THEWOOD_API FWoodPlacementProfile WoodPlacementProfile(const UStaticMesh& Asset);

// Cached imported root skirt vertices, in local Unreal centimetres.
THEWOOD_API const TArray<FVector>& WoodRootContacts(const UStaticMesh& Asset);
// Fits all transformed root contacts to the rendered terrain, including negative chunks.
THEWOOD_API FTransform WoodGroundedTransform(const wood::World& World, const wood::Feature& Feature, const UStaticMesh& Asset);
THEWOOD_API FTransform WoodGroundedTransform(const wood::World& World, const wood::Feature& Feature, const FWoodPlacementProfile& Profile);
// A job can provide a cheap triangle sampler over its already-realized chunk.
// GroundHeight takes and returns metres, including contacts beyond chunk edges.
THEWOOD_API FTransform WoodGroundedTransform(const wood::Feature& Feature, const FWoodPlacementProfile& Profile, TFunctionRef<double(double,double)> GroundHeight);
