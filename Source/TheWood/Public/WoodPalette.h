#pragma once
#include "CoreMinimal.h"
#include "Engine/DataAsset.h"
#include "WoodPalette.generated.h"
class UStaticMesh;
class UMaterialInterface;

UCLASS(BlueprintType)
class THEWOOD_API UWoodPalette : public UDataAsset {
 GENERATED_BODY()
public:
 // All mesh pivots should be at their ground contact, in centimetres.
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> Trees;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> Saplings;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> Ferns;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> Grasses;
 // Prairie-layer (type 3) clumps, >=0.6m footprint; kept separate from the shared Grasses slot.
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> Prairie;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> Rocks;
 // Prop meshes (E2): array index is the propId carried by Kind::Prop features.
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> Props;
 // Masonry kit meshes (discovery pieces): array index is the kitId from WoodKit.h.
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> Kit;
 // Species canopy (LOD0 <=150k tris, 3 LODs). Broadleaf holds the jacaranda old-growth giant and tree_small_02.
 // Not yet routed by the runtime; population is the next task.
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> BroadleafTrees;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> ConiferTrees;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> EvergreenTrees;
 // Fallen logs (no collision, no wind).
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> DeadWood;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TSoftObjectPtr<UMaterialInterface> GroundMaterial;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TSoftObjectPtr<UMaterialInterface> WaterMaterial;
 // Trailhead lot gravel (M_Gravel_Lot): vertex alpha drives edge fade.
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TSoftObjectPtr<UMaterialInterface> LotMaterial;
};
