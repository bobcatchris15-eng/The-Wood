#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "Tests/AutomationCommon.h"
#include "WoodWorld.h"
#include "Components/InstancedStaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/Engine.h"
#include "Engine/LocalPlayer.h"
#include "Engine/World.h"
#include "GameFramework/Pawn.h"
#include "GameFramework/PlayerController.h"
#include "HAL/PlatformProcess.h"
#include "HAL/PlatformTime.h"

namespace {
using FChunkSnapshot = TArray<TMap<FIntVector,FTransform>>;
FChunkSnapshot Snapshot(const TArray<UInstancedStaticMeshComponent*>& Components,FIntPoint Chunk) {
 FChunkSnapshot Result;Result.SetNum(Components.Num());
 for(int32 Component=0;Component<Components.Num();++Component) {
  for(int32 Index=0;Index<Components[Component]->GetInstanceCount();++Index) {
   FTransform Transform;
   if(!Components[Component]->GetInstanceTransform(Index,Transform,true)) continue;
   const FVector P=Transform.GetLocation();
   if(FMath::FloorToInt(P.X/12800)!=Chunk.X||FMath::FloorToInt(P.Y/12800)!=Chunk.Y) continue;
   // Position identifies a generated feature independently of mutable array indices.
   const FIntVector Key(FMath::RoundToInt(P.X*10),FMath::RoundToInt(P.Y*10),FMath::RoundToInt(P.Z*10));
   Result[Component].Add(Key,Transform);
  }
 }
 return Result;
}
int32 Count(const FChunkSnapshot& Value) {int32 Total=0;for(const auto& Component:Value) Total+=Component.Num();return Total;}
}

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodInstanceRetentionTest,"Wood.Runtime.RetainedVegetation",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FWoodInstanceRetentionTest::RunTest(const FString& Parameters) {
 (void)Parameters;
 FTestWorldWrapper Fixture;
 if(!Fixture.CreateTestWorld(EWorldType::Game)) return false;
 auto* World=Fixture.GetTestWorld();
 auto* Environment=World->SpawnActor<AWoodWorld>();
 if(!TestNotNull(TEXT("Streaming environment spawned"),Environment)) return false;
 Environment->ChunkRadius=1;
 auto* Viewer=World->SpawnActor<APawn>(Environment->ExplorerStart(),FRotator::ZeroRotator);
 auto* Controller=World->SpawnActor<APlayerController>();
 if(!Viewer||!Controller) return false;
 auto* ViewerRoot=NewObject<USceneComponent>(Viewer);
 Viewer->SetRootComponent(ViewerRoot);ViewerRoot->RegisterComponent();Viewer->SetActorLocation(Environment->ExplorerStart());
 Controller->SetPlayer(NewObject<ULocalPlayer>(GEngine));Controller->Possess(Viewer);
 if(!Fixture.BeginPlayInTestWorld()) return false;
 TArray<UInstancedStaticMeshComponent*> Components;
 Environment->GetComponents<UInstancedStaticMeshComponent>(Components);
 if(!TestTrue(TEXT("Generated vegetation components exist"),!Components.IsEmpty())) return false;
 const FVector Start=Environment->ExplorerStart();
 const FIntPoint Center(FMath::FloorToInt(Start.X/12800),FMath::FloorToInt(Start.Y/12800));
 const FIntPoint Retained=Center+FIntPoint(1,0),FirstRemoved=Center+FIntPoint(-1,0);
 const auto Original=Snapshot(Components,Retained);
 TestTrue(TEXT("Retained chunk contains original generated features"),Count(Original)>0);
 TestTrue(TEXT("First outgoing chunk initially contains features"),Count(Snapshot(Components,FirstRemoved))>0);

 auto CheckRetained=[&]() {
  const auto Current=Snapshot(Components,Retained);
  bool Equal=Count(Current)==Count(Original);
  for(int32 Component=0;Component<Original.Num();++Component) {
   Equal&=Current[Component].Num()==Original[Component].Num();
   for(const auto& Entry:Original[Component]) {
    const FTransform* Found=Current[Component].Find(Entry.Key);
    Equal&=Found&&Found->Equals(Entry.Value,0.0001);
   }
  }
  return Equal;
 };
 // Two successive removals matter: a hierarchy rebuild after the first swap
 // used to rebase stored instance IDs and corrupt retained plants on the second.
 for(int32 Step=3;Step<=4;++Step) {
  const FIntPoint Next=Center+FIntPoint(Step,0);
  Viewer->SetActorLocation(FVector((Next.X+.5)*12800,(Next.Y+.5)*12800,20000));
  const double Deadline=FPlatformTime::Seconds()+15;
  bool Ready=false;
  while(FPlatformTime::Seconds()<Deadline) {
   Fixture.TickTestWorld(.01f);
   if(Count(Snapshot(Components,Next))>0) {Ready=true;break;}
   // Yield to actual worker jobs; ticking simulated time alone cannot await them.
   FPlatformProcess::Sleep(.005f);
  }
  TestTrue(TEXT("New distant chunk finishes actual background placement"),Ready);
  TestEqual(TEXT("Outgoing original chunk has no remaining vegetation"),Count(Snapshot(Components,FirstRemoved)),0);
  TestTrue(TEXT("Retained original features preserve identity and transforms after unload"),CheckRetained());
  if(!Ready) break;
 }
 Fixture.EndPlayInTestWorld();Fixture.ForwardErrorMessages(this);
 return !HasAnyErrors();
}
#endif
