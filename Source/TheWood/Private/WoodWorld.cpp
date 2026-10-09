#include "WoodWorld.h"
#include "WoodRuntime.h"
#include "WoodGrounding.h"
#include "Async/Async.h"
#include "GameFramework/PlayerController.h"
#include "WoodPalette.h"
#include "Generation/WoodAtmosphere.h"
#include "Generation/WoodEntrance.h"
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
#include "Misc/Paths.h"
#include "Misc/FileHelper.h"
#include "HAL/FileManager.h"
#include "HAL/PlatformTime.h"
#include "Kismet/GameplayStatics.h"
#include <map>
#include <memory>
#include <utility>

namespace {
// Writes Json to Path via temp file + atomic move, then reads back and verifies it parses and matches.
bool WriteResumeFile(const FString& Path,const std::string& Json) {
 IFileManager& Files=IFileManager::Get();
 Files.MakeDirectory(*FPaths::GetPath(Path),true);
 const FString Temp=Path+TEXT(".tmp");
 TArray<uint8> Bytes;
 Bytes.Append(reinterpret_cast<const uint8*>(Json.data()),static_cast<int32>(Json.size()));
 if(!FFileHelper::SaveArrayToFile(Bytes,*Temp)) { UE_LOG(LogTemp,Error,TEXT("Resume temp write failed: %s"),*Temp); return false; }
 if(!Files.Move(*Path,*Temp,true,true)) { Files.Delete(*Temp); UE_LOG(LogTemp,Error,TEXT("Resume move failed: %s"),*Path); return false; }
 TArray<uint8> Readback;
 if(!FFileHelper::LoadFileToArray(Readback,*Path)) return false;
 const std::string Text(reinterpret_cast<const char*>(Readback.GetData()),static_cast<std::size_t>(Readback.Num()));
 return Text==Json && wood::save::fromJson(Text).has_value();
}
}

