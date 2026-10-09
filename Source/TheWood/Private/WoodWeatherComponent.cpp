#include "WoodWeatherComponent.h"
#include "Generation/WoodGeneration.h"
#include "Generation/WoodWeather.h"

UWoodWeatherComponent::UWoodWeatherComponent() {
 PrimaryComponentTick.bCanEverTick=false;
}

void UWoodWeatherComponent::Advance(float DeltaSeconds, const wood::World& World, FVector Position, double WorldClockSeconds) {
 Accumulator+=DeltaSeconds;
 if(Accumulator<1.0f) return;
 Accumulator-=1.0f;
 // Position is in cm; the core works in metres. Weather is keyed by the owning hex region.
 const auto Cell=World.regionOwner(Position.X/100.0,Position.Y/100.0);
 const auto Local=World.region(Cell.q,Cell.r);
 const auto Sample=wood::weather::sampleWeather(World.settings().seed,Cell.q,Cell.r,WorldClockSeconds,Local.temperature,Local.moisture);
 Precip=static_cast<EWoodPrecip>(static_cast<uint8>(Sample.kind));
 Intensity=static_cast<float>(Sample.intensity01);
 Wetness=static_cast<float>(Sample.wetness01);
 Wind=static_cast<float>(Sample.windMps);
}
