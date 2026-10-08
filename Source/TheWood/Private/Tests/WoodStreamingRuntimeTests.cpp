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
#include "Misc/Paths.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodExplorationTest,"Wood.Runtime.ContinuousExploration",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FWoodExplorationTest::RunTest(const FString& Parameters) {
 (void)Parameters;
 FTestWorldWrapper Fixture;
 if(!Fixture.CreateTestWorld(EWorldType::Game)) return false;
 UWorld* World=Fixture.GetTestWorld();
 auto* Environment=World->SpawnActor<AWoodWorld>();
 if(!Fixture.BeginPlayInTestWorld()) return false;
 const FVector Destination(93000,-12000,Environment->GroundAt(93000,-12000)+100);
 auto* Character=World->SpawnActor<AWoodCharacter>(Destination,FRotator::ZeroRotator);
 auto* Controller=World->SpawnActor<APlayerController>();
 Controller->SetPlayer(NewObject<ULocalPlayer>(GEngine));
 Controller->Possess(Character);
 for(int Frame=0;Frame<200;++Frame) Fixture.TickTestWorld(0.01f);
 FHitResult Hit;
 const bool Floor=World->LineTraceSingleByChannel(Hit,Destination+FVector(0,0,10000),Destination-FVector(0,0,10000),ECC_Visibility);
 TestTrue(TEXT("Terrain is realized beyond the old bounded forest"),Floor);
 TestTrue(TEXT("Exploration is not clamped to the old benchmark edge"),FMath::Abs(Character->GetActorLocation().X-Destination.X)<200);
 if(Floor) TestTrue(TEXT("Streamed floor agrees with terrain query"),FMath::Abs(Hit.ImpactPoint.Z-Environment->GroundAt(Destination.X,Destination.Y))<2);
 Fixture.EndPlayInTestWorld();
 Fixture.ForwardErrorMessages(this);
 return !HasAnyErrors();
}
namespace {
int32 CountPhotos() {
 TArray<FString> Files;
 IFileManager::Get().FindFiles(Files,*FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Photos"),TEXT("*")),true,false);
 return Files.Num();
}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodForgettingTest,"Wood.Runtime.Forgetting",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FWoodForgettingTest::RunTest(const FString& Parameters) {
 (void)Parameters;
 FTestWorldWrapper Fixture;
 if(!Fixture.CreateTestWorld(EWorldType::Game)) return false;
 UWorld* World=Fixture.GetTestWorld();
 auto* Environment=World->SpawnActor<AWoodWorld>();
 if(!Fixture.BeginPlayInTestWorld()) return false;
 const FVector Start=Environment->ExplorerStart();
 const FIntPoint StartChunk(FMath::FloorToInt(Start.X/12800),FMath::FloorToInt(Start.Y/12800));
 const FVector StartSpot(Start.X,Start.Y,Environment->GroundAt(Start.X,Start.Y)+100);
 const FVector FarSpot(Start.X+400000,Start.Y,Environment->GroundAt(Start.X+400000,Start.Y)+100);
 auto* Character=World->SpawnActor<AWoodCharacter>(StartSpot,FRotator::ZeroRotator);
 auto* Controller=World->SpawnActor<APlayerController>();
 Controller->SetPlayer(NewObject<ULocalPlayer>(GEngine));
 Controller->Possess(Character);
 for(int Frame=0;Frame<100;++Frame) Fixture.TickTestWorld(0.01f);
 TestEqual(TEXT("Start region begins at epoch 0"),Environment->RegionEpochAt(Start.X,Start.Y),0u);
 const uint64 FirstFingerprint=Environment->ChunkFingerprint(StartChunk);
 const int32 PhotosBefore=CountPhotos();
 // Teleport beyond retain radius plus one hex, then advance shared clock 100 s (grace is 90 s).
 Character->SetActorLocation(FarSpot);
 // Frame delta is clamped by the test world, so tick until the shared clock itself has run 100 s.
 const double ClockBefore=Environment->ObservationSeconds();
 for(int Step=0;Step<5000&&Environment->ObservationSeconds()-ClockBefore<100;++Step) Fixture.TickTestWorld(0.5f);
 TestTrue(TEXT("Shared clock advanced past grace"),Environment->ObservationSeconds()-ClockBefore>=90);
 TestEqual(TEXT("Left region is forgotten after grace"),Environment->RegionEpochAt(Start.X,Start.Y),1u);
 Character->SetActorLocation(StartSpot);
 for(int Frame=0;Frame<100;++Frame) Fixture.TickTestWorld(0.01f);
 TestNotEqual(TEXT("Returning yields a regenerated chunk"),Environment->ChunkFingerprint(StartChunk),FirstFingerprint);
 TestEqual(TEXT("Forgetting leaves photos untouched"),CountPhotos(),PhotosBefore);
 Fixture.EndPlayInTestWorld();
 Fixture.ForwardErrorMessages(this);
 return !HasAnyErrors();
}
#endif
