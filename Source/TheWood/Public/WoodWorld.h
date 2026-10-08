#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Generation/WoodGeneration.h"
#include "Generation/WoodMemory.h"
#include "WoodWorld.generated.h"
struct FWoodRuntime;
struct FWoodPreparedChunk;
class UStaticMeshComponent;
class UWoodPalette;
class UProceduralMeshComponent;
class UInstancedStaticMeshComponent;
class ARectLight;
class ASkyLight;
class AExponentialHeightFog;
class UMaterialInstanceDynamic;

UCLASS()
class THEWOOD_API AWoodWorld : public AActor {
 GENERATED_BODY()
public:
 AWoodWorld();
 virtual ~AWoodWorld();
 FVector ExplorerStart() const;
 void EnsureTerrainAround(FVector Position);
 int32 LoadedChunkCount() const;
 virtual void BeginPlay() override;
 virtual void Tick(float DeltaSeconds) override;
 UPROPERTY(EditAnywhere, Category="Generation") int32 Seed=12345;
 UPROPERTY(EditAnywhere, Category="Generation", meta=(ClampMin="1", ClampMax="4")) int32 ChunkRadius=4;
 // Shared-clock seconds a region may go unobserved before it is forgotten.
 UPROPERTY(EditAnywhere, Category="Generation", meta=(ClampMin="0")) float ForgetGraceSeconds=90.0f;
 UPROPERTY(EditAnywhere, Category="Art") TObjectPtr<UWoodPalette> Palette;
 double GroundAt(double Xcm,double Ycm) const;
 double DepthAt(double Xcm,double Ycm) const;
 void SetSeated(bool Value);
 void ToggleAcceleration();
 bool IsSeated() const { return Clock.seated; }
 bool IsAccelerated() const { return Clock.accelerated; }
 double ObservationSeconds() const { return Clock.seconds; }
 double ForestAt(double Xcm,double Ycm) const { return Generator.sample(Xcm/100,Ycm/100).forest; }
 // Epoch of the hex region owning (Xcm,Ycm); 0 until that region is forgotten.
 uint32 RegionEpochAt(double Xcm,double Ycm) const;
 // Hash of a chunk's generated features under the current region epochs.
 uint64 ChunkFingerprint(FIntPoint Chunk) const;
private:
 wood::World Generator{wood::Settings{}};
 wood::Observation Clock;
 wood::memory::RegionMemory Memory;
 UPROPERTY() TArray<TObjectPtr<UProceduralMeshComponent>> Terrain;
 UPROPERTY() TArray<TObjectPtr<UProceduralMeshComponent>> Water;
 UPROPERTY() TObjectPtr<UStaticMeshComponent> SkyComponent;
 UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> Vegetation;
 UPROPERTY() TArray<TObjectPtr<ARectLight>> RegionLights;
 UPROPERTY() TObjectPtr<ASkyLight> AmbientLight;
 UPROPERTY() TObjectPtr<AExponentialHeightFog> AtmosphereFog;
 UPROPERTY() TObjectPtr<UMaterialInstanceDynamic> SkyMaterial;
 UPROPERTY() TArray<TObjectPtr<UMaterialInstanceDynamic>> WindMaterials;
 TSharedPtr<FWoodRuntime> Runtime;
 void Generate();
 void Stream(FVector Position);
 void UpdateForgetting();
 void Realize(const FWoodPreparedChunk& Prepared, bool Detailed=true);
};

