#include "WoodWeatherComponent.h"
#include "Generation/WoodGeneration.h"
#include "Generation/WoodWeather.h"
#include "Generation/WoodSoundscape.h"

UWoodWeatherComponent::UWoodWeatherComponent() {
 PrimaryComponentTick.bCanEverTick=false;
}

void UWoodWeatherComponent::Force(EWoodPrecip Kind, float Level) {
 bForced=true;
 Precip=Kind;
 Intensity=Kind==EWoodPrecip::Clear?0.0f:FMath::Clamp(Level,0.0f,1.0f);
 Wetness=Kind==EWoodPrecip::Rain?Intensity:0.0f;
}

void UWoodWeatherComponent::ClearForce() {
 bForced=false;
 Accumulator=1.0f; // resample on the next Advance
}

void UWoodWeatherComponent::Advance(float DeltaSeconds, const wood::World& World, FVector Position, double WorldClockSeconds) {
 if(bForced) return;
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
 const wood::LayerGains Layers=wood::weatherLayers(Sample);
 RainGain=static_cast<float>(Layers.rain);
 WindGain=static_cast<float>(Layers.wind);
 DripGain=static_cast<float>(Layers.drip);
 BirdsongGain=static_cast<float>(Layers.birdsong);
 AmbientGain=static_cast<float>(Layers.ambient);
}
