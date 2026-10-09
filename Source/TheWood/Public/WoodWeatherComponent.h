#pragma once
#include "CoreMinimal.h"
#include "Components/ActorComponent.h"
#include "WoodWeatherComponent.generated.h"

namespace wood { class World; }

UENUM(BlueprintType)
enum class EWoodPrecip : uint8 { Clear, Overcast, Rain, Snow };

// Samples the engine-free weather core once per second at the region under the owner.
UCLASS(ClassGroup=(Wood), meta=(BlueprintSpawnableComponent))
class THEWOOD_API UWoodWeatherComponent : public UActorComponent {
 GENERATED_BODY()
public:
 UWoodWeatherComponent();
 // Called by the owning world each frame; takes one sample per accumulated second.
 void Advance(float DeltaSeconds, const wood::World& World, FVector Position, double WorldClockSeconds);
 UPROPERTY(BlueprintReadOnly, Category="Wood|Weather") EWoodPrecip Precip=EWoodPrecip::Clear;
 UPROPERTY(BlueprintReadOnly, Category="Wood|Weather") float Intensity=0.0f; // 0..1
 UPROPERTY(BlueprintReadOnly, Category="Wood|Weather") float Wetness=0.0f;   // 0..1
 UPROPERTY(BlueprintReadOnly, Category="Wood|Weather") float Wind=0.0f;      // m/s
 // Additive fog density nudge, 1/cm.
 float FogDensityBoost() const { return 0.02f*Intensity; }
 // Multiplier for ambient sky light intensity.
 float AmbientScale() const { return 1.0f-0.3f*Intensity; }
private:
 float Accumulator=1.0f; // starts full so the first Advance samples immediately
};
