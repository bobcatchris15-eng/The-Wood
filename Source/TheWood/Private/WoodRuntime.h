#pragma once
#include "WoodGrounding.h"
#include "WoodPreparedChunk.h"
#include "Async/Future.h"
#include "Components/InstancedStaticMeshComponent.h"
struct FWoodResident { UProceduralMeshComponent* Ground=nullptr; UProceduralMeshComponent* Water=nullptr; TArray<TArray<FPrimitiveInstanceId>> Instances; bool Detailed=false; };
struct FWoodRuntime {
 TMap<FIntPoint,FWoodResident> Chunks;
 TMap<FIntPoint,TFuture<FWoodPreparedChunk>> Jobs;
 TArray<bool> Available;
 TArray<wood::Kind> Kinds;
 TArray<FWoodPlacementProfile> Profiles;
 FIntPoint LightCenter{MAX_int32,MAX_int32};
};
