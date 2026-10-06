#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "WoodAmbience.generated.h"
class UAudioComponent;
class USoundWaveProcedural;
class AWoodWorld;
struct FWoodAmbienceState;

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
 TSharedPtr<FWoodAmbienceState, ESPMode::ThreadSafe> State;
};
