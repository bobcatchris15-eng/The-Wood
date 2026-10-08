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
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TSoftObjectPtr<UMaterialInterface> GroundMaterial;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TSoftObjectPtr<UMaterialInterface> WaterMaterial;
};
