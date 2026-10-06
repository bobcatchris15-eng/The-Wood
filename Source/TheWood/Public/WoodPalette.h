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
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TArray<TSoftObjectPtr<UStaticMesh>> Rocks;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TSoftObjectPtr<UMaterialInterface> GroundMaterial;
 UPROPERTY(EditAnywhere, BlueprintReadOnly) TSoftObjectPtr<UMaterialInterface> WaterMaterial;
};
