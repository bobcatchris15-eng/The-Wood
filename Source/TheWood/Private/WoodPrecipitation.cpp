#include "WoodPrecipitation.h"
#include "WoodWorld.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInterface.h"
#include "Engine/World.h"
#include "EngineUtils.h"
#include "GameFramework/PlayerController.h"
#include "HAL/IConsoleManager.h"

namespace {
constexpr int32 RainCapacity=4000;
constexpr int32 SnowCapacity=2500;
constexpr int32 AtlasGrid=4;          // 4x4 atlas, index = row*4+col
constexpr float BoxHalfCm=1500.0f;    // 30 m box around the camera
constexpr float BoxTopCm=2000.0f;     // spawn up to 20 m above the camera
constexpr float GroundMarginCm=300.0f;
constexpr float RainFallCmPerS=900.0f;
constexpr float SnowFallCmPerS=120.0f;

// Stateless hash in [0,1). Visual scatter only; world generation stays on random(seed,gx,gy,salt).
float Noise(uint32 A,uint32 B) {
 uint32 H=(A*0x9E3779B1u)^((B+0x7F4A7C15u)*0x85EBCA77u);
 H^=H>>15; H*=0x2C1B3C6Du; H^=H>>12; H*=0x297A2D39u; H^=H>>15;
 return static_cast<float>(H&0xFFFFFFu)/16777216.0f;
}

void WoodWeatherCommand(const TArray<FString>& Args,UWorld* World) {
 AWoodWorld* Wood=nullptr;
 for(TActorIterator<AWoodWorld> It(World);It;++It) { Wood=*It; break; }
 if(!Wood) { UE_LOG(LogTemp,Warning,TEXT("WoodWeather: no AWoodWorld in level")); return; }
 const FString Mode=Args.Num()>0?Args[0].ToLower():FString();
 const float Level=Args.Num()>1?FCString::Atof(*Args[1]):1.0f;
 if(Mode==TEXT("clear")) Wood->ForceWeather(EWoodPrecip::Clear,0.0f);
 else if(Mode==TEXT("rain")) Wood->ForceWeather(EWoodPrecip::Rain,Level);
 else if(Mode==TEXT("snow")) Wood->ForceWeather(EWoodPrecip::Snow,Level);
 else if(Mode==TEXT("auto")) Wood->ClearForcedWeather();
 else UE_LOG(LogTemp,Warning,TEXT("Usage: WoodWeather <clear|rain|snow|auto> [intensity 0..1]"));
}
FAutoConsoleCommandWithWorldAndArgs GWoodWeatherCommand(
 TEXT("WoodWeather"),
 TEXT("WoodWeather <clear|rain|snow|auto> [intensity]"),
 FConsoleCommandWithWorldAndArgsDelegate::CreateStatic(&WoodWeatherCommand));
}

AWoodPrecipitation::AWoodPrecipitation() {
 PrimaryActorTick.bCanEverTick=false;
 RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("PrecipitationRoot"));
}

void AWoodPrecipitation::Drive(float DeltaSeconds,FVector CenterCm,EWoodPrecip Kind,float Intensity,float WindMps,float CameraYawDeg) {
 if(!bReady) Initialize();
 const float Dt=FMath::Clamp(DeltaSeconds,0.0f,0.1f);
 const float Level=FMath::Clamp(Intensity,0.0f,1.0f);
 // Wind drift in cm/s, toward +X/+Y. Rain takes the full drift; snow takes half, as it floats.
 const FVector Drift(WindMps*80.0f,WindMps*60.0f,0.0f);
 const int32 RainActive=Kind==EWoodPrecip::Rain?FMath::RoundToInt(RainCapacity*Level):0;
 const int32 SnowActive=Kind==EWoodPrecip::Snow?FMath::RoundToInt(SnowCapacity*Level):0;
 // Plane mesh is 100 cm square; scale 0.08 x 0.9 gives an 8 cm x 90 cm streak (was 4 x 50 cm, invisible in a still frame), 0.07 gives a 7 cm flake.
 Step(RainPool,RainFlakes,RainActive,Dt,CenterCm,Drift,RainFallCmPerS,FVector(0.45f,1.4f,1.0f),CameraYawDeg,101);
 Step(SnowPool,SnowFlakes,SnowActive,Dt,CenterCm,Drift*0.5f,SnowFallCmPerS,FVector(0.2f,0.2f,1.0f),CameraYawDeg,202);
}