AWoodWorld::~AWoodWorld() = default;
AWoodWorld::AWoodWorld():Generator(wood::Settings{}),Runtime(MakeShared<FWoodRuntime>()) {
 PrimaryActorTick.bCanEverTick=true;
 RootComponent=CreateDefaultSubobject<USceneComponent>(TEXT("GeneratedWorld"));
 bResumeEnabled=!FString(FCommandLine::Get()).Contains(TEXT("-WoodFresh"));
 ResumePath=FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Wood"),TEXT("resume.json"));
}
void AWoodWorld::BeginPlay() {
 Super::BeginPlay();
 FParse::Value(FCommandLine::Get(),TEXT("WoodSeed="),Seed);
 FParse::Value(FCommandLine::Get(),TEXT("WoodTime="),Clock.seconds);
 if(!FMath::IsFinite(Clock.seconds)||Clock.seconds<0) Clock.seconds=0;
 Generator=wood::World({static_cast<uint32>(Seed),128,64});
 // Startup: (1) valid resume → as saved; (2) otherwise new journey at the lot; -WoodWild skips the entrance (dev/test).
 const bool Wild=FString(FCommandLine::Get()).Contains(TEXT("-WoodWild"));
 wood::save::SaveState Resume;
 const bool Resuming=bResumeEnabled&&LoadResume(Resume);
 if(Resuming) ApplyResume(Resume);
 const bool Lot=!Wild&&(!Resuming||!Resume.enteredWild);
 if(Wild) Generator.setEntered(true);
 else if(Lot) Generator.setEntered(false);
 // A new journey replaces any stale resume; its first autosave rewrites the file.
 if(!Resuming&&!Wild&&bResumeEnabled) IFileManager::Get().Delete(*ResumePath);
 bTrailheadStart=Lot;
 if(!Palette) Palette=LoadObject<UWoodPalette>(nullptr,TEXT("/Game/Wood/DA_BenchmarkPalette.DA_BenchmarkPalette"));
 Generate();
 if(Lot&&!Generator.entered()) SpawnTrailheadLot();
 if(Resuming) PrefetchResumedChunks(Resume);
 LastAutosaveRealSeconds=FPlatformTime::Seconds();
 bResumeReady=true;
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
 TArray<int32> PropIds;
 TArray<int32> KitIds;
 if(Palette) {
  auto Add=[&](const TArray<TSoftObjectPtr<UStaticMesh>>& Source,wood::Kind Kind,bool IsYoung=false,bool IsPrairie=false) {
   for(const auto& Mesh:Source) { Meshes.Add(Mesh); Kinds.Add(Kind);Young.Add(IsYoung);PrairieMesh.Add(IsPrairie);PropIds.Add(-1);KitIds.Add(-1); }
  };
  Add(Palette->Trees,wood::Kind::Tree); Add(Palette->Saplings,wood::Kind::Tree,true); Add(Palette->Ferns,wood::Kind::Fern);
  Add(Palette->Grasses,wood::Kind::Grass); Add(Palette->Rocks,wood::Kind::Rock); Add(Palette->Prairie,wood::Kind::Grass,false,true);
  // Palette index is the propId; slots beyond WoodPropCount have no bucket and are skipped.
  for(int32 PropId=0;PropId<Palette->Props.Num()&&PropId<WoodPropCount;++PropId) {
   Meshes.Add(Palette->Props[PropId]); Kinds.Add(wood::Kind::Prop); Young.Add(false); PrairieMesh.Add(false); PropIds.Add(PropId); KitIds.Add(-1);
  }
  // Palette index is the kitId; slots beyond WoodKitCount have no bucket and are skipped.
  for(int32 KitId=0;KitId<Palette->Kit.Num()&&KitId<WoodKitCount;++KitId) {
   Meshes.Add(Palette->Kit[KitId]); Kinds.Add(wood::Kind::Kit); Young.Add(false); PrairieMesh.Add(false); PropIds.Add(-1); KitIds.Add(KitId);
  }
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
  if(Asset && Kinds[Index]!=wood::Kind::Rock && Kinds[Index]!=wood::Kind::Prop && Kinds[Index]!=wood::Kind::Kit) {
   for(int32 Slot=0;Slot<Asset->GetStaticMaterials().Num();++Slot) {
    if(auto* Material=Instances->CreateDynamicMaterialInstance(Slot)) WindMaterials.Add(Material);
   }
  }
  const bool Solid=Kinds[Index]==wood::Kind::Tree||Kinds[Index]==wood::Kind::Rock||Kinds[Index]==wood::Kind::Prop||(Kinds[Index]==wood::Kind::Kit&&WoodKitSolid(KitIds[Index]));
  Instances->SetCollisionEnabled(Solid?ECollisionEnabled::QueryAndPhysics:ECollisionEnabled::NoCollision);
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
  auto Profile=Asset?WoodPlacementProfile(*Asset):FWoodPlacementProfile{};Profile.Young=Young[Index];Profile.Prairie=PrairieMesh[Index];Profile.PropId=PropIds[Index];Profile.KitId=KitIds[Index];
  Runtime->Profiles.Add(Profile);
 }
 const FVector Start=ExplorerStart();
 const int32 CX=FMath::FloorToInt(Start.X/12800),CY=FMath::FloorToInt(Start.Y/12800);
 for(int32 Y=CY-1;Y<=CY+1;++Y) for(int32 X=CX-1;X<=CX+1;++X) Realize(WoodPrepareChunk(Generator,X,Y,Runtime->Kinds,Runtime->Profiles,Runtime->Available));
 Stream(Start);
}
void AWoodWorld::SetEntered(bool Value) {
 // Never revert: a crossed threshold stays crossed for this journey.
 if(!Value&&bEnteredWild) return;
 if(Value) bTrailheadStart=false;
 Generator.setEntered(Value);
 if(Value&&TrailheadLot) { TrailheadLot->DestroyComponent(); TrailheadLot=nullptr; }
}
void AWoodWorld::SpawnTrailheadLot() {
 if(TrailheadLot) return;
 // Lot pad from the core (metres, converted to cm), skirt fading vertex alpha to 0.
 namespace entrance=wood::entrance;
 constexpr double PadMinX=(entrance::LotX-entrance::LotHalfW)*100,PadMaxX=(entrance::LotX+entrance::LotHalfW)*100;
 constexpr double PadMinY=(entrance::LotY-entrance::LotHalfH)*100,PadMaxY=(entrance::LotY+entrance::LotHalfH)*100;
 constexpr double Skirt=entrance::LotPadSkirt*100,Cell=100;
 constexpr int32 NX=static_cast<int32>((PadMaxX-PadMinX+2*Skirt)/Cell);
 constexpr int32 NY=static_cast<int32>((PadMaxY-PadMinY+2*Skirt)/Cell);
 const double X0=PadMinX-Skirt,Y0=PadMinY-Skirt;
 TArray<FVector> Verts,Normals;
 TArray<FVector2D> UVs;
 TArray<FColor> Colors;
 TArray<int32> Tris;
 Verts.Reserve((NX+1)*(NY+1));
 for(int32 J=0;J<=NY;++J) for(int32 I=0;I<=NX;++I) {
  const double X=X0+I*Cell,Y=Y0+J*Cell;
  const double Z=GroundAt(X,Y)+3.0;
  const double Gx=GroundAt(X+Cell,Y)-GroundAt(X-Cell,Y),Gy=GroundAt(X,Y+Cell)-GroundAt(X,Y-Cell);
  Verts.Add(FVector(X,Y,Z));
  Normals.Add(FVector(-Gx,-Gy,2*Cell).GetSafeNormal());
  UVs.Add(FVector2D(X/200.0,Y/200.0));
  const double Dx=FMath::Max3(PadMinX-X,0.0,X-PadMaxX),Dy=FMath::Max3(PadMinY-Y,0.0,Y-PadMaxY);
  const double Alpha=FMath::Clamp(1.0-FMath::Sqrt(Dx*Dx+Dy*Dy)/Skirt,0.0,1.0);
  Colors.Add(FColor(255,255,255,static_cast<uint8>(FMath::RoundToInt(Alpha*255.0))));
 }
 for(int32 J=0;J<NY;++J) for(int32 I=0;I<NX;++I) {
  const int32 V00=J*(NX+1)+I,V10=V00+1,V01=V00+(NX+1),V11=V01+1;
  Tris.Append({V00,V01,V10,V10,V01,V11});
 }
 TrailheadLot=NewObject<UProceduralMeshComponent>(this,TEXT("TrailheadLot"));
 TrailheadLot->SetupAttachment(RootComponent);
 TrailheadLot->CreateMeshSection(0,Verts,Tris,Normals,UVs,Colors,TArray<FProcMeshTangent>(),false);
 if(Palette) if(auto* Material=Palette->LotMaterial.LoadSynchronous()) TrailheadLot->SetMaterial(0,Material);
 TrailheadLot->SetCollisionEnabled(ECollisionEnabled::NoCollision);
 TrailheadLot->SetCastShadow(false);
 TrailheadLot->RegisterComponent();
}
void AWoodWorld::Tick(float DeltaSeconds) {
 Super::Tick(DeltaSeconds);
 PollResumeWrite();
 // Autosave every 60 s of real time while walking (real time, not dilated shared clock).
 if(bResumeReady&&!Clock.seated&&FPlatformTime::Seconds()-LastAutosaveRealSeconds>=60.0) RequestResumeSave();
 Clock.advance(DeltaSeconds/Clock.rate());
 const APawn* Viewer=GetWorld()->GetFirstPlayerController()?GetWorld()->GetFirstPlayerController()->GetPawn():nullptr;
 const FVector Position=Viewer?Viewer->GetActorLocation():FVector::ZeroVector;
 CheckThreshold(Position);
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
 const bool Standing=Clock.seated&&!Value;
 Clock.sit(Value); UGameplayStatics::SetGlobalTimeDilation(GetWorld(),static_cast<float>(Clock.rate()));
 if(Standing) RequestResumeSave();
}
void AWoodWorld::ToggleAcceleration() {
 Clock.accelerate(!Clock.accelerated); UGameplayStatics::SetGlobalTimeDilation(GetWorld(),static_cast<float>(Clock.rate()));
}

