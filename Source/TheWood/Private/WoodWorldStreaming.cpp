#include "WoodWorld.h"
#include "Generation/WoodStreaming.h"
#include "Generation/WoodLandmarks.h"
#include "Generation/WoodFlora.h"
#include "Engine/StaticMesh.h"
#include "Materials/MaterialInstanceDynamic.h"
#include "Materials/Material.h"
#include "Materials/MaterialInstanceConstant.h"
#include "Materials/MaterialInterface.h"
#include "Components/InstancedStaticMeshComponent.h"
#include <algorithm>
#include <map>
#include <memory>
#include "WoodRuntime.h"
#include "WoodPalette.h"
#include "ProceduralMeshComponent.h"
#include "PhysicsEngine/BodySetup.h"
#include "Async/Async.h"
#include "Engine/RectLight.h"
#include "Components/RectLightComponent.h"
#include "Engine/World.h"
#include "Misc/CommandLine.h"
#include "Misc/Parse.h"
#include "Generation/WoodEntrance.h"
#include "WoodCreature.h"
#include <cmath>

namespace {
// Flora leaf/frond/petal instances carry a BLEND_Translucent base-property override over a MASKED parent. Translucent draws
// are unsorted overdraw and cost ~13 ms GPU on the iGPU (measured: GPU/Translucency); the alpha-tested cutout is what the
// parent encodes. Drops the override on the in-memory instance once per session; persist by re-saving content (not done here).
void ForceMaskedFlora(UMaterialInterface* Interface) {
#if WITH_EDITORONLY_DATA
 if(!Interface||Interface->GetBlendMode()!=BLEND_Translucent) return;
 const UMaterial* Base=Interface->GetMaterial();
 if(!Base||Base->BlendMode!=BLEND_Masked) return;
 for(UMaterialInterface* Walk=Interface;Walk;) {
  auto* Constant=Cast<UMaterialInstanceConstant>(Walk);
  if(!Constant) break;
  if(Constant->BasePropertyOverrides.bOverride_BlendMode&&Constant->BasePropertyOverrides.BlendMode==BLEND_Translucent) {
   Constant->BasePropertyOverrides.bOverride_BlendMode=false;
   Constant->PostEditChange();
  }
  Walk=Constant->Parent;
 }
#endif
}
}

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
  DestroyFlora(C);
  for(auto& Creature:C.Creatures) if(Creature.IsValid()) Creature->Destroy();
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
bool AWoodWorld::StreamingSettled(FVector Position) const {
 if(!Runtime.IsValid()||!Runtime->Jobs.IsEmpty()) return false;
 // The flora queue drains over frames (PumpFlora): no resident chunk may still hold queued groups.
 for(const auto& Entry:Runtime->Chunks) if(!Entry.Value.FloraPending.IsEmpty()) return false;
 const FIntPoint Center(FMath::FloorToInt(Position.X/12800),FMath::FloorToInt(Position.Y/12800));
 for(int32 J=-1;J<=1;++J) for(int32 I=-1;I<=1;++I) {
  const FWoodResident* Resident=Runtime->Chunks.Find(FIntPoint(Center.X+I,Center.Y+J));
  if(!Resident||!Resident->Detailed||!Resident->FloraPending.IsEmpty()) return false;
  // Async collision cook: the body setup only reports created physics meshes once the cook has been swapped in.
  const UBodySetup* Body=Resident->Ground?Resident->Ground->GetBodySetup():nullptr;
  if(!Body||!Body->bCreatedPhysicsMeshes) return false;
 }
 return true;
}
void AWoodWorld::EnsureTerrainAround(FVector Position) {
 FIntPoint Key(FMath::FloorToInt(Position.X/12800),FMath::FloorToInt(Position.Y/12800));
 if(!Runtime->Chunks.Contains(Key)) Realize(WoodPrepareChunk(Generator,Key.X,Key.Y,Runtime->Kinds,Runtime->Profiles,Runtime->Available,false),false);
}
void AWoodWorld::Realize(const FWoodPreparedChunk& Prepared,bool Detailed) {
 const double GroundStart=FPlatformTime::Seconds();
 const auto& Chunk=Prepared.Chunk;
 const FIntPoint Key(Chunk.x,Chunk.y);
 auto& Resident=Runtime->Chunks.FindOrAdd(Key);
 if(!Resident.Ground) {
  auto* Mesh=NewObject<UProceduralMeshComponent>(this); Mesh->SetupAttachment(RootComponent);
  // Collision cooks off the game thread: a synchronous 64x64 trimesh cook was a per-chunk hitch.
  Mesh->bUseAsyncCooking=true;
  Mesh->RegisterComponent();
  TArray<FVector> Vertices,Normals;TArray<FVector2D> UVs,UV1,UV2;TArray<FColor> Colors;TArray<int32> Triangles;
  for(const auto& P:Chunk.vertices) Vertices.Add(FVector(P.x,P.y,P.z)*100);
  Normals=Prepared.Normals;UVs=Prepared.HabitatUV;
  // Archetype weights are linear data, not colour: encoding them as sRGB skews the shader's blend ratios.
  for(const auto& C:Prepared.BiomeColors) Colors.Add(C.ToFColor(false));
  // Per-vertex ground tint from wood::ground::shade(): UV1 = tint R,G; UV2 = tint B, 0 (identity for original families).
  UV1.Init(FVector2D(1.f,1.f),Vertices.Num());UV2.Init(FVector2D(1.f,0.f),Vertices.Num());
  for(int32 I=0;I<Prepared.Tints.Num()&&I<Vertices.Num();++I) { UV1[I]=FVector2D(Prepared.Tints[I].R,Prepared.Tints[I].G); UV2[I]=FVector2D(Prepared.Tints[I].B,Prepared.Tints[I].A); }
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
 // Timed for hitch correlation: matches CSV GameThread spikes to chunk realisation.
 const double RealizeStart=FPlatformTime::Seconds();
 const double GroundMs=(RealizeStart-GroundStart)*1000.0;
 const auto& Placements=Prepared.Placements;Resident.Instances.SetNum(Vegetation.Num());
 for(int32 I=0;I<Vegetation.Num();++I) if(!Placements[I].IsEmpty()) {
  Resident.Instances[I]=Vegetation[I]->AddInstancesById(Placements[I],true,false);
 }
 SpawnFlora(Resident,Prepared);
 Resident.Detailed=true;
 SpawnFauna(Resident,Key);
 SpawnLandmarks(Key);
 UE_LOG(LogTemp,Log,TEXT("WoodRealize chunk %d,%d detailed in %.1f ms (ground+water %.1f), flora groups queued %d"),Key.X,Key.Y,(FPlatformTime::Seconds()-RealizeStart)*1000.0,GroundMs,Resident.FloraPending.Num());
}
void AWoodWorld::BuildFlora() {
 Runtime->FloraVariants.Reset();
 Runtime->FloraSpecies.Reset();
 FloraKeep.Reset();
 if(!Palette) return;
 const int32 Count=FMath::Min(Palette->FloraMeshIndex.Num(),Palette->FloraMeshes.Num());
 for(int32 I=0;I<Count;++I) {
  const int32 Species=Palette->FloraMeshIndex[I];
  if(Species<0||Species>=wood::flora::kFloraCount) continue;
  UStaticMesh* Mesh=Palette->FloraMeshes[I].LoadSynchronous();
  if(!Mesh) continue;
  FWoodFloraVariant Variant;
  Variant.Mesh=Mesh;
  Variant.Species=Species;
  Variant.Profile=WoodPlacementProfile(*Mesh);
  for(const auto& Slot:Mesh->GetStaticMaterials()) {
   if(FParse::Param(FCommandLine::Get(),TEXT("WoodMaskFlora"))) ForceMaskedFlora(Slot.MaterialInterface);
   UMaterialInstanceDynamic* Mid=Slot.MaterialInterface?UMaterialInstanceDynamic::Create(Slot.MaterialInterface,this):nullptr;
   if(Mid) WindMaterials.Add(Mid);
   Variant.Slots.Add(Mid);
  }
  FloraKeep.Add(Mesh);
  Runtime->FloraSpecies.FindOrAdd(Species).Add(Runtime->FloraVariants.Num());
  Runtime->FloraVariants.Add(Variant);
 }
}
void AWoodWorld::SpawnFlora(FWoodResident& Resident,const FWoodPreparedChunk& Prepared) {
 if(Runtime->FloraVariants.IsEmpty()||!GetWorld()) return;
 // Placement: core feature positions in metres; the grounded transform is in centimetres, as for the bucket path.
 TMap<int32,TArray<FTransform>> Placed;
 TMap<int32,TArray<float>> Tints;
 for(const auto& Feature:Prepared.Chunk.features) {
  if(Feature.flora<0||Feature.floraMesh<0) continue;
  const TArray<int32>* Ids=Runtime->FloraSpecies.Find(Feature.floraMesh);
  if(!Ids||Ids->IsEmpty()) continue;
  // Variant pick from yaw, as the bucket path does for its candidate tables.
  const int32 Pick=FMath::Abs(static_cast<int32>(Feature.yaw*19))%Ids->Num();
  const int32 Id=(*Ids)[Pick];
  const FWoodFloraVariant& Variant=Runtime->FloraVariants[Id];
  FTransform Where=WoodGroundedTransform(Feature,Variant.Profile,[this](double X,double Y){return Generator.terrainHeight(X,Y);});
  if(wood::flora::table()[static_cast<std::size_t>(Variant.Species)].row.role==wood::flora::Role::Moss) {
   // Ground moss mounds are 0.5 m discs at feature scale 0.5-2.5, which read as flat green decals. Patches are 0.4x the
   // feature scale with 0.8-1.2 height variation, and half the instances are thinned deterministically (catalogue ceiling unchanged).
   if(FMath::Frac(Feature.yaw*0.0137+Feature.position.x*0.31)>0.5) continue;
   const FVector S=Where.GetScale3D();
   Where.SetScale3D(FVector(S.X*0.4,S.Y*0.4,S.Z*0.4*(0.8+0.4*FMath::Frac(Feature.yaw*0.0531+Feature.position.y*0.17))));
  }
  Placed.FindOrAdd(Id).Add(Where);
  Tints.FindOrAdd(Id).Add(static_cast<float>(Feature.tint));
 }
 for(auto& Group:Placed) {
  FWoodPendingFlora& Pending=Resident.FloraPending.AddDefaulted_GetRef();
  Pending.Variant=Group.Key;
  Pending.Transforms=MoveTemp(Group.Value);
  Pending.Tints=MoveTemp(Tints.FindChecked(Group.Key));
 }
}
void AWoodWorld::PumpFlora(double BudgetSeconds) {
 if(!Runtime.IsValid()) return;
 const double Start=FPlatformTime::Seconds();
 bool Any=false;
 for(auto& Entry:Runtime->Chunks) {
  FWoodResident& Resident=Entry.Value;
  while(!Resident.FloraPending.IsEmpty()) {
   if(Any&&FPlatformTime::Seconds()-Start>=BudgetSeconds) return;
   FWoodPendingFlora Group=MoveTemp(Resident.FloraPending[0]);
   Resident.FloraPending.RemoveAt(0,1,EAllowShrinking::No);
   Any=true;
   const FWoodFloraVariant& Variant=Runtime->FloraVariants[Group.Variant];
   const auto& Row=wood::flora::table()[static_cast<std::size_t>(Variant.Species)].row;
   auto* Comp=NewObject<UInstancedStaticMeshComponent>(this);
   Comp->SetupAttachment(RootComponent);
   Comp->SetStaticMesh(Variant.Mesh);
   // One float per instance: tint index 0-3, read by the flora material.
   Comp->NumCustomDataFloats=1;
   for(int32 S=0;S<Variant.Slots.Num();++S) if(Variant.Slots[S]) Comp->SetMaterial(S,Variant.Slots[S]);
   const bool Understory=wood::flora::understoryRole(Row.role);
   int32 Cull=4000;
   switch(Row.role) {
    case wood::flora::Role::Canopy: Cull=30000; break;
    case wood::flora::Role::Subcanopy: Cull=15000; break;
    case wood::flora::Role::Shrub: Cull=8000; break;
    case wood::flora::Role::Moss:
    case wood::flora::Role::Fungus: Cull=2500; break;
    default: Cull=4000; break;
   }
   Comp->SetCullDistances(Cull*3/4,Cull);
   Comp->SetWorldPositionOffsetDisableDistance(Understory?6000:14000);
   Comp->SetCollisionEnabled(ECollisionEnabled::NoCollision);
   // Grass, flowers, moss and fungus cast no dynamic or contact shadow: sub-metre, invisible at range, and costly per instance.
   if(Understory||Row.role==wood::flora::Role::Moss||Row.role==wood::flora::Role::Fungus) {
    Comp->SetCastShadow(false);
    Comp->bCastContactShadow=false;
   }
   Comp->RegisterComponent();
   Comp->AddInstances(Group.Transforms,false,false);
   const TArray<float>& Values=Group.Tints;
   for(int32 I=0;I<Values.Num();++I) Comp->SetCustomDataValue(I,0,Values[I],false);
   Comp->MarkRenderStateDirty();
   FloraComponents.Add(Comp);
   Resident.Flora.Add(Comp);
  }
 }
}
void AWoodWorld::DestroyFlora(FWoodResident& Resident) {
 for(auto& Weak:Resident.Flora) if(auto* Comp=Weak.Get()) {
  // Clear instance data first: observers holding the component must not still see the chunk's placements.
  Comp->ClearInstances();
  FloraComponents.Remove(Comp);
  Comp->DestroyComponent();
 }
 Resident.Flora.Reset();
 Resident.FloraPending.Reset();
}
void AWoodWorld::SpawnFauna(FWoodResident& Resident,FIntPoint Chunk) {
 if(!GetWorld()) return;
 // Fauna cells are 64 m; one 128 m terrain chunk holds a 2x2 block of them. Spawns are chunk-local metres.
 const double Cell=wood::fauna::kChunkM;
 for(int32 J=0;J<2;++J) for(int32 I=0;I<2;++I) {
  const int32 GX=Chunk.X*2+I,GY=Chunk.Y*2+J;
  const auto Region=Generator.regionOwner(GX*Cell+Cell/2,GY*Cell+Cell/2);
  const auto& RegionInfo=Generator.region(Region.q,Region.r);
  for(const auto& Spawn:wood::fauna::spawnCreatures(static_cast<uint32>(Seed),GX,GY,RegionInfo.family,RegionInfo.unreal)) {
   const double X=GX*Cell+Spawn.x,Y=GY*Cell+Spawn.y;
   const FVector Where(X*100,Y*100,GroundAt(X*100,Y*100));
   if(auto* Creature=GetWorld()->SpawnActor<AWoodCreature>(Where,FRotator(0,Spawn.heading,0))) {
    Creature->Init(Spawn.kind,this,Spawn.heading);
    Resident.Creatures.Add(Creature);
   }
  }
 }
}
void AWoodWorld::SpawnLandmarks(FIntPoint Chunk) {
 if(!Palette || !GetWorld()) return;
 // Each region places at most one landmark; it is realized once, the first time a chunk centred in it goes detailed.
 const auto Region=Generator.regionOwner((Chunk.X+0.5)*128.0,(Chunk.Y+0.5)*128.0);
 const FIntPoint RegionKey(Region.q,Region.r);
 if(LandmarkRegions.Contains(RegionKey)) return;
 LandmarkRegions.Add(RegionKey);
 const auto Found=wood::landmark::placeLandmark(static_cast<uint32>(Seed),Region.q,Region.r,Generator);
 if(!Found) return;
 const auto& Lm=*Found;
 // Authored landmark kits (WoodKit.h table): 15 fire_lookout_tower, 16 rock_spire, 17 stone_ring_base, 18-20 standing_stone_01..03.
 auto KitMesh=[this](int32 KitId) -> UStaticMesh* {
  return Palette->Kit.IsValidIndex(KitId)?Palette->Kit[KitId].LoadSynchronous():nullptr;
 };
 if(Lm.kind==wood::landmark::LandmarkKind::StoneRing) {
  // Turf ring at ground pivot, three standing stones on an inner ring 120 degrees apart. Authored in metres: scale 1.
  const FVector Centre(Lm.x*100,Lm.y*100,Lm.z*100);
  if(UStaticMesh* Base=KitMesh(17)) {
   auto* Part=NewObject<UStaticMeshComponent>(this);
   Part->SetupAttachment(RootComponent);
   Part->SetStaticMesh(Base);
   Part->SetRelativeLocation(Centre);
   Part->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
   Part->RegisterComponent();
   Landmarks.Add(Part);
  }
  for(int32 I=0;I<3;++I) {
   UStaticMesh* Stone=KitMesh(18+I);
   if(!Stone) continue;
   const double Angle=FMath::DegreesToRadians(30.0+120.0*I);
   const FVector Offset(450.0*FMath::Cos(Angle),450.0*FMath::Sin(Angle),0.0);
   auto* Part=NewObject<UStaticMeshComponent>(this);
   Part->SetupAttachment(RootComponent);
   Part->SetStaticMesh(Stone);
   Part->SetRelativeLocation(Centre+Offset);
   Part->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
   Part->RegisterComponent();
   Landmarks.Add(Part);
  }
  return;
 }
 UStaticMesh* Asset=nullptr;
 switch(Lm.kind) {
 case wood::landmark::LandmarkKind::Spire: Asset=KitMesh(16); break;
 case wood::landmark::LandmarkKind::Tower: Asset=KitMesh(15); break;
 case wood::landmark::LandmarkKind::Waterfall: if(Palette->Rocks.IsValidIndex(0)) Asset=Palette->Rocks[0].LoadSynchronous(); break;
 case wood::landmark::LandmarkKind::GiantTree: {
  // Tallest species tree across all canopy arrays.
  double Tallest=0;
  for(const auto* Set:{&Palette->Trees,&Palette->ConiferTrees,&Palette->EvergreenTrees,&Palette->BroadleafTrees}) for(const auto& Soft:*Set) {
   auto* Mesh=Soft.LoadSynchronous();
   if(Mesh && Mesh->GetBoundingBox().GetSize().Z>Tallest) { Tallest=Mesh->GetBoundingBox().GetSize().Z; Asset=Mesh; }
  }
  break;
 }
 }
 if(!Asset) return;
 const double MeshHeightCm=Asset->GetBoundingBox().GetSize().Z;
 if(MeshHeightCm<=0) return;
 auto* Part=NewObject<UStaticMeshComponent>(this);
 Part->SetupAttachment(RootComponent);
 Part->SetStaticMesh(Asset);
 // Mesh pivots sit at ground contact (palette convention), so scale by height and place at the core ground height.
 Part->SetRelativeLocation(FVector(Lm.x*100,Lm.y*100,Lm.z*100));
 Part->SetRelativeScale3D(FVector(static_cast<float>(Lm.heightM*100/MeshHeightCm)));
 Part->SetCollisionEnabled(ECollisionEnabled::QueryAndPhysics);
 Part->RegisterComponent();
 Landmarks.Add(Part);
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
  DestroyFlora(C);
  for(auto& Creature:C.Creatures) if(Creature.IsValid()) Creature->Destroy();
  Terrain.Remove(C.Ground);C.Ground->DestroyComponent();if(C.Water) {Water.Remove(C.Water);C.Water->DestroyComponent();}Runtime->Chunks.Remove(Key);
 }
 PumpFlora(0.002);
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
