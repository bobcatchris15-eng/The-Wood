#include "WoodCharacter.h"
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
#include "Engine/GameViewportClient.h"
#include "Kismet/GameplayStatics.h"
#include "GameFramework/PlayerController.h"

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
 GetCharacterMovement()->MaxWalkSpeed=Seated?0:(Environment->DepthAt(P.X,P.Y)>0.05?280:420);
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
void AWoodCharacter::Sit() {
 if(Environment&&GetCharacterMovement()->IsMovingOnGround()) {
  Environment->SetSeated(!Environment->IsSeated()); GetCharacterMovement()->StopMovementImmediately();
 }
}
void AWoodCharacter::Accelerate() { if(Environment) Environment->ToggleAcceleration(); }
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
  else Known=false;
  if(!Known) {
   UE_LOG(LogTemp,Error,TEXT("Unknown -WoodFrameBiome: %s"),*FrameBiome);
  } else if(Family==wood::Biome::OldGrowthForest||Family==wood::Biome::ColdRainforest||Family==wood::Biome::IcyHills||Family==wood::Biome::Savannah||Family==wood::Biome::Swamp||Family==wood::Biome::Marsh||Family==wood::Biome::WarmRainforest) {
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
void AWoodCharacter::WoodCapture(const FString& View,float Delay) {
 WoodView(View);
 FTimerHandle CaptureTimer;
 GetWorldTimerManager().SetTimer(CaptureTimer,this,&AWoodCharacter::Photograph,FMath::Max(Delay,0.1f),false);
}
void AWoodCharacter::ApplyRuntimeSettings(const FWoodSettings& S) {
 MouseSensitivity=S.MouseSensitivity;
 bInvertY=S.bInvertY;
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
