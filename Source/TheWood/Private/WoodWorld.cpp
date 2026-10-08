#include "WoodWorld.h"
#include "WoodRuntime.h"
#include "WoodGrounding.h"
#include "Async/Async.h"
#include "GameFramework/PlayerController.h"
#include "WoodPalette.h"
#include "Generation/WoodAtmosphere.h"
#include "ProceduralMeshComponent.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/RectLightComponent.h"
#include "Components/SkyLightComponent.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "Engine/RectLight.h"
#include "Engine/SkyLight.h"
#include "Engine/ExponentialHeightFog.h"
#include "Engine/StaticMesh.h"
#include "PhysicsEngine/BodySetup.h"
#include "Engine/TextureCube.h"
#include "Engine/World.h"
#include "Components/SceneComponent.h"
#include "Components/StaticMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Kismet/GameplayStatics.h"

AWoodWorld::~AWoodWorld() = default;
AWoodWorld::AWoodWorld():Generator(wood::Settings{}),Runtime(MakeShared<FWoodRuntime>()) {
 PrimaryActorTick.bCanEverTick=true;
 RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("GeneratedWorld"));
}
void AWoodWorld::BeginPlay() {
 Super::BeginPlay();
 FParse::Value(FCommandLine::Get(),TEXT("WoodSeed="),Seed);
 FParse::Value(FCommandLine::Get(),TEXT("WoodTime="),Clock.seconds);
 if(!FMath::IsFinite(Clock.seconds)||Clock.seconds<0) Clock.seconds=0;
 Generator=wood::World({static_cast<uint32>(Seed),128,64});
 if(!Palette) Palette=LoadObject<UWoodPalette>(nullptr,TEXT("/Game/Wood/DA_BenchmarkPalette.DA_BenchmarkPalette"));
 Generate();
 auto* Sky=NewObject<UStaticMeshComponent>(this);
 Sky->SetupAttachment(RootComponent);
 Sky->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Sphere.Sphere")));
 SkyComponent=Sky;
 Sky->SetRelativeScale3D(FVector(10000));
 Sky->SetCollisionEnabled(ECollisionEnabled::NoCollision);
 Sky->SetCastShadow(false);
 if(auto* Material=LoadObject<UMaterialInterface>(nullptr,TEXT("/Game/Wood/M_Sky.M_Sky"))) {
  SkyMaterial=UMaterialInstanceDynamic::Create(Material,this);
  Sky->SetMaterial(0,SkyMaterial);
 }
 Sky->RegisterComponent();
 AmbientLight=GetWorld()->SpawnActor<ASkyLight>();
 if(AmbientLight) {
  AmbientLight->GetLightComponent()->SetMobility(EComponentMobility::Movable);
  // A neutral specified capture supplies ambient fill without a solar source.
  auto* Ambient=AmbientLight->GetLightComponent();
  Ambient->SourceType=SLS_SpecifiedCubemap;
  Ambient->SetCubemap(LoadObject<UTextureCube>(nullptr,TEXT("/Engine/EngineResources/GrayLightTextureCube.GrayLightTextureCube")));
  Ambient->SetIntensity(1.0f);
 }
 AtmosphereFog=GetWorld()->SpawnActor<AExponentialHeightFog>();
 auto* Fog=AtmosphereFog.Get();
 if(Fog) {
  Fog->GetComponent()->SetFogDensity(0.018f);
  Fog->GetComponent()->SetFogHeightFalloff(0.02f);
  Fog->GetComponent()->SetFogInscatteringColor(FLinearColor(0.16f,0.22f,0.25f));
  Fog->GetComponent()->SetVolumetricFog(true);
 }
 UE_LOG(LogTemp,Display,TEXT("Wood seed %d: %d terrain chunks. Diagnostic art until palette approval."),Seed,Terrain.Num());
}
void AWoodWorld::Generate() {
 TArray<TSoftObjectPtr<UStaticMesh>> Meshes;
 TArray<wood::Kind> Kinds;
 TArray<bool> Young;
 TArray<bool> PrairieMesh;
 if(Palette) {
  auto Add=[&](const TArray<TSoftObjectPtr<UStaticMesh>>& Source,wood::Kind Kind,bool IsYoung=false,bool IsPrairie=false) {
   for(const auto& Mesh:Source) { Meshes.Add(Mesh); Kinds.Add(Kind);Young.Add(IsYoung);PrairieMesh.Add(IsPrairie); }
  };
  Add(Palette->Trees,wood::Kind::Tree); Add(Palette->Saplings,wood::Kind::Tree,true); Add(Palette->Ferns,wood::Kind::Fern);
  Add(Palette->Grasses,wood::Kind::Grass); Add(Palette->Rocks,wood::Kind::Rock); Add(Palette->Prairie,wood::Kind::Grass,false,true);
 }
 for(int32 Index=0;Index<Meshes.Num();++Index) {
  auto* Instances=NewObject<UInstancedStaticMeshComponent>(this);
  Instances->SetupAttachment(RootComponent);
  auto* Asset=Meshes[Index].LoadSynchronous();
  if(Asset && Kinds[Index]==wood::Kind::Tree) {
   // Foliage cards must never act as walls. Only the grounded trunk collides.
   Asset->CreateBodySetup();
   auto* Body=Asset->GetBodySetup();
   Body->AggGeom.EmptyElements();
   const float Height=static_cast<float>(Asset->GetBoundingBox().GetSize().Z);
   const float Radius=FMath::Clamp(Height*0.018f,12.0f,45.0f);
   FKSphylElem Trunk(Radius,FMath::Max(Height-2*Radius,1.0f));
   Trunk.Center=FVector(0,0,Height/2);
   Body->AggGeom.SphylElems.Add(Trunk);
   Body->CollisionTraceFlag=CTF_UseSimpleAsComplex;
   Body->InvalidatePhysicsData();
   Body->CreatePhysicsMeshes();
  }
  Instances->SetStaticMesh(Asset);
  if(Asset && Kinds[Index]!=wood::Kind::Rock) {
   for(int32 Slot=0;Slot<Asset->GetStaticMaterials().Num();++Slot) {
    if(auto* Material=Instances->CreateDynamicMaterialInstance(Slot)) WindMaterials.Add(Material);
   }
  }
  Instances->SetCollisionEnabled(Kinds[Index]==wood::Kind::Tree||Kinds[Index]==wood::Kind::Rock?ECollisionEnabled::QueryAndPhysics:ECollisionEnabled::NoCollision);
  const bool Understory=Kinds[Index]==wood::Kind::Fern||Kinds[Index]==wood::Kind::Grass;
  Instances->SetCullDistances(Understory?3500:25000,Understory?8000:45000);
  Instances->SetWorldPositionOffsetDisableDistance(Understory?6000:14000);
  if(Understory) Instances->SetCastShadow(false);
  // Crown motion is only a few centimetres; retain its cached ground shadow.
  if(Kinds[Index]==wood::Kind::Tree) Instances->ShadowCacheInvalidationBehavior=EShadowCacheInvalidationBehavior::Rigid;
  Instances->RegisterComponent();
  Vegetation.Add(Instances);
  Runtime->Available.Add(Asset!=nullptr);
  Runtime->Kinds.Add(Kinds[Index]);
  auto Profile=Asset?WoodPlacementProfile(*Asset):FWoodPlacementProfile{};Profile.Young=Young[Index];Profile.Prairie=PrairieMesh[Index];
  Runtime->Profiles.Add(Profile);
 }
 const FVector Start=ExplorerStart();
 const int32 CX=FMath::FloorToInt(Start.X/12800),CY=FMath::FloorToInt(Start.Y/12800);
 for(int32 Y=CY-1;Y<=CY+1;++Y) for(int32 X=CX-1;X<=CX+1;++X) Realize(WoodPrepareChunk(Generator,X,Y,Runtime->Kinds,Runtime->Profiles,Runtime->Available));
 Stream(Start);
}
void AWoodWorld::Tick(float DeltaSeconds) {
 Super::Tick(DeltaSeconds);
 Clock.advance(DeltaSeconds/Clock.rate());
 const APawn* Viewer=GetWorld()->GetFirstPlayerController()?GetWorld()->GetFirstPlayerController()->GetPawn():nullptr;
 const FVector Position=Viewer?Viewer->GetActorLocation():FVector::ZeroVector;
 Stream(Position);
 if(SkyComponent) SkyComponent->SetWorldLocation(Position);
 const auto Habitat=Generator.sample(Position.X/100,Position.Y/100);
 const auto Weather=wood::atmosphere(Habitat.forest,Position.X/100,Position.Y/100,Clock.seconds);
 const auto LocalLight=Generator.lighting(Position.X/100,Position.Y/100,Clock.seconds);
 if(SkyMaterial) {
  SkyMaterial->SetScalarParameterValue(TEXT("SkyBrightness"),static_cast<float>(4*LocalLight.brightness*(1-0.45*Weather.cloudCover)));
  SkyMaterial->SetScalarParameterValue(TEXT("CloudCover"),static_cast<float>(Weather.cloudCover));
 }
 if(AmbientLight) AmbientLight->GetLightComponent()->SetIntensity(static_cast<float>(0.25+0.75*LocalLight.brightness*(1-0.45*Weather.cloudCover)));
  const float CurrentWind=static_cast<float>(Weather.windStrength);
  static float LastWindValue=-1.0f;
  if(FMath::Abs(CurrentWind-LastWindValue)>0.005f) {
   LastWindValue=CurrentWind;
   for(const auto& Material:WindMaterials) Material->SetScalarParameterValue(TEXT("WindStrength"),CurrentWind);
  }
 if(AtmosphereFog) {
  AtmosphereFog->SetActorLocation(FVector(Position.X,Position.Y,Position.Z+1200));
  AtmosphereFog->GetComponent()->SetFogDensity(static_cast<float>(0.014+Weather.fogDensity));
 }
 for(int32 Index=0;Index<RegionLights.Num();++Index) {
  auto* Component=Cast<URectLightComponent>(RegionLights[Index]->GetLightComponent());
  const auto Light=Generator.lighting(RegionLights[Index]->GetActorLocation().X/100,RegionLights[Index]->GetActorLocation().Y/100,Clock.seconds);
  Component->SetIntensity(static_cast<float>(Light.brightness*50000*(1-0.45*Weather.cloudCover)));
  Component->SetTemperature(static_cast<float>(Light.kelvin));
 }
 // DeltaSeconds already includes dilation; the observation core receives real time.
}
double AWoodWorld::GroundAt(double X,double Y) const { return Generator.terrainHeight(X/100,Y/100)*100; }
double AWoodWorld::DepthAt(double X,double Y) const { return Generator.sample(X/100,Y/100).depth; }
uint32 AWoodWorld::RegionEpochAt(double Xcm,double Ycm) const {
 const auto Cell=Generator.regionOwner(Xcm/100,Ycm/100);
 return Memory.epoch(wood::memory::RegionKey{Cell.q,Cell.r});
}
uint64 AWoodWorld::ChunkFingerprint(FIntPoint Chunk) const {
 const auto Built=Generator.generate(Chunk.X,Chunk.Y);
 uint64 Hash=1469598103934665603ull;
 auto Mix=[&Hash](uint64 Value){Hash^=Value;Hash*=1099511628211ull;};
 for(const auto& F:Built.features) {
  Mix(static_cast<uint64>(F.kind));
  Mix(static_cast<uint64>(static_cast<int64>(F.position.x*1000)));
  Mix(static_cast<uint64>(static_cast<int64>(F.position.y*1000)));
  Mix(static_cast<uint64>(static_cast<int64>(F.scale*1000)));
 }
 return Hash;
}
void AWoodWorld::SetSeated(bool Value) {
 Clock.sit(Value); UGameplayStatics::SetGlobalTimeDilation(GetWorld(),static_cast<float>(Clock.rate()));
}
void AWoodWorld::ToggleAcceleration() {
 Clock.accelerate(!Clock.accelerated); UGameplayStatics::SetGlobalTimeDilation(GetWorld(),static_cast<float>(Clock.rate()));
}

