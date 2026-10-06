#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Tests/AutomationCommon.h"
#include "WoodWorld.h"
#include "WoodCharacter.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"

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
#endif
