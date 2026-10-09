#include "WoodAmbience.h"
#include "WoodWorld.h"
#include "WoodWeatherComponent.h"
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
#include <cmath>
#include <memory>

namespace {
constexpr int32 AmbRate=32000;
constexpr int32 AmbChunk=1024;
// Procedural layers are mono and cheap; the emitter range is where a stream stops being audible.
constexpr int32 LayerRate=22050;
constexpr int32 LayerChunk=512;
constexpr double EmitterRangeM=150.0;
constexpr double Pi=3.141592653589793;
constexpr double Tau=6.283185307179586;

// Player settings, stored as atomics: written from the game thread, read on Tick.
std::atomic<float> gMaster{1.0f};
std::atomic<float> gAmbient{1.0f};
float AudioMix() { return gMaster.load()*gAmbient.load(); }

enum class ELayer : uint8 { Rain, Wind, Drip, Birdsong, Burble };

// Mono layer synth. Touched only on the audio thread; gains are applied by the component's volume multiplier.
struct FLayerSynth {
 ELayer Kind;
 uint32 Rng;
 double Lo=0, Hi=0, Brown=0, Phase=0, Env=0, Freq=0, Lfo=0, T=1.0;
 FLayerSynth(ELayer InKind,uint32 Seed) : Kind(InKind), Rng(Seed|1u) {}
 double Uniform() { Rng^=Rng<<13; Rng^=Rng>>17; Rng^=Rng<<5; return Rng*(1.0/4294967296.0); }
 double White() { return 2.0*Uniform()-1.0; }
 float Next();
};

float FLayerSynth::Next() {
 const double Rate=LayerRate;
 double Out=0;
 switch(Kind) {
 case ELayer::Rain: {
  // Filtered white noise: high-passed hiss.
  const double N=White();
  Lo+=0.5*(N-Lo);
  Out=0.5*(N-Lo);
  break;
 }
 case ELayer::Wind: {
  // Low-passed brown noise: slow rumble with a leak so it does not drift.
  Brown=0.998*Brown+0.02*White();
  Out=2.5*Brown;
  break;
 }
 case ELayer::Drip: {
  // Sparse decaying sine plinks, about 0.6 per second.
  if(Uniform()<0.6/Rate) { Env=1.0; Freq=1200.0+1800.0*Uniform(); Phase=0; }
  Out=0.6*Env*std::sin(Phase);
  Phase+=Tau*Freq/Rate; if(Phase>Tau) Phase-=Tau;
  Env*=std::exp(-1.0/(0.04*Rate));
  break;
 }
 case ELayer::Birdsong: {
  // Short frequency-swept chirps with a trill, about 0.5 per second.
  constexpr double ChirpLen=0.15;
  if(T>=ChirpLen && Uniform()<0.5/Rate) { T=0; Freq=2600.0+1400.0*Uniform(); Phase=0; }
  if(T<ChirpLen) {
   const double Win=std::sin(Pi*T/ChirpLen);
   const double F=Freq*(1.0+0.12*std::sin(Tau*32.0*T));
   Out=0.5*Win*Win*std::sin(Phase);
   Phase+=Tau*F/Rate; if(Phase>Tau) Phase-=Tau;
   T+=1.0/Rate;
  }
  break;
 }
 case ELayer::Burble: {
  // Stream burble: band between about 100 and 900 Hz, slow bubbling envelope.
  const double N=White();
  Lo+=0.03*(N-Lo);
  Hi+=0.25*(N-Hi);
  Lfo+=Tau*0.7/Rate; if(Lfo>Tau) Lfo-=Tau;
  const double Bubble=0.55+0.45*std::sin(Lfo);
  Out=1.6*(Hi-Lo)*Bubble;
  break;
 }
 }
 return FMath::Clamp(static_cast<float>(Out),-1.0f,1.0f);
}

void PumpLayer(FLayerSynth& S,USoundWaveProcedural* Sound,int32 Needed) {
 if(!Sound) return;
 const int32 Frames=FMath::Clamp(FMath::Max(LayerChunk,Needed/2+1),LayerChunk,LayerChunk*4);
 TArray<int16> Pcm;
 Pcm.SetNumUninitialized(Frames);
 for(int32 I=0;I<Frames;++I) Pcm[I]=static_cast<int16>(S.Next()*32767.f);
 Sound->QueueAudio(reinterpret_cast<const uint8*>(Pcm.GetData()),Frames*sizeof(int16));
}

USoundWaveProcedural* MakeLayerWave(UObject* Outer,TSharedPtr<FLayerSynth,ESPMode::ThreadSafe> Synth) {
 auto* Wave=NewObject<USoundWaveProcedural>(Outer);
 Wave->SetSampleRate(LayerRate);
 Wave->NumChannels=1;
 Wave->Duration=INDEFINITELY_LOOPING_DURATION;
 Wave->SoundGroup=SOUNDGROUP_Default;
 Wave->bLooping=false;
 // Audio-thread callback. The synth is owned by the shared pointer, so the lambda never outlives it.
 Wave->OnSoundWaveProceduralUnderflow.BindLambda([Synth](USoundWaveProcedural* Sound,int32 Needed) {
  if(Synth.IsValid()) PumpLayer(*Synth,Sound,Needed);
 });
 return Wave;
}
}

