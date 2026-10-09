#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WoodAmbience.generated.h"
class UAudioComponent;
class USoundWaveProcedural;
class AWoodWorld;
struct FWoodAmbienceState;

// Player volume (0..1 each). Applied to every Wood audio component on the next ambience Tick.
// Set from ApplyRuntimeSettings; the values persist through FWoodSettings (WoodSettings.ini).
THEWOOD_API void WoodSetAudioVolumes(float Master,float Ambient);

// One spatial stream emitter, owned by a resident chunk and destroyed with it.
USTRUCT()
struct FWoodEmitterAudio {
 GENERATED_BODY()
 UPROPERTY() TObjectPtr<UAudioComponent> Audio;
 UPROPERTY() TObjectPtr<USoundWaveProcedural> Wave;
 FIntPoint Chunk=FIntPoint::ZeroValue;
 FVector Position=FVector::ZeroVector;
 float Gain=0.0f;
};

UCLASS()
class THEWOOD_API AWoodAmbience : public AActor {
 GENERATED_BODY()
public:
 AWoodAmbience();
 virtual void BeginPlay() override;
 virtual void Tick(float DeltaSeconds) override;
 UPROPERTY(EditAnywhere, Category="Audio", meta=(ClampMin="0", ClampMax="2")) float Volume=0.5f;
private:
 UPROPERTY() TObjectPtr<UAudioComponent> Audio;
 UPROPERTY() TObjectPtr<USoundWaveProcedural> Wave;
 UPROPERTY() TObjectPtr<AWoodWorld> World;
 // Weather layers, index 0 rain, 1 wind, 2 drip, 3 birdsong. Procedural mono loops.
 UPROPERTY() TArray<TObjectPtr<UAudioComponent>> LayerAudio;
 UPROPERTY() TArray<TObjectPtr<USoundWaveProcedural>> LayerWaves;
 // Stream emitters for every resident chunk; parallel to nothing, each entry carries its own chunk key.
 UPROPERTY() TArray<FWoodEmitterAudio> Emitters;
 TSet<FIntPoint> SpawnedChunks;
 void SyncStreamEmitters(const TArray<FIntPoint>& Loaded);
 void SpawnEmitter(FIntPoint Chunk,FVector Position,float Gain);
 void DestroyEmitter(int32 Index);
 TSharedPtr<FWoodAmbienceState, ESPMode::ThreadSafe> State;
};
