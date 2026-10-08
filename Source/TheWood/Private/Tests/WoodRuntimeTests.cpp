#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Tests/AutomationCommon.h"
#include "WoodWorld.h"
#include "WoodCharacter.h"
#include "Camera/CameraComponent.h"
#include "Components/CapsuleComponent.h"
#include "GameFramework/CharacterMovementComponent.h"
#include "GameFramework/PlayerController.h"
#include "Engine/World.h"
#include "Engine/LocalPlayer.h"
#include "Engine/Engine.h"
#include "Engine/ExponentialHeightFog.h"
#include "Components/ExponentialHeightFogComponent.h"
#include "EngineUtils.h"
#include "Kismet/GameplayStatics.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodRuntimeTest,"Wood.Runtime.GroundAndObservation",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FWoodRuntimeTest::RunTest(const FString& Parameters) {
 (void)Parameters;
 FTestWorldWrapper Fixture;
 if(!Fixture.CreateTestWorld(EWorldType::Game)) { Fixture.ForwardErrorMessages(this);return false; }
 auto* World=Fixture.GetTestWorld();
 auto* Environment=World->SpawnActor<AWoodWorld>();
 if(!TestNotNull(TEXT("Generated environment spawned"),Environment)) return false;
 if(!Fixture.BeginPlayInTestWorld()) { Fixture.ForwardErrorMessages(this);return false; }
 Fixture.TickTestWorld();
 const FVector Above(-17920,-17920,10000),Below(-17920,-17920,-10000);
 FHitResult Hit;
 const bool Found=World->LineTraceSingleByChannel(Hit,Above,Below,ECC_Visibility);
 TestTrue(TEXT("Generated terrain has a collidable floor"),Found);
 if(Found) TestTrue(TEXT("Collision floor agrees with generated height within one grid cell"),FMath::Abs(Hit.ImpactPoint.Z-Environment->GroundAt(Above.X,Above.Y))<100);
 Environment->ToggleAcceleration();
 TestFalse(TEXT("Standing cannot accelerate time"),Environment->IsAccelerated());
 Environment->SetSeated(true); Environment->ToggleAcceleration();
 TestTrue(TEXT("Seated acceleration affects the actual world clock"),UGameplayStatics::GetGlobalTimeDilation(World)>1);
 for(TActorIterator<AExponentialHeightFog> It(World);It;++It) {
  const float Before=It->GetComponent()->FogDensity;
  Environment->Tick(200.0f); // Ten wall-clock seconds at the seated 20x rate.
  TestTrue(TEXT("Accelerated observation changes rendered mist"),FMath::Abs(It->GetComponent()->FogDensity-Before)>0.0001f);
 }
 Environment->SetSeated(false);
 TestEqual(TEXT("Standing restores world time"),UGameplayStatics::GetGlobalTimeDilation(World),1.0f);
 auto* Character=World->SpawnActor<AWoodCharacter>(FVector(Above.X,Above.Y,Environment->GroundAt(Above.X,Above.Y)+100),FRotator::ZeroRotator);
 if(TestNotNull(TEXT("Explorer spawned"),Character)) {
  auto* Controller=World->SpawnActor<APlayerController>();
  if(!TestNotNull(TEXT("Explorer controller spawned"),Controller)) return false;
  Controller->SetPlayer(NewObject<ULocalPlayer>(GEngine));
  Controller->Possess(Character);
  for(int Frame=0;Frame<100;++Frame) Fixture.TickTestWorld(0.01f);
  TestTrue(TEXT("Explorer settles on generated collision"),Character->GetCharacterMovement()->IsMovingOnGround());
  const double StartY=-16000;
  const wood::World RouteWorld(wood::Settings{});
  const double RouteX=(RouteWorld.streamX(StartY/100)-7)*100;
  Character->SetActorLocation(FVector(RouteX,StartY,Environment->GroundAt(RouteX,StartY)+100));
  for(int Frame=0;Frame<100;++Frame) Fixture.TickTestWorld(0.01f);
  const FVector WalkStart=Character->GetActorLocation();
  for(int Frame=0;Frame<100;++Frame) {
   Character->AddMovementInput(FVector(0,1,0),1);
   Fixture.TickTestWorld(0.01f);
  }
  TestTrue(TEXT("Normal walking covers a comfortable exploration distance"),Character->GetActorLocation().Y-WalkStart.Y>350);
  AddInfo(FString::Printf(TEXT("Walking probe: distance %.2fcm, max speed %.2f, grounded %d, velocity %s, locally controlled %d"),
   Character->GetActorLocation().Y-WalkStart.Y,Character->GetCharacterMovement()->MaxWalkSpeed,
   Character->GetCharacterMovement()->IsMovingOnGround(),*Character->GetVelocity().ToString(),Character->IsLocallyControlled()));
 }
 Fixture.EndPlayInTestWorld(); Fixture.ForwardErrorMessages(this);
 return !HasAnyErrors();
}
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodSpecMovementTest,"Wood.Runtime.SpecMovement",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FWoodSpecMovementTest::RunTest(const FString& Parameters) {
 (void)Parameters;
 FTestWorldWrapper Fixture;
 if(!Fixture.CreateTestWorld(EWorldType::Game)) { Fixture.ForwardErrorMessages(this);return false; }
 auto* World=Fixture.GetTestWorld();
 auto* Environment=World->SpawnActor<AWoodWorld>();
 if(!TestNotNull(TEXT("Generated environment spawned"),Environment)) return false;
 if(!Fixture.BeginPlayInTestWorld()) { Fixture.ForwardErrorMessages(this);return false; }
 Fixture.TickTestWorld();
 const wood::World RouteWorld(wood::Settings{});
 const double StreamY=-16000;
 const double StreamX=RouteWorld.streamX(StreamY/100)*100;
 const double DryX=StreamX-700;
 auto* Character=World->SpawnActor<AWoodCharacter>(FVector(DryX,StreamY,Environment->GroundAt(DryX,StreamY)+100),FRotator::ZeroRotator);
 if(!TestNotNull(TEXT("Spec character spawned"),Character)) { Fixture.EndPlayInTestWorld(); Fixture.ForwardErrorMessages(this); return false; }
 auto* Movement=Character->GetCharacterMovement();
 const auto* Camera=Character->FindComponentByClass<UCameraComponent>();
 if(TestNotNull(TEXT("Character has eye camera"),Camera)) TestTrue(TEXT("Camera FOV is 80"),FMath::Abs(Camera->FieldOfView-80.0f)<=0.01f);
 TestTrue(TEXT("MaxStepHeight is 40"),FMath::Abs(Movement->MaxStepHeight-40.0f)<=0.01f);
 TestTrue(TEXT("Walkable floor angle is 38"),FMath::Abs(Movement->GetWalkableFloorAngle()-38.0f)<=0.01f);
 for(int Frame=0;Frame<100;++Frame) Fixture.TickTestWorld(0.01f);
 TestTrue(TEXT("Dry land walk speed is 420"),FMath::Abs(Movement->MaxWalkSpeed-420.0f)<=0.01f);
 // Wading: centreline of the stream, same DepthAt expression the character Tick evaluates.
 Character->SetActorLocation(FVector(StreamX,StreamY,Environment->GroundAt(StreamX,StreamY)+100));
 for(int Frame=0;Frame<100;++Frame) Fixture.TickTestWorld(0.01f);
 const double Depth=Environment->DepthAt(StreamX,StreamY);
 TestTrue(TEXT("Stream centreline depth exceeds 0.05 wading threshold"),Depth>0.05);
 TestTrue(TEXT("Wading walk speed is 280 over stream"),FMath::Abs(Movement->MaxWalkSpeed-280.0f)<=0.01f);
 Fixture.EndPlayInTestWorld(); Fixture.ForwardErrorMessages(this);
 return !HasAnyErrors();
}
#endif
