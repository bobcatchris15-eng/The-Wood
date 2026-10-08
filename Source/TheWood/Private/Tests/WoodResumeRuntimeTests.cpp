#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Tests/AutomationCommon.h"
#include "WoodWorld.h"
#include "WoodCharacter.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"

namespace {
FString ResumeTestPath() {
 return FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Wood"),TEXT("resume-test.json"));
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodSaveResumeTest,"Wood.Runtime.SaveResume",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FWoodSaveResumeTest::RunTest(const FString& Parameters) {
 (void)Parameters;
 const FString Path=ResumeTestPath();
 IFileManager::Get().Delete(*Path,false,true,true);
 FVector Start=FVector::ZeroVector,PreLocation=FVector::ZeroVector;
 FIntPoint StartChunk(0,0);
 uint64 PreFingerprint=0;
 double PreSeconds=0;
 {
  FTestWorldWrapper Fixture;
  if(!Fixture.CreateTestWorld(EWorldType::Game)) return false;
  UWorld* World=Fixture.GetTestWorld();
  auto* Environment=World->SpawnActor<AWoodWorld>();
  Environment->bResumeEnabled=true;
  Environment->ResumePath=Path;
  if(!Fixture.BeginPlayInTestWorld()) return false;
  Start=Environment->ExplorerStart();
  StartChunk=FIntPoint(FMath::FloorToInt(Start.X/12800),FMath::FloorToInt(Start.Y/12800));
  const FVector StartSpot(Start.X,Start.Y,Environment->GroundAt(Start.X,Start.Y)+100);
  const FVector FarSpot(Start.X+400000,Start.Y,Environment->GroundAt(Start.X+400000,Start.Y)+100);
  auto* Character=World->SpawnActor<AWoodCharacter>(StartSpot,FRotator::ZeroRotator);
  auto* Controller=World->SpawnActor<APlayerController>();
  Controller->SetPlayer(NewObject<ULocalPlayer>(GEngine));
  Controller->Possess(Character);
  for(int Frame=0;Frame<100;++Frame) Fixture.TickTestWorld(0.01f);
  // Forget the start region: leave it, then advance the shared clock 100 s (grace is 90 s).
  Character->SetActorLocation(FarSpot);
  const double ClockBefore=Environment->ObservationSeconds();
  for(int Step=0;Step<5000&&Environment->ObservationSeconds()-ClockBefore<100;++Step) Fixture.TickTestWorld(0.5f);
  TestEqual(TEXT("Start region forgotten before save"),Environment->RegionEpochAt(Start.X,Start.Y),1u);
  // Known state: a nearby position, seated.
  const FVector Known(Start.X+2000,Start.Y+1000,Environment->GroundAt(Start.X+2000,Start.Y+1000)+100);
  Character->SetActorLocation(Known);
  Environment->SetSeated(true);
  for(int Frame=0;Frame<20;++Frame) Fixture.TickTestWorld(0.01f);
  PreLocation=Character->GetActorLocation();
  PreSeconds=Environment->ObservationSeconds();
  PreFingerprint=Environment->ChunkFingerprint(StartChunk);
  TestTrue(TEXT("Explicit save writes resume file"),Environment->SaveResumeNow());
  TestTrue(TEXT("Resume file exists after save"),IFileManager::Get().FileExists(*Path));
  Fixture.EndPlayInTestWorld();
  Fixture.ForwardErrorMessages(this);
 }
 {
  FTestWorldWrapper Fixture;
  if(!Fixture.CreateTestWorld(EWorldType::Game)) return false;
  UWorld* World=Fixture.GetTestWorld();
  auto* Environment=World->SpawnActor<AWoodWorld>();
  Environment->bResumeEnabled=true;
  Environment->ResumePath=Path;
  if(!Fixture.BeginPlayInTestWorld()) return false;
  TestTrue(TEXT("Seated state restored"),Environment->IsSeated());
  TestTrue(TEXT("Shared clock seconds restored"),FMath::IsNearlyEqual(Environment->ObservationSeconds(),PreSeconds,1e-6));
  TestEqual(TEXT("Forgotten region epoch restored"),Environment->RegionEpochAt(Start.X,Start.Y),1u);
  TestEqual(TEXT("Forgotten region regenerates to pre-save fingerprint"),Environment->ChunkFingerprint(StartChunk),PreFingerprint);
  FVector Location=FVector::ZeroVector;
  FRotator Rotation=FRotator::ZeroRotator;
  TestTrue(TEXT("Player transform restored"),Environment->TakeResumedPlayer(Location,Rotation));
  TestTrue(TEXT("Player location restored"),Location.Equals(PreLocation,0.01));
  TestTrue(TEXT("Retained area pre-requested"),Environment->LoadedChunkCount()>0);
  Fixture.EndPlayInTestWorld();
  Fixture.ForwardErrorMessages(this);
 }
 // Corrupt resume file: the game must start fresh without crashing.
 FFileHelper::SaveStringToFile(TEXT("{\"version\":1,\"seed\":"),*Path);
 {
  FTestWorldWrapper Fixture;
  if(!Fixture.CreateTestWorld(EWorldType::Game)) return false;
  UWorld* World=Fixture.GetTestWorld();
  auto* Environment=World->SpawnActor<AWoodWorld>();
  Environment->bResumeEnabled=true;
  Environment->ResumePath=Path;
  if(!Fixture.BeginPlayInTestWorld()) return false;
  TestFalse(TEXT("Corrupt resume ignored: not seated"),Environment->IsSeated());
  TestEqual(TEXT("Corrupt resume ignored: epoch 0"),Environment->RegionEpochAt(Start.X,Start.Y),0u);
  FVector Location=FVector::ZeroVector;
  FRotator Rotation=FRotator::ZeroRotator;
  TestFalse(TEXT("Corrupt resume yields no player transform"),Environment->TakeResumedPlayer(Location,Rotation));
  Fixture.EndPlayInTestWorld();
  Fixture.ForwardErrorMessages(this);
 }
 IFileManager::Get().Delete(*Path,false,true,true);
 return !HasAnyErrors();
}
#endif