void AWoodPrecipitation::Initialize() {
 bReady=true;
 UStaticMesh* Quad=LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Plane.Plane"));
 UMaterialInterface* RainMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Wood/M_Rain.M_Rain"));
 UMaterialInterface* SnowMaterial=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Wood/M_Snow.M_Snow"));
 RainPool=MakePool(TEXT("RainPool"),Quad,RainMaterial,RainCapacity);
 SnowPool=MakePool(TEXT("SnowPool"),Quad,SnowMaterial,SnowCapacity);
 // Far below any camera, so every flake respawns on its first step.
 RainFlakes.SetNum(RainCapacity);
 SnowFlakes.SetNum(SnowCapacity);
 for(auto& F:RainFlakes) F.Pos.Z=-1.0e9f;
 for(auto& F:SnowFlakes) F.Pos.Z=-1.0e9f;
}

UInstancedStaticMeshComponent* AWoodPrecipitation::MakePool(const TCHAR* Name,UStaticMesh* Mesh,UMaterialInterface* Material,int32 Count) {
 auto* Pool=NewObject<UInstancedStaticMeshComponent>(this,FName(Name));
 Pool->SetupAttachment(RootComponent);
 Pool->SetMobility(EComponentMobility::Movable);
 Pool->SetStaticMesh(Mesh);
 if(Material) Pool->SetMaterial(0,Material);
 Pool->SetCollisionEnabled(ECollisionEnabled::NoCollision);
 Pool->SetCastShadow(false);
 // Custom data 0/1 carry the atlas column and row for each instance.
 Pool->NumCustomDataFloats=2;
 Pool->RegisterComponent();
 // Zero-scale instances are hidden until a flake is activated.
 TArray<FTransform> Hidden;
 Hidden.Init(FTransform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector),Count);
 Pool->AddInstances(Hidden,false);
 return Pool;
}

void AWoodPrecipitation::Step(UInstancedStaticMeshComponent* Pool,TArray<FWoodFlake>& Flakes,int32 Active,float Dt,FVector Center,FVector Drift,float Fall,FVector Scale,float CameraYawDeg,uint32 Salt) {
 if(!Pool) return;
 const int32 Count=Flakes.Num();
 // Billboard: tilt the XY plane upright (Y to Z; normal becomes -Y), then yaw by heading+90 so the normal faces along the view axis (was edge-on). Quads are two-sided.
 const FQuat Facing=FRotator(0.0f,CameraYawDeg+90.0f,0.0f).Quaternion()*FQuat(FVector::XAxisVector,PI*0.5f);
 TArray<FTransform> Transforms;
 Transforms.Reserve(Count);
 for(int32 I=0;I<Count;++I) {
  FWoodFlake& F=Flakes[I];
  if(I>=Active) {
   Transforms.Add(FTransform(FQuat::Identity,FVector::ZeroVector,FVector::ZeroVector));
   continue;
  }
  F.Pos+=Drift*Dt;
  F.Pos.Z-=Fall*F.Speed*Dt;
  const bool Outside=FMath::Abs(F.Pos.X-Center.X)>BoxHalfCm||FMath::Abs(F.Pos.Y-Center.Y)>BoxHalfCm;
  if(F.Pos.Z<Center.Z-GroundMarginCm||Outside) {
   // Respawn across the top of the box. A running draw counter keeps every respawn distinct.
   const uint32 Id=++Draws;
   F.Pos=FVector(Center.X+(Noise(Id,Salt)-0.5f)*2.0f*BoxHalfCm,
                 Center.Y+(Noise(Id,Salt+1)-0.5f)*2.0f*BoxHalfCm,
                 Center.Z+BoxTopCm*(0.2f+0.8f*Noise(Id,Salt+2)));
   F.Speed=0.85f+0.3f*Noise(Id,Salt+3);
   F.Atlas=FMath::Min(static_cast<int32>(Noise(Id,Salt+4)*AtlasGrid*AtlasGrid),AtlasGrid*AtlasGrid-1);
   Pool->SetCustomDataValue(I,0,static_cast<float>(F.Atlas%AtlasGrid),false);
   Pool->SetCustomDataValue(I,1,static_cast<float>(F.Atlas/AtlasGrid),false);
  }
  Transforms.Add(FTransform(Facing,F.Pos,Scale));
 }
 if(Count>0) Pool->BatchUpdateInstancesTransforms(0,Transforms,true,true,false);
}