struct FWoodAmbienceState {
 std::atomic<float> Wind{0}, Forest{0}, Stream{0}, Seconds{0};
 wood::Soundscape Synth{12345u,double(AmbRate)};
};

void WoodSetAudioVolumes(float Master,float Ambient) {
 gMaster.store(FMath::Clamp(Master,0.0f,1.0f));
 gAmbient.store(FMath::Clamp(Ambient,0.0f,1.0f));
}

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
 Audio->SetVolumeMultiplier(Volume*AudioMix());
 Audio->SetSound(Wave);
 Audio->RegisterComponent();
 Audio->Play();

 // Weather layers: rain, wind, drip, birdsong. Each has its own seed so the loops do not correlate.
 const ELayer Kinds[4]={ELayer::Rain,ELayer::Wind,ELayer::Drip,ELayer::Birdsong};
 for(int32 I=0;I<4;++I) {
  auto Synth=MakeShared<FLayerSynth,ESPMode::ThreadSafe>(Kinds[I],static_cast<uint32>(1000+I*7919));
  USoundWaveProcedural* LayerWave=MakeLayerWave(this,Synth);
  auto* Comp=NewObject<UAudioComponent>(this);
  Comp->bAllowSpatialization=false;
  Comp->bAutoActivate=false;
  Comp->SetSound(LayerWave);
  Comp->RegisterComponent();
  Comp->Play();
  LayerWaves.Add(LayerWave);
  LayerAudio.Add(Comp);
 }
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
 const float Mix=AudioMix();
 if(Audio) Audio->SetVolumeMultiplier(Volume*Mix);

 // Weather layers follow the once-per-second weather sample. Birdsong also follows the fauna call gain.
 if(LayerAudio.Num()==4) {
  if(const UWoodWeatherComponent* W=World->Weather()) {
   const double Fauna=World->FaunaCallGainAt(P,Seconds);
   LayerAudio[0]->SetVolumeMultiplier(static_cast<float>(W->RainGain)*Mix);
   LayerAudio[1]->SetVolumeMultiplier(static_cast<float>(W->WindGain*W->AmbientGain)*Mix);
   LayerAudio[2]->SetVolumeMultiplier(static_cast<float>(W->DripGain)*Mix);
   LayerAudio[3]->SetVolumeMultiplier(static_cast<float>(W->BirdsongGain*Fauna)*Mix);
  }
 }

 // Stream emitters: spawned per resident chunk, destroyed with it, attenuated by distance from the camera.
 TArray<FIntPoint> Loaded;
 World->GetLoadedChunks(Loaded);
 SyncStreamEmitters(Loaded);
 for(auto& E:Emitters) {
  if(!E.Audio) continue;
  const double DistM=FVector::Dist(E.Position,P)/100.0;
  const double Falloff=FMath::Clamp(1.0-DistM/EmitterRangeM,0.0,1.0);
  E.Audio->SetVolumeMultiplier(static_cast<float>(0.8*E.Gain*Falloff*Falloff)*Mix);
 }
}

void AWoodAmbience::SyncStreamEmitters(const TArray<FIntPoint>& Loaded) {
 TSet<FIntPoint> Live;
 for(const FIntPoint& K:Loaded) Live.Add(K);
 for(int32 I=Emitters.Num()-1;I>=0;--I) if(!Live.Contains(Emitters[I].Chunk)) DestroyEmitter(I);
 for(auto It=SpawnedChunks.CreateIterator();It;++It) if(!Live.Contains(*It)) It.RemoveCurrent();
 for(const FIntPoint& K:Loaded) {
  if(SpawnedChunks.Contains(K)) continue;
  SpawnedChunks.Add(K);
  TArray<FVector> Positions;
  TArray<float> Gains;
  World->GetStreamEmitters(K,Positions,Gains);
  for(int32 I=0;I<Positions.Num()&&I<Gains.Num();++I) SpawnEmitter(K,Positions[I],Gains[I]);
 }
}

void AWoodAmbience::SpawnEmitter(FIntPoint Chunk,FVector Position,float Gain) {
 // Per-emitter seed from its position, so each stream reach bubbles differently and deterministically.
 const uint32 Seed=static_cast<uint32>(FMath::FloorToInt(Position.X))*73856093u^static_cast<uint32>(FMath::FloorToInt(Position.Y))*19349663u;
 auto Synth=MakeShared<FLayerSynth,ESPMode::ThreadSafe>(ELayer::Burble,Seed);
 USoundWaveProcedural* EmitterWave=MakeLayerWave(this,Synth);
 auto* Comp=NewObject<UAudioComponent>(this);
 Comp->bAllowSpatialization=true;
 Comp->bAutoActivate=false;
 Comp->SetSound(EmitterWave);
 Comp->RegisterComponent();
 Comp->SetWorldLocation(Position);
 Comp->Play();
 FWoodEmitterAudio E;
 E.Audio=Comp;
 E.Wave=EmitterWave;
 E.Chunk=Chunk;
 E.Position=Position;
 E.Gain=Gain;
 Emitters.Add(E);
}

void AWoodAmbience::DestroyEmitter(int32 Index) {
 if(!Emitters.IsValidIndex(Index)) return;
 FWoodEmitterAudio& E=Emitters[Index];
 if(E.Audio) {
  E.Audio->Stop();
  E.Audio->DestroyComponent();
 }
 Emitters.RemoveAtSwap(Index);
}
