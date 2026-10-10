#include "WoodCreature.h"
#include "WoodWorld.h"
#include "Components/StaticMeshComponent.h"
#include "Components/SceneComponent.h"
#include "Engine/StaticMesh.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
#include "GameFramework/Pawn.h"
#include "Materials/MaterialInstanceDynamic.h"

namespace {
// Retreat speed, cm/s.
constexpr double RetreatSpeedCmS=300.0;
// Placeholder box scale per kind, multiples of the 100 cm engine cube.
FVector ScaleFor(wood::fauna::CreatureKind Kind) {
 using wood::fauna::CreatureKind;
 switch(Kind) {
 case CreatureKind::Deer: return FVector(1.8,0.7,1.5);
 case CreatureKind::Elk: return FVector(2.2,0.8,2.0);
 case CreatureKind::Bear: return FVector(2.4,1.2,2.0);
 case CreatureKind::Fox: return FVector(0.8,0.3,0.5);
 case CreatureKind::Hare: return FVector(0.4,0.2,0.3);
 case CreatureKind::Crow: return FVector(0.2,0.15,0.15);
 case CreatureKind::Owl: return FVector(0.25,0.25,0.3);
 case CreatureKind::Heron: return FVector(0.8,0.3,1.2);
 case CreatureKind::MothStag: return FVector(1.0,0.6,1.3);
 case CreatureKind::GlassHare: return FVector(0.45,0.22,0.32);
 case CreatureKind::LanternOwl: return FVector(0.3,0.28,0.4);
 case CreatureKind::StoneTortoise: return FVector(1.0,0.8,0.4);
 case CreatureKind::ShadowFox: return FVector(0.9,0.35,0.6);
 }
 return FVector(1.0);
}
// Authored species mesh per kind (Blender, /Game/Art/Authored/Creatures). The FBX import names the texture <name> and the static mesh <name>1. Strange kinds reuse the nearest species mesh.
// Host kind supplies the mesh; ScaleFor(kind)/ScaleFor(host) gives the strange-kind scale relative to it.
wood::fauna::CreatureKind HostFor(wood::fauna::CreatureKind Kind) {
 using wood::fauna::CreatureKind;
 switch(Kind) {
 case CreatureKind::MothStag: return CreatureKind::Deer;
 case CreatureKind::GlassHare: return CreatureKind::Hare;
 case CreatureKind::LanternOwl: return CreatureKind::Owl;
 case CreatureKind::StoneTortoise: return CreatureKind::Bear;
 case CreatureKind::ShadowFox: return CreatureKind::Fox;
 default: return Kind;
 }
}
const TCHAR* MeshPathFor(wood::fauna::CreatureKind Kind) {
 using wood::fauna::CreatureKind;
 switch(HostFor(Kind)) {
 case CreatureKind::Deer: return TEXT("/Game/Art/Authored/Creatures/deer1.deer1");
 case CreatureKind::Elk: return TEXT("/Game/Art/Authored/Creatures/elk1.elk1");
 case CreatureKind::Bear: return TEXT("/Game/Art/Authored/Creatures/bear1.bear1");
 case CreatureKind::Fox: return TEXT("/Game/Art/Authored/Creatures/fox1.fox1");
 case CreatureKind::Hare: return TEXT("/Game/Art/Authored/Creatures/hare1.hare1");
 case CreatureKind::Crow: return TEXT("/Game/Art/Authored/Creatures/crow1.crow1");
 case CreatureKind::Owl: return TEXT("/Game/Art/Authored/Creatures/owl1.owl1");
 case CreatureKind::Heron: return TEXT("/Game/Art/Authored/Creatures/heron1.heron1");
 default: return nullptr;
 }
}
// Placeholder colour tint for strange kinds only. Mainstream kinds keep the default material.
FLinearColor TintFor(wood::fauna::CreatureKind Kind) {
 using wood::fauna::CreatureKind;
 switch(Kind) {
 case CreatureKind::MothStag: return FLinearColor(0.9,0.6,0.2);
 case CreatureKind::GlassHare: return FLinearColor(0.6,0.9,1.0);
 case CreatureKind::LanternOwl: return FLinearColor(1.0,0.9,0.3);
 case CreatureKind::StoneTortoise: return FLinearColor(0.45,0.5,0.42);
 case CreatureKind::ShadowFox: return FLinearColor(0.12,0.05,0.18);
 default: return FLinearColor::White;
 }
}
}

