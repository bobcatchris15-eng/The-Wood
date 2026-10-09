#include "WoodWorld.h"
#include "Generation/WoodStreaming.h"
#include <algorithm>
#include <map>
#include <memory>
#include "WoodRuntime.h"
#include "WoodPalette.h"
#include "ProceduralMeshComponent.h"
#include "Async/Async.h"
#include "Engine/RectLight.h"
#include "Components/RectLightComponent.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Generation/WoodEntrance.h"
#include <cmath>

namespace {
// True if any sample of the 128 m chunk footprint (metres) lies inside the entrance zone.
bool chunkTouchesZone(FIntPoint Chunk) {
 const double X0=Chunk.X*128.0,Y0=Chunk.Y*128.0;
 for(int I=0;I<=16;++I) for(int J=0;J<=16;++J) if(wood::entrance::inZone(X0+I*8.0,Y0+J*8.0)) return true;
 return false;
}
// Distance in metres from (X,Y) to the chunk footprint; zero inside.
double chunkDistance(FIntPoint Chunk,double X,double Y) {
 const double X0=Chunk.X*128.0,Y0=Chunk.Y*128.0;
 const double Dx=FMath::Max3(X0-X,0.0,X-(X0+128.0)),Dy=FMath::Max3(Y0-Y,0.0,Y-(Y0+128.0));
 return std::sqrt(Dx*Dx+Dy*Dy);
}
}

// Threshold: past the passage (north of CrossY) with the lot occluded, the entrance silently becomes wilderness.
void AWoodWorld::CheckThreshold(FVector Position) {
 if(Generator.entered()) return;
 const wood::Vec3 Player{Position.X/100,Position.Y/100,Position.Z/100};
 const wood::Vec3 Eye{Player.x,Player.y,Player.z+1.7};
 const wood::Vec3 LotCentre{wood::entrance::LotX,wood::entrance::LotY,0};
 if(!wood::entrance::crossed(Player)||!wood::entrance::lineOfSightBlocked(Eye,LotCentre)) return;
 bEnteredWild=true;
 SetEntered(true);
 // Cancel in-flight jobs for zone chunks: they were built with the entrance present.
 TArray<FIntPoint> Stale;
 for(const auto& Job:Runtime->Jobs) if(chunkTouchesZone(Job.Key)) Stale.Add(Job.Key);
 for(const auto& Key:Stale) Runtime->Jobs.Remove(Key);
 // Zone chunks behind the occluder are evicted; they regenerate as wilderness on the next Stream.
 // Chunks within 40 m of the player are kept as-is so immediate geometry is preserved.
 TArray<FIntPoint> Evict;
 for(const auto& Entry:Runtime->Chunks) if(chunkTouchesZone(Entry.Key)&&chunkDistance(Entry.Key,Player.x,Player.y)>40.0) Evict.Add(Entry.Key);
 for(const auto& Key:Evict) {
  auto& C=Runtime->Chunks[Key];
  for(int32 I=0;I<C.Instances.Num();++I) if(!C.Instances[I].IsEmpty()) Vegetation[I]->RemoveInstancesById(C.Instances[I],false);
  Terrain.Remove(C.Ground);C.Ground->DestroyComponent();
  if(C.Water) {Water.Remove(C.Water);C.Water->DestroyComponent();}
  Runtime->Chunks.Remove(Key);
 }
 RequestResumeSave();
}