// ---------------------------------------------------------------- resume

bool AWoodWorld::LoadResume(wood::save::SaveState& Out) const {
 // First run has no save: check existence so a missing file is silent rather than a streaming warning.
 if(!IFileManager::Get().FileExists(*ResumePath)) return false;
 TArray<uint8> Bytes;
 if(!FFileHelper::LoadFileToArray(Bytes,*ResumePath) || Bytes.Num()==0) return false;
 const std::string Json(reinterpret_cast<const char*>(Bytes.GetData()),static_cast<std::size_t>(Bytes.Num()));
 const auto Parsed=wood::save::fromJson(Json);
 if(!Parsed) { UE_LOG(LogTemp,Warning,TEXT("Resume file rejected, starting fresh: %s"),*ResumePath); return false; }
 if(Parsed->seed!=static_cast<uint32>(Seed)) { UE_LOG(LogTemp,Display,TEXT("Resume seed %u differs from world seed %d, starting fresh"),Parsed->seed,Seed); return false; }
 Out=*Parsed;
 return true;
}
void AWoodWorld::ApplyResume(const wood::save::SaveState& Saved) {
 // Must run before Generate(): regenerated chunks take their epochs from the generator.
 Clock.sit(Saved.seated);
 Clock.accelerate(Saved.accelerated);
 Clock.seconds=FMath::Max(0.0,Saved.clockSeconds);
 UGameplayStatics::SetGlobalTimeDilation(GetWorld(),static_cast<float>(Clock.rate()));
 // Threshold restored before first generation: resumed wild entrance has no lot and no zone features.
 if(Saved.enteredWild) { bEnteredWild=true; Generator.setEntered(true); }
 Memory.restore(Saved.epochs);
 auto Snapshot=std::make_shared<std::map<wood::memory::RegionKey,std::uint32_t>>();
 for(const auto& Epoch:Saved.epochs) Snapshot->insert(Epoch);
 Generator.setEpochs([Snapshot](int q,int r){const auto It=Snapshot->find(wood::memory::RegionKey{q,r});return It==Snapshot->end()?std::uint32_t{0}:It->second;});
 bResumedPlayer=true;
 ResumedLocation=FVector(Saved.playerX,Saved.playerY,Saved.playerZ);
 ResumedRotation=FRotator(Saved.pitch,Saved.yaw,0);
}
void AWoodWorld::PrefetchResumedChunks(const wood::save::SaveState& Saved) {
 for(const auto& Coordinate:Saved.retainedChunks) {
  const FIntPoint Key(Coordinate.x,Coordinate.y);
  if(Runtime->Chunks.Contains(Key)||Runtime->Jobs.Contains(Key)) continue;
  const wood::World Snapshot=Generator;const auto Kinds=Runtime->Kinds;const auto Profiles=Runtime->Profiles;const auto Available=Runtime->Available;
  Runtime->Jobs.Add(Key,Async(EAsyncExecution::ThreadPool,[Snapshot,Key,Kinds,Profiles,Available](){return WoodPrepareChunk(Snapshot,Key.X,Key.Y,Kinds,Profiles,Available);}));
 }
}
wood::save::SaveState AWoodWorld::CaptureResume() const {
 wood::save::SaveState State;
 State.seed=static_cast<uint32>(Seed);
 const APlayerController* PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;
 if(const APawn* Pawn=PC?PC->GetPawn():nullptr) {
  const FVector P=Pawn->GetActorLocation();
  const FRotator R=PC->GetControlRotation();
  State.playerX=P.X; State.playerY=P.Y; State.playerZ=P.Z;
  State.yaw=R.Yaw; State.pitch=R.Pitch;
 }
 State.clockSeconds=Clock.seconds;
 State.seated=Clock.seated;
 State.accelerated=Clock.accelerated;
 State.enteredWild=bEnteredWild;
 for(const auto& Entry:Runtime->Chunks) State.retainedChunks.push_back({Entry.Key.X,Entry.Key.Y});
 State.epochs=Memory.epochs();
 return State;
}
void AWoodWorld::RequestResumeSave() {
 if(!bResumeEnabled) return;
 LastAutosaveRealSeconds=FPlatformTime::Seconds();
 StartResumeWrite(wood::save::toJson(CaptureResume()));
}
bool AWoodWorld::SaveResumeNow() {
 if(!bResumeEnabled) return false;
 if(ResumeWrite.IsValid()) { ResumeWrite.Wait(); ResumeWrite=TFuture<bool>(); }
 bResumeQueued=false;
 LastAutosaveRealSeconds=FPlatformTime::Seconds();
 const bool Ok=WriteResumeFile(ResumePath,wood::save::toJson(CaptureResume()));
 if(!Ok) UE_LOG(LogTemp,Error,TEXT("Resume save failed: %s"),*ResumePath);
 return Ok;
}
void AWoodWorld::StartResumeWrite(std::string Bytes) {
 if(ResumeWrite.IsValid()) { QueuedResume=std::move(Bytes); bResumeQueued=true; return; }
 ResumeWrite=Async(EAsyncExecution::ThreadPool,[Path=ResumePath,Payload=std::move(Bytes)](){return WriteResumeFile(Path,Payload);});
}
void AWoodWorld::PollResumeWrite() {
 if(!ResumeWrite.IsValid()||!ResumeWrite.IsReady()) return;
 if(!ResumeWrite.Get()) UE_LOG(LogTemp,Error,TEXT("Resume save failed: %s"),*ResumePath);
 ResumeWrite=TFuture<bool>();
 if(bResumeQueued) { bResumeQueued=false; StartResumeWrite(std::move(QueuedResume)); }
}
bool AWoodWorld::TakeResumedPlayer(FVector& Location,FRotator& Rotation) {
 if(!bResumedPlayer) return false;
 bResumedPlayer=false;
 Location=ResumedLocation;
 Rotation=ResumedRotation;
 return true;
}
void AWoodWorld::EndPlay(const EEndPlayReason::Type EndPlayReason) {
 if(bResumeReady) SaveResumeNow();
 bResumeReady=false;
 Super::EndPlay(EndPlayReason);
}

