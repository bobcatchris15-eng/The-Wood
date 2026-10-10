#include "WoodCharacter.h"
#include "WoodCreature.h"
#include "WoodWorld.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "Components/InputComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "EngineUtils.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "Misc/CommandLine.h"
#include "Misc/DateTime.h"
#include "Misc/Guid.h"
#include "Misc/Parse.h"
#include "UnrealClient.h"
#include "TimerManager.h"
#include "WoodSettingsWidget.h"
#include "WoodGalleryWidget.h"
#include "WoodAmbience.h"
#include "Engine/Engine.h"
#include "Engine/World.h"
#include "HAL/PlatformMisc.h"
#include "Engine/StaticMesh.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Materials/MaterialInterface.h"
#include "Engine/GameViewportClient.h"
#include "Kismet/GameplayStatics.h"
#include "GameFramework/PlayerController.h"
#include "Generation/WoodLandmarks.h"
#include "Generation/WoodFauna.h"

AWoodCharacter::AWoodCharacter() {
 PrimaryActorTick.bCanEverTick=true;
 GetCapsuleComponent()->InitCapsuleSize(30,88);
 Camera=CreateDefaultSubobject<UCameraComponent>(TEXT("Eyes"));
 Camera->SetupAttachment(GetCapsuleComponent());
 Camera->SetRelativeLocation(FVector(0,0,65));
 Camera->bUsePawnControlRotation=true;
 Camera->FieldOfView=80;
 Camera->PostProcessSettings.bOverride_MotionBlurAmount=true;
 Camera->PostProcessSettings.MotionBlurAmount=0;
 bUseControllerRotationYaw=true;
 GetCharacterMovement()->MaxWalkSpeed=420;
 GetCharacterMovement()->MaxStepHeight=40;
 GetCharacterMovement()->SetWalkableFloorAngle(38);
 GetCharacterMovement()->JumpZVelocity=360;
 GetCharacterMovement()->AirControl=0.25f;
}
void AWoodCharacter::BeginPlay() {
 Super::BeginPlay();
 const FWoodSettings Settings=FWoodSettings::Load();
 ApplyRuntimeSettings(Settings);
 Settings.ApplyEngine();
 for(TActorIterator<AWoodWorld> It(GetWorld());It;++It) { Environment=*It; break; }
 if(APlayerController* PC=Cast<APlayerController>(Controller)) {
  PC->bShowMouseCursor=false; PC->SetInputMode(FInputModeGameOnly());
 }
}
void AWoodCharacter::Tick(float DeltaSeconds) {
 Super::Tick(DeltaSeconds);
 if(!Environment) return;
 const bool Seated=Environment->IsSeated();
 // -WoodEntrance: first tick places the explorer at the trailhead, eye height, facing north (+Y).
 static bool bEntrancePlaced=false;
 if(!bEntrancePlaced && FString(FCommandLine::Get()).Contains(TEXT("-WoodEntrance"))) {
  bEntrancePlaced=true;
  SetActorLocation(FVector(0,-57500,Environment->GroundAt(0,-57500)+100));
  if(Controller) Controller->SetControlRotation(FRotator(0,90,0));
  GetCharacterMovement()->StopMovementImmediately();
 }
 const FVector P=GetActorLocation();
 Environment->EnsureTerrainAround(P);
 // Sprint: no sprint while wading or seated. Ramp 0->1 over 0.5 s; speed lerps 420->700, wade cap 280 is immediate.
 const bool Wading=Environment->DepthAt(P.X,P.Y)>0.05;
 const bool Sprinting=bSprintHeld&&!Seated&&!Wading;
 constexpr float SprintRampPerSecond=2.0f;
 SprintAlpha=FMath::Clamp(SprintAlpha+(Sprinting?1.0f:-1.0f)*DeltaSeconds*SprintRampPerSecond,0.0f,1.0f);
 GetCharacterMovement()->MaxWalkSpeed=Seated?0.0f:(Wading?280.0f:FMath::Lerp(420.0f,700.0f,SprintAlpha));
 if(Camera) {
  const float Ease=SprintAlpha*SprintAlpha*(3.0f-2.0f*SprintAlpha); // smoothstep
  Camera->FieldOfView=BaseFOV+5.0f*Ease;
 }
 const FVector Goal(0,0,Seated?-20:65);
 Camera->SetRelativeLocation(FMath::VInterpTo(Camera->GetRelativeLocation(),Goal,DeltaSeconds,5));
}
void AWoodCharacter::SetupPlayerInputComponent(UInputComponent* Input) {
 Super::SetupPlayerInputComponent(Input);
 Input->BindAxis(TEXT("MoveForward"),this,&AWoodCharacter::Forward);
 Input->BindAxis(TEXT("MoveRight"),this,&AWoodCharacter::Right);
 Input->BindAxis(TEXT("Turn"),this,&AWoodCharacter::Turn);
 Input->BindAxis(TEXT("LookUp"),this,&AWoodCharacter::Look);
 Input->BindAction(TEXT("Photograph"),IE_Pressed,this,&AWoodCharacter::Photograph);
 Input->BindAction(TEXT("Sit"),IE_Pressed,this,&AWoodCharacter::Sit);
 Input->BindAction(TEXT("Accelerate"),IE_Pressed,this,&AWoodCharacter::Accelerate);
 Input->BindAction(TEXT("Jump"),IE_Pressed,this,&AWoodCharacter::StartJump);
 Input->BindAction(TEXT("Jump"),IE_Released,this,&ACharacter::StopJumping);
 Input->BindAction(TEXT("Sprint"),IE_Pressed,this,&AWoodCharacter::StartSprint);
 Input->BindAction(TEXT("Sprint"),IE_Released,this,&AWoodCharacter::StopSprint);
 Input->BindKey(EKeys::G,IE_Pressed,this,&AWoodCharacter::ToggleGallery);
 Input->BindKey(EKeys::Escape,IE_Pressed,this,&AWoodCharacter::ToggleSettings);
 Input->BindKey(EKeys::F10,IE_Pressed,this,&AWoodCharacter::ToggleSettings);
}
void AWoodCharacter::Forward(float Value) { if(Environment&&!Environment->IsSeated()) AddMovementInput(GetActorForwardVector(),Value); }
void AWoodCharacter::Right(float Value) { if(Environment&&!Environment->IsSeated()) AddMovementInput(GetActorRightVector(),Value); }
void AWoodCharacter::Turn(float Value) { AddControllerYawInput(Value*MouseSensitivity); }
void AWoodCharacter::Look(float Value) { AddControllerPitchInput(Value*MouseSensitivity*(bInvertY?-1.0f:1.0f)); }
void AWoodCharacter::StartJump() {
 if(Environment&&Environment->IsSeated()) { Environment->SetSeated(false); return; }
 Jump();
}
void AWoodCharacter::StartSprint() { SetSprintHeld(true); }
void AWoodCharacter::StopSprint() { SetSprintHeld(false); }
void AWoodCharacter::SetSprintHeld(bool bHeld) { bSprintHeld=bHeld; }
void AWoodCharacter::Sit() {
 if(Environment&&GetCharacterMovement()->IsMovingOnGround()) {
  Environment->SetSeated(!Environment->IsSeated()); GetCharacterMovement()->StopMovementImmediately();
 }
}
void AWoodCharacter::Accelerate() { if(Environment) Environment->ToggleAcceleration(); }
namespace {
// Sight length in cm from eye height along yaw; 3000 cm when nothing blocks.
double OpenSight(UWorld* World,const AActor* Self,FVector Eye,double YawDeg) {
 const FVector Dir=FRotator(0,YawDeg,0).Vector();
 FHitResult Hit;
 FCollisionQueryParams Params(SCENE_QUERY_STAT(WoodFrameClearance),true);
 Params.AddIgnoredActor(Self);
 if(World->LineTraceSingleByChannel(Hit,Eye,Eye+Dir*3000.0,ECC_Visibility,Params)) return Hit.Distance;
 return 3000.0;
}
// Keeps the authored yaw when 6 m is clear in front; otherwise takes the most open of 16 directions.
FRotator OpenFacing(UWorld* World,const AActor* Self,FVector Position,FRotator Authored) {
 if(!World) return Authored;
 const FVector Eye=Position+FVector(0,0,150);
 if(OpenSight(World,Self,Eye,Authored.Yaw)>=600.0) return Authored;
 double BestYaw=Authored.Yaw,BestLen=-1.0;
 for(int32 K=0;K<16;++K) {
  const double Yaw=K*22.5;
  const double Len=OpenSight(World,Self,Eye,Yaw);
  if(Len>BestLen) { BestLen=Len; BestYaw=Yaw; }
 }
 UE_LOG(LogTemp,Display,TEXT("WoodView authored yaw blocked; open yaw %.1f, clear %.0f cm"),BestYaw,BestLen);
 Authored.Yaw=BestYaw;
 return Authored;
}
}
void AWoodCharacter::WoodView(const FString& View) {
 if(!Environment || !Controller) return;
 wood::World Landscape(wood::Settings{static_cast<uint32>(Environment->Seed),128,64});
 FVector Position=Environment->ExplorerStart();
 const FVector Start=Position;
 FRotator Facing(-4,35,0);
 // -WoodFrameBiome=<Grassland|Taiga|Highlands|OldGrowth|ColdRainforest|IcyHills|Savannah|Swamp|Marsh|WarmRainforest|Prairie>moves the camera to the nearest core of that biome family, searched from the explorer start.
 const FString Cmd=FCommandLine::Get();
 FString FrameBiome;
 FParse::Value(*Cmd,TEXT("-WoodFrameBiome="),FrameBiome);
 if(View.Equals(TEXT("Grassland"),ESearchCase::IgnoreCase)) {
  const auto R=Landscape.region(1,0);Position=FVector(R.origin.x*100,R.origin.y*100,0);Facing=FRotator(-6,35,0);
 } else if(View.Equals(TEXT("Taiga"),ESearchCase::IgnoreCase)) {
  const auto R=Landscape.region(0,-1);Position=FVector(R.origin.x*100,R.origin.y*100,0);Facing=FRotator(-4,35,0);
 } else if(View.Equals(TEXT("Highlands"),ESearchCase::IgnoreCase)) {
  const auto R=Landscape.region(1,1);Position=FVector(R.origin.x*100,R.origin.y*100,0);Facing=FRotator(-8,35,0);
 } else if(View.Equals(TEXT("Ruins"),ESearchCase::IgnoreCase)) {
  // Frame the nearest generated ruin 12 m away, facing it; fixed fallback when none is in range.
  const auto Ruin=Landscape.nearestDiscovery(Position.X/100.0,Position.Y/100.0,900.0);
  if(Ruin&&(Cmd.Contains(TEXT("-WoodFrameRuin"))||!Cmd.Contains(TEXT("WoodStartX=")))) {
   const double Yaw=45.0,Rad=FMath::DegreesToRadians(Yaw);
   Position=FVector((Ruin->x-12.0*FMath::Cos(Rad))*100.0,(Ruin->y-12.0*FMath::Sin(Rad))*100.0,0);
   Facing=FRotator(-5,Yaw,0);
  } else {
   Position=FVector(-6800,-6800,0);Facing=FRotator(-5,45,0);
  }
 } else if(View.Equals(TEXT("Roots"),ESearchCase::IgnoreCase)) {
  const auto Chunk=Landscape.generate(-2,-2);
  for(const auto& Feature:Chunk.features) if(Feature.kind==wood::Kind::Tree) {
   Position=FVector(Feature.position.x*100-450,Feature.position.y*100,0);Facing=FRotator(-15,0,0);break;
  }
 } else if(View.Equals(TEXT("Stream"),ESearchCase::IgnoreCase)) {
  Position=FVector((Landscape.streamX(-110)-7)*100,-11000,0);
  Facing=FRotator(-8,65,0);
 } else if(View.Equals(TEXT("Ridge"),ESearchCase::IgnoreCase)) {
  double Highest=-TNumericLimits<double>::Max();
  for(double X=130;X<=240;X+=5) for(double Y=-120;Y<=120;Y+=5) {
   const auto Site=Landscape.sample(X,Y);
   if(Site.slope<0.35 && Site.height>Highest) {
    Highest=Site.height; Position=FVector(X*100,Y*100,0);
   }
  }
  Facing=FRotator(-12,180,0);
 } else if(View.Equals(TEXT("Trailhead"),ESearchCase::IgnoreCase)) {
  // Trailhead lot, 1 m south of its pad edge, facing north up the lot. Requires -WoodEntrance.
  Position=FVector(0,-57500,0);Facing=FRotator(-4,90,0);
 } else if(View.Equals(TEXT("Landmark"),ESearchCase::IgnoreCase)) {
  // Nearest lattice region holding a landmark; camera 120 m west of it, facing east.
  bool Found=false;
  for(int Ring=0;Ring<=30&&!Found;++Ring) for(int Q=-Ring;Q<=Ring&&!Found;++Q) for(int R=-Ring;R<=Ring&&!Found;++R) {
   if(FMath::Max(FMath::Abs(Q),FMath::Abs(R))!=Ring) continue;
   const auto Lm=wood::landmark::placeLandmark(static_cast<uint32>(Environment->Seed),Q,R,Landscape);
   if(!Lm) continue;
   Position=FVector((Lm->x-120.0)*100.0,Lm->y*100.0,0);Facing=FRotator(-6,0,0);
   Found=true;
  }
  if(!Found) UE_LOG(LogTemp,Warning,TEXT("No landmark within lattice ring 30; keeping start frame"));
 } else if(View.Equals(TEXT("Creature"),ESearchCase::IgnoreCase)) {
  // First fauna cell (64 m, outward from origin) with a spawn; camera 8 m west of the first spawn, facing east.
  bool Found=false;
  for(int Ring=0;Ring<=40&&!Found;++Ring) for(int Q=-Ring;Q<=Ring&&!Found;++Q) for(int R=-Ring;R<=Ring&&!Found;++R) {
   if(FMath::Max(FMath::Abs(Q),FMath::Abs(R))!=Ring) continue;
   const auto CellOwner=Landscape.regionOwner(Q*wood::fauna::kChunkM+wood::fauna::kChunkM/2,R*wood::fauna::kChunkM+wood::fauna::kChunkM/2);
   const auto Info=Landscape.region(CellOwner.q,CellOwner.r);
   const auto Spawns=wood::fauna::spawnCreatures(static_cast<uint32>(Environment->Seed),Q,R,Info.family,Info.unreal);
   if(Spawns.empty()) continue;
   Position=FVector((Q*wood::fauna::kChunkM+Spawns[0].x-8.0)*100.0,(R*wood::fauna::kChunkM+Spawns[0].y)*100.0,0);Facing=FRotator(-6,0,0);
   Found=true;
  }
  if(!Found) UE_LOG(LogTemp,Warning,TEXT("No fauna spawn within fauna ring 40; keeping start frame"));
 } else if(View.Equals(TEXT("Unreal"),ESearchCase::IgnoreCase)) {
  // Nearest unreal-flagged region, framed at its origin.
  bool Found=false;
  for(int Ring=0;Ring<=30&&!Found;++Ring) for(int Q=-Ring;Q<=Ring&&!Found;++Q) for(int R=-Ring;R<=Ring&&!Found;++R) {
   if(FMath::Max(FMath::Abs(Q),FMath::Abs(R))!=Ring) continue;
   const auto Reg=Landscape.region(Q,R);
   if(!Reg.unreal) continue;
   Position=FVector(Reg.origin.x*100.0,Reg.origin.y*100.0,0);Facing=FRotator(-4,35,0);
   Found=true;
  }
  if(!Found) UE_LOG(LogTemp,Warning,TEXT("No unreal region within lattice ring 30; keeping start frame"));
 }
 if(!FrameBiome.IsEmpty()) {
  wood::Biome Family=wood::Biome::DryGrassland;
  bool Known=true;
  if(FrameBiome.Equals(TEXT("Grassland"),ESearchCase::IgnoreCase)) Family=wood::Biome::DryGrassland;
  else if(FrameBiome.Equals(TEXT("Taiga"),ESearchCase::IgnoreCase)) Family=wood::Biome::Taiga;
  else if(FrameBiome.Equals(TEXT("Highlands"),ESearchCase::IgnoreCase)) Family=wood::Biome::RockyHighlands;
  else if(FrameBiome.Equals(TEXT("OldGrowth"),ESearchCase::IgnoreCase)) Family=wood::Biome::OldGrowthForest;
  else if(FrameBiome.Equals(TEXT("ColdRainforest"),ESearchCase::IgnoreCase)) Family=wood::Biome::ColdRainforest;
  else if(FrameBiome.Equals(TEXT("IcyHills"),ESearchCase::IgnoreCase)) Family=wood::Biome::IcyHills;
  else if(FrameBiome.Equals(TEXT("Savannah"),ESearchCase::IgnoreCase)) Family=wood::Biome::Savannah;
  else if(FrameBiome.Equals(TEXT("Swamp"),ESearchCase::IgnoreCase)) Family=wood::Biome::Swamp;
  else if(FrameBiome.Equals(TEXT("Marsh"),ESearchCase::IgnoreCase)) Family=wood::Biome::Marsh;
  else if(FrameBiome.Equals(TEXT("WarmRainforest"),ESearchCase::IgnoreCase)) Family=wood::Biome::WarmRainforest;
  else if(FrameBiome.Equals(TEXT("Prairie"),ESearchCase::IgnoreCase)) Family=wood::Biome::Prairie;
  else if(FrameBiome.Equals(TEXT("TemperateForest"),ESearchCase::IgnoreCase)) Family=wood::Biome::TemperateForest;
  else if(FrameBiome.Equals(TEXT("RockyHighlands"),ESearchCase::IgnoreCase)) Family=wood::Biome::RockyHighlands;
  else if(FrameBiome.Equals(TEXT("DryGrassland"),ESearchCase::IgnoreCase)) Family=wood::Biome::DryGrassland;
  else Known=false;
  if(!Known) {
   UE_LOG(LogTemp,Error,TEXT("Unknown -WoodFrameBiome: %s"),*FrameBiome);
  } else if(Family==wood::Biome::OldGrowthForest||Family==wood::Biome::ColdRainforest||Family==wood::Biome::IcyHills||Family==wood::Biome::Savannah||Family==wood::Biome::Swamp||Family==wood::Biome::Marsh||Family==wood::Biome::WarmRainforest||Family==wood::Biome::Prairie) {
   // Prairie joins the lattice search: no core lies within 2000 m of the start, so the nearest-core search fell back to the start frame.
   // Climate-driven families sit far from the start cell: take the nearest lattice region origin holding a core weight.
   bool Found=false;
   for(int Ring=0;Ring<=30&&!Found;++Ring) for(int Q=-Ring;Q<=Ring&&!Found;++Q) for(int R=-Ring;R<=Ring&&!Found;++R) {
    if(FMath::Max(FMath::Abs(Q),FMath::Abs(R))!=Ring) continue;
    const auto Reg=Landscape.region(Q,R);
    if(Reg.family!=Family) continue;
    if(Landscape.sample(Reg.origin.x,Reg.origin.y).biome[static_cast<std::size_t>(Family)]<0.85) continue;
    Position=FVector(Reg.origin.x*100.0,Reg.origin.y*100.0,0);
    Found=true;
   }
   if(!Found) UE_LOG(LogTemp,Warning,TEXT("No %s core within lattice ring 30; keeping fixed frame"),*FrameBiome);
  } else if(const auto Core=Landscape.nearestBiomeCore(Family,Start.X/100.0,Start.Y/100.0,2000.0,0.85)) {
   Position=FVector(Core->x*100.0,Core->y*100.0,0);
  } else {
   UE_LOG(LogTemp,Warning,TEXT("No %s core within 2000 m of explorer start; keeping fixed frame"),*FrameBiome);
  }
 }
 const auto Here=Landscape.sample(Position.X/100.0,Position.Y/100.0);
 UE_LOG(LogTemp,Display,TEXT("WoodView biome weights: TemperateForest=%.3f DryGrassland=%.3f RockyHighlands=%.3f Taiga=%.3f OldGrowth=%.3f ColdRainforest=%.3f IcyHills=%.3f Savannah=%.3f Swamp=%.3f Marsh=%.3f WarmRainforest=%.3f Prairie=%.3f"),Here.biome[0],Here.biome[1],Here.biome[2],Here.biome[3],Here.biome[4],Here.biome[5],Here.biome[6],Here.biome[7],Here.biome[8],Here.biome[9],Here.biome[10],Here.biome[11]);
 Position.Z=Environment->GroundAt(Position.X,Position.Y)+100;
 Environment->EnsureTerrainAround(Position);
 SetActorLocation(Position);
 // Biome, Taiga, Highlands, Unreal and Rain/Snow frames take the open direction; ruin, creature, landmark and stream frames keep their intended facing.
 if(!FrameBiome.IsEmpty()||View.Equals(TEXT("Taiga"),ESearchCase::IgnoreCase)||View.Equals(TEXT("Highlands"),ESearchCase::IgnoreCase)||View.Equals(TEXT("Unreal"),ESearchCase::IgnoreCase)||View.Equals(TEXT("Rain"),ESearchCase::IgnoreCase)||View.Equals(TEXT("Snow"),ESearchCase::IgnoreCase))
  Facing=OpenFacing(GetWorld(),this,Position,Facing);
 Controller->SetControlRotation(Facing);
 GetCharacterMovement()->StopMovementImmediately();
}
void AWoodCharacter::Photograph() {
 const double Now=FPlatformTime::Seconds();
 if(Now-LastPhotoSeconds<0.5||FScreenshotRequest::IsScreenshotRequested()) return;
 const FString Directory=FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Photos"));
 if(!IFileManager::Get().MakeDirectory(*Directory,true)) { UE_LOG(LogTemp,Error,TEXT("Could not create photo album: %s"),*Directory); return; }
 const FString Name=FDateTime::UtcNow().ToString(TEXT("%Y%m%d-%H%M%S-"))+FGuid::NewGuid().ToString(EGuidFormats::Digits)+TEXT(".png");
 FScreenshotRequest::RequestScreenshot(FPaths::Combine(Directory,Name),false,false);
 LastPhotoSeconds=Now;
}
void AWoodCharacter::WoodDumpView(float RadiusM) {
 // Diagnostic: instanced components with instances within RadiusM of the camera: mesh, materials, count, nearest distance.
 UWorld* World=GetWorld(); if(!World) return;
 const FVector Eye=GetActorLocation(); const double R2=FMath::Square(RadiusM*100.0);
 for(TObjectIterator<UInstancedStaticMeshComponent> It;It;++It) {
  UInstancedStaticMeshComponent* C=*It;
  if(!C||C->GetWorld()!=World||!C->GetStaticMesh()) continue;
  int32 Near=0; double Min=1e18; FTransform T; float TintSum=0; double ScaleSum=0;
  for(int32 I=0;I<C->GetInstanceCount();++I) {
   if(!C->GetInstanceTransform(I,T,true)) continue;
   const double D2=FVector::DistSquared(T.GetLocation(),Eye);
   if(D2>R2) continue;
   ++Near; Min=FMath::Min(Min,D2); ScaleSum+=T.GetScale3D().Z;
   if(C->NumCustomDataFloats>0&&C->PerInstanceSMCustomData.IsValidIndex(I*C->NumCustomDataFloats)) TintSum+=C->PerInstanceSMCustomData[I*C->NumCustomDataFloats];
  }
  if(!Near) continue;
  FString Mats;
  for(int32 M=0;M<C->GetNumMaterials();++M) Mats+=(C->GetMaterial(M)?C->GetMaterial(M)->GetPathName():TEXT("none"))+TEXT(" ");
  UE_LOG(LogTemp,Display,TEXT("WoodDump mesh=%s near=%d total=%d nearestM=%.1f meanScale=%.2f meanTint=%.2f mats=%s"),*C->GetStaticMesh()->GetPathName(),Near,C->GetInstanceCount(),FMath::Sqrt(Min)/100.0,ScaleSum/Near,TintSum/Near,*Mats);
 }
}
void AWoodCharacter::WoodCapture(const FString& View,float Delay) {
 WoodView(View);
 // Weather review views: forced precipitation at 0.8 (WoodWeather override), applied after framing.
 if(Environment&&View.Equals(TEXT("Rain"),ESearchCase::IgnoreCase)) Environment->ForceWeather(EWoodPrecip::Rain,0.8f);
 if(Environment&&View.Equals(TEXT("Snow"),ESearchCase::IgnoreCase)) Environment->ForceWeather(EWoodPrecip::Snow,0.8f);
 if(Environment&&View.Equals(TEXT("Creature"),ESearchCase::IgnoreCase)) {
  // Freeze every creature and place a deer 8 m ahead on the ground, facing the camera, so the subject cannot retreat before the shot.
  AWoodCreature::bFreezeAll=true;
  FRotator Look=Controller?Controller->GetControlRotation():FRotator::ZeroRotator;
  // Face the most open of 16 directions so no trunk stands between the camera and the subject.
  double BestYaw=Look.Yaw,BestLen=-1.0;
  for(int32 K=0;K<16;++K) {
   const double Len=OpenSight(GetWorld(),this,GetActorLocation(),K*22.5);
   if(Len>BestLen) { BestLen=Len; BestYaw=K*22.5; }
  }
  Look.Yaw=BestYaw; Look.Pitch=-6.0f;
  if(Controller) Controller->SetControlRotation(Look);
  FVector Where=GetActorLocation()+FRotator(0,Look.Yaw,0).Vector()*800.0;
  Where.Z=Environment->GroundAt(Where.X,Where.Y);
  Environment->EnsureTerrainAround(Where);
  Where.Z=Environment->GroundAt(Where.X,Where.Y);
  if(auto* Subject=GetWorld()->SpawnActor<AWoodCreature>(Where,FRotator(0,Look.Yaw+180.0f,0))) {
   Subject->Init(wood::fauna::CreatureKind::Deer,Environment,Look.Yaw+180.0f);
   TWeakObjectPtr<AWoodCreature> Weak=Subject;
   FTimerHandle ProbeTimer;
   GetWorldTimerManager().SetTimer(ProbeTimer,FTimerDelegate::CreateLambda([this,Weak]{
    if(!Weak.IsValid()) { UE_LOG(LogTemp,Display,TEXT("WoodCapture: creature subject destroyed")); return; }
    const FBox Box=Weak->GetComponentsBoundingBox();
    UE_LOG(LogTemp,Display,TEXT("WoodCapture: creature subject at %s bounds %s hidden=%d camera %s"),*Weak->GetActorLocation().ToString(),*Box.GetSize().ToString(),Weak->IsHidden()?1:0,*GetActorLocation().ToString());
   }),1.5f,false);
   UE_LOG(LogTemp,Display,TEXT("WoodCapture: creature subject placed at %s camera %s yaw %.1f sight %.0f"),*Where.ToString(),*GetActorLocation().ToString(),Look.Yaw,BestLen);
  }
 }
 if(FParse::Param(FCommandLine::Get(),TEXT("WoodDumpView"))) {
  FTimerHandle DumpTimer;
  GetWorldTimerManager().SetTimer(DumpTimer,FTimerDelegate::CreateLambda([this]{ WoodDumpView(60.0f); }),FMath::Max(Delay,0.1f)*0.8f,false);
 }
 // Settle gate: poll every 0.1 s; photograph once the minimum delay and 30 frames have passed and the camera's chunks are resident.
 // Timeout after 30 s past the delay captures anyway with a warning. The run exits 3 s after the shot.
 const double MinDelay=FMath::Max(Delay,0.1f);
 const double Start=FPlatformTime::Seconds();
 const uint64 StartFrame=GFrameCounter;
 TSharedRef<FTimerHandle> Poll=MakeShared<FTimerHandle>();
 GetWorldTimerManager().SetTimer(*Poll,FTimerDelegate::CreateLambda([this,Poll,Start,StartFrame,MinDelay]{
  const double Elapsed=FPlatformTime::Seconds()-Start;
  const bool Settled=Environment&&Environment->StreamingSettled(GetActorLocation());
  const bool Ready=Elapsed>=MinDelay&&GFrameCounter-StartFrame>=30&&Settled;
  if(!Ready&&Elapsed<MinDelay+30.0) { if(Environment) Environment->EnsureTerrainAround(GetActorLocation()); return; }
  if(!Ready) UE_LOG(LogTemp,Warning,TEXT("WoodCapture: settle timeout, capturing unsettled view"));
  GetWorldTimerManager().ClearTimer(*Poll);
  Photograph();
  FTimerHandle ExitTimer;
  GetWorldTimerManager().SetTimer(ExitTimer,FTimerDelegate::CreateLambda([]{ FPlatformMisc::RequestExit(false); }),3.0f,false);
 }),0.1f,true);
}
void AWoodCharacter::ApplyRuntimeSettings(const FWoodSettings& S) {
 MouseSensitivity=S.MouseSensitivity;
 bInvertY=S.bInvertY;
 BaseFOV=S.FOV;
 if(Camera) Camera->FieldOfView=S.FOV;
 WoodSetAudioVolumes(S.MasterVolume,S.AmbientVolume);
}
void AWoodCharacter::ToggleGallery() {
 if(Gallery) { CloseMenu(); return; }
 if(SettingsMenu) return;
 APlayerController* PC=Cast<APlayerController>(Controller);
 if(!PC||!GEngine||!GEngine->GameViewport) return;
 Gallery=SNew(SWoodGallery).OnRequestClose(FSimpleDelegate::CreateUObject(this,&AWoodCharacter::CloseMenu));
 GEngine->GameViewport->AddViewportWidgetContent(Gallery.ToSharedRef(),100);
 UGameplayStatics::SetGamePaused(GetWorld(),true);
 PC->bShowMouseCursor=true;
 PC->SetInputMode(FInputModeUIOnly().SetWidgetToFocus(Gallery));
}
void AWoodCharacter::ToggleSettings() {
 if(SettingsMenu) { HandleSettingsClosed(SettingsMenu->GetValues()); return; }
 if(Gallery) return;
 APlayerController* PC=Cast<APlayerController>(Controller);
 if(!PC||!GEngine||!GEngine->GameViewport) return;
 SettingsMenu=SNew(SWoodSettings)
  .Initial(FWoodSettings::Load())
  .OnChanged(FOnWoodSettingsEvent::CreateUObject(this,&AWoodCharacter::HandleSettingsChanged))
  .OnClosed(FOnWoodSettingsEvent::CreateUObject(this,&AWoodCharacter::HandleSettingsClosed));
 GEngine->GameViewport->AddViewportWidgetContent(SettingsMenu.ToSharedRef(),100);
 PC->bShowMouseCursor=true;
 PC->SetInputMode(FInputModeUIOnly().SetWidgetToFocus(SettingsMenu));
}
void AWoodCharacter::HandleSettingsChanged(FWoodSettings S) {
 ApplyRuntimeSettings(S);
}
void AWoodCharacter::HandleSettingsClosed(FWoodSettings S) {
 S.Save();
 S.ApplyEngine();
 ApplyRuntimeSettings(S);
 CloseMenu();
}
void AWoodCharacter::CloseMenu() {
 if(GEngine&&GEngine->GameViewport) {
  if(Gallery) GEngine->GameViewport->RemoveViewportWidgetContent(Gallery.ToSharedRef());
  if(SettingsMenu) GEngine->GameViewport->RemoveViewportWidgetContent(SettingsMenu.ToSharedRef());
 }
 Gallery.Reset();
 SettingsMenu.Reset();
 UGameplayStatics::SetGamePaused(GetWorld(),false);
 if(APlayerController* PC=Cast<APlayerController>(Controller)) {
  PC->bShowMouseCursor=false;
  PC->SetInputMode(FInputModeGameOnly());
 }
}
