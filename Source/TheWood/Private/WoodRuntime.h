#pragma once
#include "WoodGrounding.h"
#include "WoodPreparedChunk.h"
#include "Async/Future.h"
#include "Components/InstancedStaticMeshComponent.h"
class AWoodCreature;
class UMaterialInstanceDynamic;
// One flora mesh variant: palette species (WoodFlora.h table index), root profile and per-slot wind MIDs.
struct FWoodFloraVariant { UStaticMesh* Mesh=nullptr; int32 Species=-1; FWoodPlacementProfile Profile; TArray<UMaterialInstanceDynamic*> Slots; };
struct FWoodResident { UProceduralMeshComponent* Ground=nullptr; UProceduralMeshComponent* Water=nullptr; TArray<TArray<FPrimitiveInstanceId>> Instances; bool Detailed=false; TArray<TWeakObjectPtr<AWoodCreature>> Creatures; TArray<TWeakObjectPtr<UInstancedStaticMeshComponent>> Flora; };
struct FWoodRuntime {
 TMap<FIntPoint,FWoodResident> Chunks;
 // Flora variants, and per flora table index (feature.floraMesh) the variant ids to pick from.
 TArray<FWoodFloraVariant> FloraVariants;
 TMap<int32,TArray<int32>> FloraSpecies;
 TMap<FIntPoint,TFuture<FWoodPreparedChunk>> Jobs;
 TArray<bool> Available;
 TArray<wood::Kind> Kinds;
 TArray<FWoodPlacementProfile> Profiles;
 FIntPoint LightCenter{MAX_int32,MAX_int32};
};