bool AWoodCreature::bFreezeAll=false;

AWoodCreature::AWoodCreature() {
 PrimaryActorTick.bCanEverTick=true;
 Body=CreateDefaultSubobject<UStaticMeshComponent>(TEXT("Body"));
 // Body hangs off a plain root: Init sets Body relative location/scale, which on the root itself moved the actor to the world origin.
 auto* Root=CreateDefaultSubobject<USceneComponent>(TEXT("Root"));
 RootComponent=Root;
 Root->SetMobility(EComponentMobility::Movable);
 Body->SetupAttachment(Root);
 // Movable: SetStaticMesh in Init and SetActorLocation in Tick are ignored on a registered Static component (creatures never rendered).
 Body->SetMobility(EComponentMobility::Movable);
 Body->SetCollisionEnabled(ECollisionEnabled::NoCollision);
}

void AWoodCreature::Init(wood::fauna::CreatureKind Kind, AWoodWorld* Terrain, double Heading) {
 KindValue=Kind;
 Mind=wood::fauna::mindFor(Kind);
 HeadingDeg=Heading;
 Ground=Terrain;
 const FVector Scale=ScaleFor(Kind);
 UStaticMesh* Species=MeshPathFor(Kind)?LoadObject<UStaticMesh>(nullptr,MeshPathFor(Kind)):nullptr;
 if(Species) {
  // Authored meshes pivot at ground contact; strange kinds scale the host mesh relative to their own box.
  const FVector Host=ScaleFor(HostFor(Kind));
  Body->SetStaticMesh(Species);
  Body->SetRelativeScale3D(FVector(Scale.X/Host.X,Scale.Y/Host.Y,Scale.Z/Host.Z));
  Body->SetRelativeLocation(FVector::ZeroVector);
 } else {
  // Fallback cube (no authored mesh): pivot is its centre; lift by half its height so the base sits on the ground.
  Body->SetStaticMesh(LoadObject<UStaticMesh>(nullptr,TEXT("/Engine/BasicShapes/Cube.Cube")));
  Body->SetRelativeScale3D(Scale);
  Body->SetRelativeLocation(FVector(0,0,Scale.Z*50.0));
 }
 if(wood::fauna::isStrange(Kind)) {
  if(UMaterialInstanceDynamic* Dyn=Body->CreateAndSetMaterialInstanceDynamic(0)) Dyn->SetVectorParameterValue(TEXT("Color"),TintFor(Kind));
 }
}

void AWoodCreature::Tick(float DeltaSeconds) {
 Super::Tick(DeltaSeconds);
 if(bFreezeAll) return;
 const APlayerController* PC=GetWorld()?GetWorld()->GetFirstPlayerController():nullptr;
 const APawn* Pawn=PC?PC->GetPawn():nullptr;
 if(!Pawn) return;
 const FVector Here=GetActorLocation();
 const FVector PlayerPos=Pawn->GetActorLocation();
 const FVector ToPlayer(PlayerPos.X-Here.X,PlayerPos.Y-Here.Y,0.0);
 const double DistM=ToPlayer.Size()/100.0;
 StateValue=wood::fauna::stepCreature(StateValue,DistM,DeltaSeconds,Mind);
 if(StateValue==wood::fauna::CreatureState::Retreat) {
  // Away from the player only: the step never reduces horizontal distance.
  FVector Away(-ToPlayer.X,-ToPlayer.Y,0.0);
  if(Away.IsNearlyZero()) {
   const double Rad=FMath::DegreesToRadians(HeadingDeg);
   Away=FVector(FMath::Cos(Rad),FMath::Sin(Rad),0.0);
  }
  Away.Normalize();
  FVector Next=Here+Away*RetreatSpeedCmS*DeltaSeconds;
  if(Ground.IsValid()) Next.Z=Ground->GroundAt(Next.X,Next.Y);
  SetActorLocation(Next);
  SetActorRotation(FRotator(0,Away.Rotation().Yaw,0));
 } else if(!ToPlayer.IsNearlyZero()) {
  // Notice, Watch and Warn stand still and face the player.
  SetActorRotation(FRotator(0,ToPlayer.Rotation().Yaw,0));
 }
}
