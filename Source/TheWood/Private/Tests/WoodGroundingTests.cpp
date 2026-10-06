#if WITH_DEV_AUTOMATION_TESTS
#include "Misc/AutomationTest.h"
#include "WoodGrounding.h"
#include "WoodPalette.h"
#include "Engine/StaticMesh.h"
#include "StaticMeshResources.h"

IMPLEMENT_SIMPLE_AUTOMATION_TEST(FWoodRootGroundingTest,"Wood.Runtime.TreeRootContact",EAutomationTestFlags::EditorContext|EAutomationTestFlags::EngineFilter)
bool FWoodRootGroundingTest::RunTest(const FString& Parameters) {
 (void)Parameters;
 auto* Palette=LoadObject<UWoodPalette>(nullptr,TEXT("/Game/Wood/DA_BenchmarkPalette.DA_BenchmarkPalette"));
 if(!TestNotNull(TEXT("Authored tree palette exists"),Palette)) return false;
 wood::World World(wood::Settings{});
 TMap<FIntPoint,wood::Chunk> Chunks;
 // This independently interpolates generated mesh triangles; it does not call
 // the terrain query used by the placement helper.
 auto Ground=[&](double X,double Y) {
  const auto& Settings=World.settings();
  const int CX=FMath::FloorToInt(X/Settings.chunkSize),CY=FMath::FloorToInt(Y/Settings.chunkSize);
  const FIntPoint Key(CX,CY);
  if(!Chunks.Contains(Key)) Chunks.Add(Key,World.generate(CX,CY));
  const auto& Chunk=Chunks.FindChecked(Key);
  const double Step=Settings.chunkSize/Chunk.cells;
  const double LX=(X-CX*Settings.chunkSize)/Step,LY=(Y-CY*Settings.chunkSize)/Step;
  const int Col=FMath::Clamp(FMath::FloorToInt(LX),0,Chunk.cells-1),Row=FMath::Clamp(FMath::FloorToInt(LY),0,Chunk.cells-1);
  const double U=LX-Col,V=LY-Row;
  auto Z=[&](int C,int R) {return Chunk.vertices[R*(Chunk.cells+1)+C].z*100;};
  return U+V<=1?Z(Col,Row)+(Z(Col+1,Row)-Z(Col,Row))*U+(Z(Col,Row+1)-Z(Col,Row))*V:
   Z(Col+1,Row+1)+(Z(Col,Row+1)-Z(Col+1,Row+1))*(1-U)+(Z(Col+1,Row)-Z(Col+1,Row+1))*(1-V);
 };
 double OldWorst=0,NewWorst=-DBL_MAX;
 int32 Models=0;
 for(const auto& Reference:Palette->Trees) {
  UStaticMesh* Asset=Reference.LoadSynchronous();
  if(!Asset) continue;
  ++Models;
  const auto* Data=Asset->GetRenderData();
  if(!TestTrue(TEXT("Tree has readable imported geometry"),Data && !Data->LODResources.IsEmpty())) continue;
  const auto& Positions=Data->LODResources[0].VertexBuffers.PositionVertexBuffer;
  if(!TestTrue(TEXT("Cooked tree retains CPU positions"),Asset->bAllowCPUAccess)) continue;
  if(!TestTrue(TEXT("Root skirt contains multiple contacts"),WoodRootContacts(*Asset).Num()>1)) continue;
  double Bottom=DBL_MAX;
  for(uint32 I=0;I<Positions.GetNumVertices();++I) Bottom=FMath::Min(Bottom,static_cast<double>(Positions.VertexPosition(I).Z));
  AddInfo(FString::Printf(TEXT("Imported %s: root minZ %.2fcm, %d skirt contacts"),*Asset->GetName(),Bottom,WoodRootContacts(*Asset).Num()));
  const FWoodPlacementProfile Profile=WoodPlacementProfile(*Asset);
  // Flat and sloped sites, both signs, near cell/chunk boundaries, variable yaw
  // and mature-tree scales. Probe actual bottom vertices independently.
  for(int32 Site=0;Site<8;++Site) {
   const double X=-250.03+Site*61.37,Y=-128.01+Site*29.81;
   wood::Feature Feature{wood::Kind::Tree,{X,Y,0},Site*43.0,.85+Site*.09};
   const FTransform Fitted=WoodGroundedTransform(World,Feature,Profile);
   if(Site==0) {
    TestTrue(TEXT("Worker profile matches mesh placement"),Fitted.Equals(WoodGroundedTransform(World,Feature,*Asset),.001));
    const FTransform Realized=WoodGroundedTransform(Feature,Profile,[&Ground](double PX,double PY) {return Ground(PX,PY)/100;});
    TestTrue(TEXT("Realized triangle sampler matches generated terrain query"),Fitted.Equals(Realized,.001));
   }
   const double Lean=FMath::Sin(FMath::DegreesToRadians(Feature.yaw*3))*2.5;
   const FTransform Original(FRotator(Lean,Feature.yaw,0),FVector(X*100,Y*100,Ground(X,Y)),FVector(Feature.scale));
   // Build independent terrain samples only once per selected root to keep
   // this integration test practical for large scanned trees.
   int32 Count=0;
   for(uint32 I=0;I<Positions.GetNumVertices();++I) {
    const FVector Vertex(Positions.VertexPosition(I));
    if(Vertex.Z>Bottom+2 || (++Count%31)!=1) continue;
    const FVector Before=Original.TransformPosition(Vertex),After=Fitted.TransformPosition(Vertex);
    OldWorst=FMath::Max(OldWorst,Before.Z-Ground(Before.X/100,Before.Y/100));
    NewWorst=FMath::Max(NewWorst,After.Z-Ground(After.X/100,After.Y/100));
   }
  }
 }
 TestTrue(TEXT("Multiple imported tree origins were tested"),Models>=3);
 TestTrue(TEXT("Original center-only placement reproduces exposed roots"),OldWorst>5);
 TestTrue(TEXT("Real bottom-root vertices meet triangulated terrain within 2cm"),NewWorst<=2);
 AddInfo(FString::Printf(TEXT("Root contact: original worst gap %.2fcm, fitted %.2fcm across %d models"),OldWorst,NewWorst,Models));
 return true;
}
#endif
