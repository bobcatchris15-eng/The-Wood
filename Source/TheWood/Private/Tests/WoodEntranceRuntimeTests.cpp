#include "Misc/AutomationTest.h"
#include "HAL/PlatformProcess.h"
#include "Engine/World.h"
#include "WoodWorld.h"
#include "WoodRuntime.h"
#include "Generation/WoodEntrance.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodThresholdTest,"Wood.Runtime.Threshold",EAutomationTestFlags::EditorContext|EAutomationTestFlags::ProductFilter)

// Lambdas below sit inside a member of FWoodThresholdTest, so they inherit its friend access to AWoodWorld privates.
bool FWoodThresholdTest::RunTest(const FString&) {
 UWorld* World=UWorld::CreateWorld(EWorldType::Game,false);
 if(!World) { AddError(TEXT("UWorld::CreateWorld failed")); return false; }
 World->InitializeActorsForPlay(FURL());
 AWoodWorld* W=World->SpawnActor<AWoodWorld>();
 if(!W) { AddError(TEXT("AWoodWorld spawn failed")); return false; }
 W->bResumeEnabled=false;
 W->Seed=42;
 W->DispatchBeginPlay();
 // Equivalent of -WoodEntrance: entrance open, lot overlay up.
 W->SetEntered(false);
 W->SpawnTrailheadLot();

 // Metres to centimetres.
 const auto AtMetres=[](double X,double Y){return FVector(X*100,Y*100,0);};
 // Pumps Stream at Position until Done() holds; false after the bounded wait.
 const auto PumpUntil=[&](FVector Position,const TFunctionRef<bool()>& Done){
  for(int I=0;I<800;++I) {
   W->Stream(Position);
   if(Done()) return true;
   FPlatformProcess::Sleep(0.005f);
  }
  return Done();
 };
 // True if the chunk carries any Kind::Prop feature from the current generator state.
 const auto HasProp=[&](FIntPoint Chunk){
  for(const auto& F:W->Generator.generate(Chunk.X,Chunk.Y).features) if(F.kind==wood::Kind::Prop) return true;
  return false;
 };

 const FIntPoint LotChunk(0,-5);     // contains the lot centre (0,-560) m
 const FIntPoint PlayerChunk(0,-2);  // contains (0,-190) m, north of the passage
 const FVector Lot=AtMetres(0,-560), Mid=AtMetres(0,-300), North=AtMetres(0,-190);

 if(!PumpUntil(Lot,[&]{return W->Runtime->Chunks.Contains(LotChunk);})) { AddError(TEXT("lot chunk never resident")); return false; }
 if(!PumpUntil(Mid,[&]{return W->Runtime->Chunks.Contains(PlayerChunk);})) { AddError(TEXT("player chunk never resident")); return false; }
 const uint64 LotBefore=W->ChunkFingerprint(LotChunk);
 // Resident geometry, not a fresh generation: ChunkFingerprint re-runs the generator and follows the entered state.
 const auto* PlayerGroundBefore=W->Runtime->Chunks.Find(PlayerChunk)->Ground;
 TestTrue(TEXT("lot overlay up before crossing"),W->TrailheadLot!=nullptr);
 TestTrue(TEXT("lot chunk has props before crossing"),HasProp(LotChunk));

 // Crossing: north of the passage with the lot occluded.
 W->CheckThreshold(North);
 TestTrue(TEXT("entered after crossing"),W->Generator.entered());
 TestTrue(TEXT("lot overlay gone after crossing"),W->TrailheadLot==nullptr);
 TestFalse(TEXT("behind-occluder zone chunk evicted"),W->Runtime->Chunks.Contains(LotChunk));

 // Regenerates as wilderness on the next Stream.
 if(!PumpUntil(North,[&]{return W->Runtime->Chunks.Contains(LotChunk);})) { AddError(TEXT("lot chunk never regenerated")); return false; }
 TestTrue(TEXT("regenerated lot chunk differs from entrance chunk"),W->ChunkFingerprint(LotChunk)!=LotBefore);
 TestFalse(TEXT("regenerated lot chunk has no props"),HasProp(LotChunk));
 TestTrue(TEXT("chunk under player still resident"),W->Runtime->Chunks.Contains(PlayerChunk));
 TestTrue(TEXT("chunk under player unchanged"),W->Runtime->Chunks.Contains(PlayerChunk)&&W->Runtime->Chunks.Find(PlayerChunk)->Ground==PlayerGroundBefore);

 // Walk back south to the old lot: no reversion, no entrance features.
 W->CheckThreshold(Mid);
 W->CheckThreshold(Lot);
 TestTrue(TEXT("still entered after walking back"),W->Generator.entered());
 if(!PumpUntil(Lot,[&]{return W->Runtime->Chunks.Contains(LotChunk);})) { AddError(TEXT("lot chunk not resident on return")); return false; }
 TestFalse(TEXT("no props at old lot on return"),HasProp(LotChunk));
 TestTrue(TEXT("no lot overlay at old lot on return"),W->TrailheadLot==nullptr);

 W->EndPlay(EEndPlayReason::Destroyed);
 World->DestroyWorld(false);
 return true;
}
