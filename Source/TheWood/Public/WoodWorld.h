#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Generation/WoodGeneration.h"
#include "Generation/WoodMemory.h"
#include "Generation/WoodSave.h"
#include "WoodWeatherComponent.h"
#include "Async/Future.h"
#include <string>
#include "WoodWorld.generated.h"
struct FWoodRuntime;
struct FWoodPreparedChunk;
class UStaticMeshComponent;
class UStaticMesh;
class UWoodPalette;
class UProceduralMeshComponent;
class UInstancedStaticMeshComponent;
class ARectLight;
class ASkyLight;
class AExponentialHeightFog;
class UMaterialInstanceDynamic;
class UWoodWeatherComponent;
class AWoodPrecipitation;
class UMaterialParameterCollection;
struct FWoodResident;

UCLASS()
class THEWOOD_API AWoodWorld : public AActor {
 GENERATED_BODY()
public:
 AWoodWorld();
 virtual ~AWoodWorld();
 FVector ExplorerStart() const;
 void EnsureTerrainAround(FVector Position);
 // True when no streaming job is pending and the 3x3 chunks around PositionCm are detailed (terrain, flora, fauna realized).
 bool StreamingSettled(FVector PositionCm) const;
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
 // Entrance gate: Value=false keeps the trailhead lot up; true clears it.
 void SetEntered(bool Value);
 // Irreversible threshold: once past the passage with the lot occluded, the entrance becomes wilderness.
 void CheckThreshold(FVector Position);
 // True for a new or pre-threshold journey: the player starts at the trailhead lot, facing north.
 bool StartsAtTrailhead() const { return bTrailheadStart; }
 bool IsSeated() const { return Clock.seated; }
 bool IsAccelerated() const { return Clock.accelerated; }
 double ObservationSeconds() const { return Clock.seconds; }
 double ForestAt(double Xcm,double Ycm) const { return Generator.sample(Xcm/100,Ycm/100).forest; }
 // Epoch of the hex region owning (Xcm,Ycm); 0 until that region is forgotten.
 uint32 RegionEpochAt(double Xcm,double Ycm) const;
 // Hash of a chunk's generated features under the current region epochs.
 uint64 ChunkFingerprint(FIntPoint Chunk) const;
 // Resume file: ResumePath (default ProjectSavedDir/Wood/resume.json). Disabled by -WoodFresh.
 bool bResumeEnabled=true;
 FString ResumePath;
 virtual void EndPlay(const EEndPlayReason::Type EndPlayReason) override;
 // Synchronous atomic write, verified by read-back. False when disabled or on failure.
 bool SaveResumeNow();
 // Queues a background atomic write of the current state. No-op when disabled.
 void RequestResumeSave();
 // Returns and consumes the player transform restored from resume.json.
 bool TakeResumedPlayer(FVector& Location,FRotator& Rotation);
 // Audio adapter queries. Chunk keys of resident chunks; stream emitters of one chunk (cm, gains 0..1); fauna call gain at a position.
 void GetLoadedChunks(TArray<FIntPoint>& Out) const;
 void GetStreamEmitters(FIntPoint Chunk,TArray<FVector>& PositionsCm,TArray<float>& Gains) const;
 double FaunaCallGainAt(FVector PositionCm,double Seconds) const;
 const UWoodWeatherComponent* Weather() const;
 // Console WoodWeather override: ForceWeather holds a state; ClearForcedWeather resumes sampled weather.
 void ForceWeather(EWoodPrecip Kind,float Level);
 void ClearForcedWeather();
private:
 friend class FWoodThresholdTest;
 bool bEnteredWild=false;
 bool bTrailheadStart=false;
 bool bResumeReady=false;
 bool bResumedPlayer=false;
 FVector ResumedLocation=FVector::ZeroVector;
 FRotator ResumedRotation=FRotator::ZeroRotator;
 double LastAutosaveRealSeconds=0;
 TFuture<bool> ResumeWrite;
 std::string QueuedResume;
 bool bResumeQueued=false;
 bool LoadResume(wood::save::SaveState& Out) const;
 void ApplyResume(const wood::save::SaveState& Saved);
 void PrefetchResumedChunks(const wood::save::SaveState& Saved);
 wood::save::SaveState CaptureResume() const;
 void StartResumeWrite(std::string Bytes);
 void PollResumeWrite();
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
 // Flora: palette meshes to variants with wind MIDs, per-chunk instanced components (one per variant with placements), teardown.
 void BuildFlora();
 void SpawnFlora(FWoodResident& Resident, const FWoodPreparedChunk& Prepared);
 void DestroyFlora(FWoodResident& Resident);
 UPROPERTY() TArray<TObjectPtr<UInstancedStaticMeshComponent>> FloraComponents;
 UPROPERTY() TArray<TObjectPtr<UStaticMesh>> FloraKeep;
 void SpawnTrailheadLot();
 // Per-chunk fauna (2x2 fauna cells) and once-per-region landmark placeholders.
 void SpawnFauna(FWoodResident& Resident, FIntPoint Chunk);
 void SpawnLandmarks(FIntPoint Chunk);
 UPROPERTY() TObjectPtr<UProceduralMeshComponent> TrailheadLot;
 UPROPERTY() TObjectPtr<UWoodWeatherComponent> WeatherState;
 UPROPERTY() TObjectPtr<AWoodPrecipitation> Precipitation;
 UPROPERTY() TObjectPtr<UMaterialParameterCollection> WeatherParameters;
 float SnowAccum=0.0f; // 0..1 ground snow accumulation pushed to MPC_Weather "Snow"
 float WetnessClock=1.0f; // starts full so the first Tick pushes Wetness
 UPROPERTY() TArray<TObjectPtr<UStaticMeshComponent>> Landmarks;
 TSet<FIntPoint> LandmarkRegions;
};

