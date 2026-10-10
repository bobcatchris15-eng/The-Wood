#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "HAL/PlatformProcess.h"
#include "HAL/FileManager.h"
#include "Misc/FileHelper.h"
#include "Misc/Paths.h"
#include "Engine/World.h"
#include "Components/StaticMeshComponent.h"
#include "WoodWorld.h"
#include "WoodRuntime.h"

// Journey-level runtime tests. Each test owns its UWorld and resume path; none touches the player's real save.
// Private access comes from the friend declarations in WoodWorld.h (same convention as FWoodThresholdTest).

namespace {
FString JourneyScratchPath(const TCHAR* Name) {
 return FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Wood"),Name);
}
int32 JourneyPhotoCount() {
 TArray<FString> Files;
 IFileManager::Get().FindFiles(Files,*FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Photos"),TEXT("*")),true,false);
 return Files.Num();
}
FIntPoint JourneyChunkOf(const FVector& PositionCm) {
 return FIntPoint(FMath::FloorToInt(PositionCm.X/12800.0),FMath::FloorToInt(PositionCm.Y/12800.0));
}
}

// Fresh start at the trailhead lot, threshold crossing, entrance unreachable afterwards, state survives save/resume.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodJourneyFlowTest,"Wood.Runtime.JourneyFlow",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ProductFilter)
bool FWoodJourneyFlowTest::RunTest(const FString&) {
 const FString Path=JourneyScratchPath(TEXT("journey-flow-test.json"));
 IFileManager::Get().Delete(*Path,false,true,true);
 UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
 if(!World) { AddError(TEXT("UWorld::CreateWorld failed")); return false; }
 World->InitializeActorsForPlay(FURL());
 AWoodWorld* W=World->SpawnActor<AWoodWorld>();
 if(!W) { AddError(TEXT("AWoodWorld spawn failed")); return false; }
 W->bResumeEnabled=true; // no file at Path yet, so this is a fresh start
 W->ResumePath=Path;
 W->Seed=42;
 W->DispatchBeginPlay();
 // Test-Unreal passes -WoodWild, which makes startup skip the lot. Establish the trailhead start explicitly, as FWoodThresholdTest does.
 W->SetEntered(false);
 W->bTrailheadStart=true;
 W->SpawnTrailheadLot();

 const auto AtMetres=[](double X,double Y){return FVector(X*100,Y*100,0);};
 const auto PumpUntil=[&](FVector Position,const TFunctionRef<bool()>& Done){
  for(int I=0;I<800;++I) {
   W->Stream(Position);
   if(Done()) return true;
   FPlatformProcess::Sleep(0.005f);
  }
  return Done();
 };

 const FIntPoint LotChunk(0,-5);     // contains lot centre (0,-560) m
 const FIntPoint PlayerChunk(0,-2);  // contains (0,-190) m, north of the passage
 const FVector Lot=AtMetres(0,-560), Mid=AtMetres(0,-300), North=AtMetres(0,-190);

 // Fresh start: trailhead, entrance open, lot overlay up.
 TestTrue(TEXT("fresh start is a trailhead start"),W->StartsAtTrailhead());
 TestFalse(TEXT("entrance open at fresh start"),W->Generator.entered());
 if(!PumpUntil(Lot,[&]{return W->Runtime->Chunks.Contains(LotChunk);})) { AddError(TEXT("lot chunk never resident")); return false; }
 TestTrue(TEXT("trailhead lot overlay up at fresh start"),W->TrailheadLot!=nullptr);

 // Walk north through the passage with the lot occluded.
 if(!PumpUntil(Mid,[&]{return W->Runtime->Chunks.Contains(PlayerChunk);})) { AddError(TEXT("player chunk never resident")); return false; }
 W->CheckThreshold(North);
 TestTrue(TEXT("entered after crossing threshold"),W->Generator.entered());
 TestTrue(TEXT("lot overlay gone after crossing"),W->TrailheadLot==nullptr);

 // Walk back to the old lot: entrance must not reappear.
 W->CheckThreshold(Mid);
 W->CheckThreshold(Lot);
 TestTrue(TEXT("still entered after walking back to lot"),W->Generator.entered());
 if(!PumpUntil(Lot,[&]{return W->Runtime->Chunks.Contains(LotChunk);})) { AddError(TEXT("lot chunk not resident on return")); return false; }
 TestTrue(TEXT("no lot overlay on return"),W->TrailheadLot==nullptr);

 // Persist and check the journey state reached disk.
 TestTrue(TEXT("save after threshold succeeds"),W->SaveResumeNow());
 FString Json;
 TestTrue(TEXT("resume file readable"),FFileHelper::LoadFileToString(Json,*Path));
 TestTrue(TEXT("world.entered saved as enteredWild true"),Json.Contains(TEXT("\"enteredWild\":true")));
 W->EndPlay(EEndPlayReason::Destroyed);
 World->DestroyWorld(false);

 // Restart from the save: no trailhead lot, entrance stays gone.
 UWorld* World2=UWorld::CreateWorld(EWorldType::Game,false);
 if(!World2) { AddError(TEXT("second UWorld::CreateWorld failed")); return false; }
 World2->InitializeActorsForPlay(FURL());
 AWoodWorld* R=World2->SpawnActor<AWoodWorld>();
 if(!R) { AddError(TEXT("second AWoodWorld spawn failed")); return false; }
 R->bResumeEnabled=true;
 R->ResumePath=Path;
 R->Seed=42;
 R->DispatchBeginPlay();
 TestTrue(TEXT("resumed journey keeps entrance gone"),R->Generator.entered());
 TestFalse(TEXT("resumed journey is not a trailhead start"),R->StartsAtTrailhead());
 TestTrue(TEXT("resumed journey has no trailhead lot"),R->TrailheadLot==nullptr);
 R->EndPlay(EEndPlayReason::Destroyed);
 World2->DestroyWorld(false);

 IFileManager::Get().Delete(*Path,false,true,true);
 return !HasAnyErrors();
}

// Teleport beyond retention, let the shared clock pass grace: start region is forgotten, nearby ring and photos untouched.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodForgetFreshTest,"Wood.Runtime.ForgetFresh",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ProductFilter)
bool FWoodForgetFreshTest::RunTest(const FString&) {
 const FString Path=JourneyScratchPath(TEXT("forget-fresh-test.json"));
 IFileManager::Get().Delete(*Path,false,true,true);
 UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
 if(!World) { AddError(TEXT("UWorld::CreateWorld failed")); return false; }
 World->InitializeActorsForPlay(FURL());
 AWoodWorld* W=World->SpawnActor<AWoodWorld>();
 if(!W) { AddError(TEXT("AWoodWorld spawn failed")); return false; }
 W->bResumeEnabled=false;
 W->ResumePath=Path;
 W->DispatchBeginPlay();

 const auto PumpUntil=[&](FVector Position,const TFunctionRef<bool()>& Done){
  for(int I=0;I<800;++I) {
   W->Stream(Position);
   if(Done()) return true;
   FPlatformProcess::Sleep(0.005f);
  }
  return Done();
 };

 const FVector Start=W->ExplorerStart();
 const FIntPoint StartChunk=JourneyChunkOf(Start);
 const FVector Far(Start.X+400000,Start.Y,0); // 4 km east, well beyond retain radius
 const FIntPoint FarChunk=JourneyChunkOf(Far);
 if(!PumpUntil(Start,[&]{return W->Runtime->Chunks.Contains(StartChunk);})) { AddError(TEXT("start chunk never resident")); return false; }
 TestEqual(TEXT("start region begins at epoch 0"),W->RegionEpochAt(Start.X,Start.Y),0u);
 const uint64 FirstFingerprint=W->ChunkFingerprint(StartChunk);
 const int32 PhotosBefore=JourneyPhotoCount();

 // Move far away and let the retained ring form around the new position.
 if(!PumpUntil(Far,[&]{return W->Runtime->Chunks.Contains(FarChunk);})) { AddError(TEXT("far chunk never resident")); return false; }
 const uint64 NearbyBefore=W->ChunkFingerprint(FarChunk);

 // Advance the shared clock past grace (90 s) while standing at Far.
 const double ClockBefore=W->ObservationSeconds();
 // Advance the clock directly, not via Tick: Tick streams around the (absent) viewer at the origin and would disturb the observed regions.
 for(int Step=0;Step<5000&&W->ObservationSeconds()-ClockBefore<100;++Step) {
  W->Clock.advance(0.5/W->Clock.rate());
  W->Stream(Far);
 }
 TestTrue(TEXT("shared clock advanced past grace"),W->ObservationSeconds()-ClockBefore>=90);
 TestEqual(TEXT("left region forgotten after grace"),W->RegionEpochAt(Start.X,Start.Y),1u);
 TestEqual(TEXT("current region keeps its epoch"),W->RegionEpochAt(Far.X,Far.Y),0u);
 TestEqual(TEXT("nearby retained ring unchanged"),W->ChunkFingerprint(FarChunk),NearbyBefore);

 // Walk back: distant region regenerates with a new identity.
 if(!PumpUntil(Start,[&]{return W->Runtime->Chunks.Contains(StartChunk);})) { AddError(TEXT("start chunk not resident on return")); return false; }
 TestNotEqual(TEXT("returning yields a new identity for the forgotten region"),W->ChunkFingerprint(StartChunk),FirstFingerprint);
 TestEqual(TEXT("forgetting leaves photos untouched"),JourneyPhotoCount(),PhotosBefore);

 W->EndPlay(EEndPlayReason::Destroyed);
 World->DestroyWorld(false);
 return !HasAnyErrors();
}

// A landmark seen while exploring keeps its position and kind while the player walks to it across chunk loads.
IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodLandmarkPersistenceTest,"Wood.Runtime.LandmarkPersistence",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ProductFilter)
bool FWoodLandmarkPersistenceTest::RunTest(const FString&) {
 UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
 if(!World) { AddError(TEXT("UWorld::CreateWorld failed")); return false; }
 World->InitializeActorsForPlay(FURL());
 AWoodWorld* W=World->SpawnActor<AWoodWorld>();
 if(!W) { AddError(TEXT("AWoodWorld spawn failed")); return false; }
 W->bResumeEnabled=false;
 W->DispatchBeginPlay();

 const auto PumpUntil=[&](FVector Position,const TFunctionRef<bool()>& Done){
  for(int I=0;I<800;++I) {
   W->Stream(Position);
   if(Done()) return true;
   FPlatformProcess::Sleep(0.005f);
  }
  return Done();
 };

 // Scan north from the start in 128 m steps (up to 3 km) until a landmark is realized.
 const FVector Start=W->ExplorerStart();
 UStaticMeshComponent* Tracked=nullptr;
 FVector Found=Start;
 for(int K=0;K<=24&&!Tracked;++K) {
  const FVector P(Start.X,Start.Y+K*12800.0,0);
  if(!PumpUntil(P,[&]{return W->Runtime->Chunks.Contains(JourneyChunkOf(P));})) { AddError(TEXT("scan chunk never resident")); return false; }
  if(W->Landmarks.Num()>0) { Tracked=W->Landmarks[0].Get(); Found=P; }
 }
 if(!Tracked) { AddError(TEXT("no landmark realized within 3 km of start")); return false; }
 const FVector Target=Tracked->GetComponentLocation();
 UStaticMesh* TrackedMesh=Tracked->GetStaticMesh();
 AddInfo(FString::Printf(TEXT("Landmark at (%.0f,%.0f) cm, %.0f m from start"),Target.X,Target.Y,FVector::Dist2D(Target,Start)/100.0));

 // Walk to the landmark in 128 m steps. Every step, the same component must still be realized at the same place with the same mesh.
 const double Dist=FVector::Dist2D(Found,Target);
 const int Steps=FMath::Max(1,FMath::CeilToInt(Dist/12800.0));
 bool Stable=true;
 for(int S=1;S<=Steps;++S) {
  const double A=double(S)/Steps;
  const FVector P=FMath::Lerp(Found,Target,A);
  if(!PumpUntil(P,[&]{return W->Runtime->Chunks.Contains(JourneyChunkOf(P));})) { AddError(TEXT("walk chunk never resident")); return false; }
  if(!W->Landmarks.Contains(Tracked)) { Stable=false; AddError(FString::Printf(TEXT("landmark dropped at step %d of %d"),S,Steps)); break; }
  if(!Tracked->GetComponentLocation().Equals(Target,1.0)) { Stable=false; AddError(FString::Printf(TEXT("landmark moved at step %d of %d"),S,Steps)); break; }
  if(Tracked->GetStaticMesh()!=TrackedMesh) { Stable=false; AddError(FString::Printf(TEXT("landmark kind changed at step %d of %d"),S,Steps)); break; }
 }
 TestTrue(TEXT("landmark stable across the whole walk"),Stable);

 W->EndPlay(EEndPlayReason::Destroyed);
 World->DestroyWorld(false);
 return !HasAnyErrors();
}
#endif