FVector AWoodWorld::ExplorerStart() const {
 // New journey: the trailhead lot centre (metres in core, converted to cm).
 if(bTrailheadStart) return FVector(wood::entrance::LotX*100,wood::entrance::LotY*100,0);
 // -WoodWild / threshold crossed: wilderness start (dev/test default).
 double X=-180,Y=-180;
 FParse::Value(FCommandLine::Get(),TEXT("WoodStartX="),X);
 FParse::Value(FCommandLine::Get(),TEXT("WoodStartY="),Y);
 return FVector(X*100,Y*100,0);
}
int32 AWoodWorld::LoadedChunkCount() const {return Runtime->Chunks.Num();}
void AWoodWorld::EnsureTerrainAround(FVector Position) {
 FIntPoint Key(FMath::FloorToInt(Position.X/12800),FMath::FloorToInt(Position.Y/12800));
 if(!Runtime->Chunks.Contains(Key)) Realize(WoodPrepareChunk(Generator,Key.X,Key.Y,Runtime->Kinds,Runtime->Profiles,Runtime->Available,false),false);
}
void AWoodWorld::Realize(const FWoodPreparedChunk& Prepared,bool Detailed) {
 const auto& Chunk=Prepared.Chunk;
 const FIntPoint Key(Chunk.x,Chunk.y);
 auto& Resident=Runtime->Chunks.FindOrAdd(Key);
 if(!Resident.Ground) {
  auto* Mesh=NewObject<UProceduralMeshComponent>(this); Mesh->SetupAttachment(RootComponent);Mesh->RegisterComponent();
  TArray<FVector> Vertices,Normals;TArray<FVector2D> UVs,UV1,UV2;TArray<FColor> Colors;TArray<int32> Triangles;
  for(const auto& P:Chunk.vertices) Vertices.Add(FVector(P.x,P.y,P.z)*100);
  Normals=Prepared.Normals;UVs=Prepared.HabitatUV;
  for(const auto& C:Prepared.BiomeColors) Colors.Add(C.ToFColor(true));
  // Step 1: tint identity (1,1,1) carried in UV1/UV2; no material edit yet.
  UV1.Init(FVector2D(1.f,1.f),Vertices.Num());UV2.Init(FVector2D(1.f,0.f),Vertices.Num());
  for(auto I:Chunk.triangles) Triangles.Add(I);
  Mesh->CreateMeshSection(0,Vertices,Triangles,Normals,UVs,UV1,UV2,TArray<FVector2D>(),Colors,TArray<FProcMeshTangent>(),true);
  if(Palette) Mesh->SetMaterial(0,Palette->GroundMaterial.LoadSynchronous());
  Terrain.Add(Mesh);Resident.Ground=Mesh;
  TArray<FVector> WV,WN;TArray<FVector2D> WU;TArray<int32> WT;TArray<FLinearColor> WC;
  // Water exists only where the core reports depth; dry rows (entrance zone) emit no ribbon.
  TArray<bool> Wet;
  for(int32 I=0;I<=64;++I) {
   const double Y=Chunk.y*128+I*2,X=Generator.streamX(Y),Half=.92*Generator.streamHalfWidth(Y);
   const double L=FMath::Clamp(X-Half,Chunk.x*128.0,(Chunk.x+1)*128.0),R=FMath::Clamp(X+Half,Chunk.x*128.0,(Chunk.x+1)*128.0);
   const auto Core=Generator.sample(X,Y);
   Wet.Add(Core.depth>0);
   const double Z=Core.waterHeight+.015;
   WV.Add(FVector(L,Y,Z)*100);WV.Add(FVector(R,Y,Z)*100);
   WN.Add(FVector::UpVector);WN.Add(FVector::UpVector);WU.Add(FVector2D(0,Y/4));WU.Add(FVector2D(1,Y/4));WC.Add(FLinearColor::White);WC.Add(FLinearColor::White);
   if(I>0&&Wet[I]&&Wet[I-1]&&(R>L||WV[(I-1)*2+1].X>WV[(I-1)*2].X)) {const int32 N=(I-1)*2;WT.Append({N,N+2,N+1,N+1,N+2,N+3});}
  }
  if(!WT.IsEmpty()) {
   auto* WaterMesh=NewObject<UProceduralMeshComponent>(this);WaterMesh->SetupAttachment(RootComponent);WaterMesh->RegisterComponent();WaterMesh->SetCollisionEnabled(ECollisionEnabled::NoCollision);
   WaterMesh->CreateMeshSection_LinearColor(0,WV,WT,WN,WU,WC,TArray<FProcMeshTangent>(),false);
   if(Palette) WaterMesh->SetMaterial(0,Palette->WaterMaterial.LoadSynchronous());Water.Add(WaterMesh);Resident.Water=WaterMesh;
  }
 }
 if(Resident.Detailed||!Detailed) return;
 const auto& Placements=Prepared.Placements;Resident.Instances.SetNum(Vegetation.Num());
 for(int32 I=0;I<Vegetation.Num();++I) if(!Placements[I].IsEmpty()) {
  Resident.Instances[I]=Vegetation[I]->AddInstancesById(Placements[I],true,false);
 }
 Resident.Detailed=true;
}
// Retained chunks keep their regions observed; a region unobserved for the grace period gets a new epoch.
void AWoodWorld::UpdateForgetting() {
 namespace memory=wood::memory;
 const double ChunkSize=Generator.settings().chunkSize;
 const auto OwnerFn=[this](double X,double Y){const auto Cell=Generator.regionOwner(X,Y);return memory::RegionKey{Cell.q,Cell.r};};
 const auto TouchedBy=[&](FIntPoint Chunk){return memory::regionsTouching(std::vector<wood::streaming::Coord>{{Chunk.X,Chunk.Y}},ChunkSize,OwnerFn);};
 std::vector<wood::streaming::Coord> Retained;
 for(const auto& Entry:Runtime->Chunks) Retained.push_back({Entry.Key.X,Entry.Key.Y});
 const double Now=Clock.seconds;
 Memory.observe(memory::regionsTouching(Retained,ChunkSize,OwnerFn),Now);
 const std::vector<memory::RegionKey> Forgotten=Memory.forgetDue(Now,static_cast<double>(ForgetGraceSeconds));
 if(Forgotten.empty()) return;
 // Jobs copy the World, so the epoch source they capture must be immutable and must not reference Memory.
 auto Snapshot=std::make_shared<std::map<memory::RegionKey,std::uint32_t>>();
 for(const auto& Saved:Memory.epochs()) Snapshot->insert(Saved);
 Generator.setEpochs([Snapshot](int q,int r){const auto It=Snapshot->find(memory::RegionKey{q,r});return It==Snapshot->end()?std::uint32_t{0}:It->second;});
 const auto IsForgotten=[&Forgotten](const memory::RegionKey& Key){return std::binary_search(Forgotten.begin(),Forgotten.end(),Key);};
 // In-flight jobs built with pre-forget epochs for a forgotten region are discarded, never realized.
 TArray<FIntPoint> Stale;
 for(const auto& Job:Runtime->Jobs) for(const auto& Key:TouchedBy(Job.Key)) if(IsForgotten(Key)) {Stale.Add(Job.Key);break;}
 for(const auto& Key:Stale) Runtime->Jobs.Remove(Key);
 // Invariant: no resident chunk may touch a forgotten region, since its regions were all observed this tick.
 for(const auto& Entry:Runtime->Chunks) for(const auto& Key:TouchedBy(Entry.Key)) {
  const bool Violated=IsForgotten(Key);
  ensureMsgf(!Violated,TEXT("Resident chunk %d,%d touches forgotten region %d,%d"),Entry.Key.X,Entry.Key.Y,Key.q,Key.r);
 }
 RequestResumeSave();
}
void AWoodWorld::Stream(FVector Position) {
 EnsureTerrainAround(Position);
 const FIntPoint Center(FMath::FloorToInt(Position.X/12800),FMath::FloorToInt(Position.Y/12800));
 TArray<FIntPoint> Done;for(auto& Job:Runtime->Jobs) if(Job.Value.IsReady()) {Done.Add(Job.Key);break;}
 for(auto Key:Done) {auto Chunk=Runtime->Jobs[Key].Get();Runtime->Jobs.Remove(Key);if(FMath::Abs(Key.X-Center.X)<=ChunkRadius+1&&FMath::Abs(Key.Y-Center.Y)<=ChunkRadius+1) Realize(Chunk);}
 TArray<FIntPoint> Remove;for(auto& Entry:Runtime->Chunks) if(FMath::Abs(Entry.Key.X-Center.X)>ChunkRadius+2||FMath::Abs(Entry.Key.Y-Center.Y)>ChunkRadius+2) Remove.Add(Entry.Key);
 for(auto Key:Remove) {
  auto& C=Runtime->Chunks[Key];for(int32 I=0;I<C.Instances.Num();++I) if(!C.Instances[I].IsEmpty()) {
   Vegetation[I]->RemoveInstancesById(C.Instances[I],false);
  }
  Terrain.Remove(C.Ground);C.Ground->DestroyComponent();if(C.Water) {Water.Remove(C.Water);C.Water->DestroyComponent();}Runtime->Chunks.Remove(Key);
 }
 UpdateForgetting();
 std::vector<wood::streaming::Coord> Loaded,Pending;
 for(const auto& Entry:Runtime->Chunks) if(Entry.Value.Detailed) Loaded.push_back({Entry.Key.X,Entry.Key.Y});
 for(const auto& Entry:Runtime->Jobs) Pending.push_back({Entry.Key.X,Entry.Key.Y});
 const auto Plan=wood::streaming::plan(Position.X/100,Position.Y/100,Loaded,Pending,{128,ChunkRadius,ChunkRadius+2,2});
 for(const auto& Coordinate:Plan.needed) {
  if(Runtime->Jobs.Num()>=2) break;
  const FIntPoint Key(Coordinate.x,Coordinate.y);
  const wood::World Snapshot=Generator;const auto Kinds=Runtime->Kinds;const auto Profiles=Runtime->Profiles;const auto Available=Runtime->Available;
  Runtime->Jobs.Add(Key,Async(EAsyncExecution::ThreadPool,[Snapshot,Key,Kinds,Profiles,Available](){return WoodPrepareChunk(Snapshot,Key.X,Key.Y,Kinds,Profiles,Available);}));
 }
 // Fixed world-space light tiles preserve shadows as the player moves.
 const FIntPoint LightCenter(FMath::FloorToInt(Position.X/51200),FMath::FloorToInt(Position.Y/51200));
 if(Runtime->LightCenter!=LightCenter) {
  Runtime->LightCenter=LightCenter;
  for(int32 I=RegionLights.Num()-1;I>=0;--I) {const FVector P=RegionLights[I]->GetActorLocation();if(FMath::Abs(P.X-Position.X)>110000||FMath::Abs(P.Y-Position.Y)>110000){RegionLights[I]->Destroy();RegionLights.RemoveAt(I);}}
  for(int32 Y=-1;Y<=1;++Y) for(int32 X=-1;X<=1;++X) {
   const FVector P((LightCenter.X+X)*51200.0+25600,(LightCenter.Y+Y)*51200.0+25600,18000);
   bool Exists=false;for(const auto& L:RegionLights) if(FVector::DistSquared2D(L->GetActorLocation(),P)<1) Exists=true;
   if(Exists) continue;auto* L=GetWorld()->SpawnActor<ARectLight>(P,FRotator(-90,0,0));if(!L) continue;
   auto* C=Cast<URectLightComponent>(L->GetLightComponent());C->SetMobility(EComponentMobility::Movable);C->SetAttenuationRadius(55000);C->SetSourceWidth(3000);C->SetSourceHeight(3000);C->SetUseTemperature(true);C->SetIntensityUnits(ELightUnits::Candelas);C->SetCastShadows(false);RegionLights.Add(L);
  }
 }
}
