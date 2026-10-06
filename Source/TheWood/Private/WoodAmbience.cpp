#include "WoodAmbience.h"
#include "WoodWorld.h"
#include "Generation/WoodSoundscape.h"
#include "Generation/WoodAtmosphere.h"
#include "Components/AudioComponent.h"
#include "Components/SceneComponent.h"
#include "Sound/SoundWaveProcedural.h"
#include "Camera/PlayerCameraManager.h"
#include "GameFramework/PlayerController.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include <atomic>

namespace {
constexpr int32 AmbRate=32000;
constexpr int32 AmbChunk=1024;
}
struct FWoodAmbienceState {
 std::atomic<float> Wind{0}, Forest{0}, Stream{0}, Seconds{0};
 wood::Soundscape Synth{12345u,double(AmbRate)};
};
AWoodAmbience::AWoodAmbience() {
 PrimaryActorTick.bCanEverTick=true;
 USceneComponent* Root=CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
 SetRootComponent(Root);
}
void AWoodAmbience::BeginPlay() {
 Super::BeginPlay();
 for(TActorIterator<AWoodWorld> It(GetWorld());It;++It) { World=*It; break; }
 State=MakeShared<FWoodAmbienceState,ESPMode::ThreadSafe>();
 Wave=NewObject<USoundWaveProcedural>(this);
 Wave->SetSampleRate(AmbRate);
 Wave->NumChannels=2;
 Wave->Duration=INDEFINITELY_LOOPING_DURATION;
 Wave->SoundGroup=SOUNDGROUP_Default;
 Wave->bLooping=false;
 TSharedPtr<FWoodAmbienceState,ESPMode::ThreadSafe> S=State;
 // Audio-thread callback: tops up the FIFO from the synth. No exceptions escape.
 Wave->OnSoundWaveProceduralUnderflow.BindLambda([S](USoundWaveProcedural* Sound,int32 Needed) {
  if(!S.IsValid()||!Sound) return;
  S->Synth.setParams(wood::SoundParams{S->Wind.load(),S->Forest.load(),S->Stream.load(),S->Seconds.load()});
  const int32 Frames=FMath::Max(AmbChunk,Needed/4+1);
  const int32 Capped=FMath::Min(Frames,AmbChunk*4);
  TArray<float,TInlineAllocator<AmbChunk*8>> Mix; Mix.SetNumUninitialized(Capped*2);
  S->Synth.render(Mix.GetData(),Capped,2);
  TArray<int16,TInlineAllocator<AmbChunk*8>> Pcm; Pcm.SetNumUninitialized(Capped*2);
  for(int32 I=0;I<Capped*2;++I) Pcm[I]=static_cast<int16>(FMath::Clamp(Mix[I],-1.f,1.f)*32767.f);
  Sound->QueueAudio(reinterpret_cast<const uint8*>(Pcm.GetData()),Capped*2*sizeof(int16));
 });
 Audio=NewObject<UAudioComponent>(this);
 Audio->bAllowSpatialization=false;
 Audio->bAutoActivate=false;
 Audio->SetVolumeMultiplier(Volume);
 Audio->SetSound(Wave);
 Audio->RegisterComponent();
 Audio->Play();
}
void AWoodAmbience::Tick(float DeltaSeconds) {
 Super::Tick(DeltaSeconds);
 if(!State.IsValid()||!World) return;
 const APlayerController* Controller=GetWorld()->GetFirstPlayerController();
 FVector P=FVector::ZeroVector;
 if(Controller&&Controller->PlayerCameraManager) P=Controller->PlayerCameraManager->GetCameraLocation();
 const double Seconds=World->ObservationSeconds();
 const double Forest=World->ForestAt(P.X,P.Y);
 const auto Weather=wood::atmosphere(Forest,P.X/100,P.Y/100,Seconds);
 // Nearest water within a ~30 m ring; closer water is louder.
 double Near=3000;
 for(double R:{0.,1000.,2000.,3000.}) for(int32 K=0;K<(R>0?8:1);++K) {
  const double A=K*UE_DOUBLE_TWO_PI/8;
  if(World->DepthAt(P.X+R*FMath::Cos(A),P.Y+R*FMath::Sin(A))>0) { Near=FMath::Min(Near,R); break; }
 }
 State->Wind.store(static_cast<float>(Weather.windStrength));
 State->Forest.store(static_cast<float>(Forest));
 State->Stream.store(static_cast<float>(1.0-Near/3000.0));
 State->Seconds.store(static_cast<float>(Seconds));
 if(Audio) Audio->SetVolumeMultiplier(Volume);
}
