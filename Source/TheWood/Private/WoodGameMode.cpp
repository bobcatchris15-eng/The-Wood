#include "WoodGameMode.h"
#include "WoodCharacter.h"
#include "WoodWorld.h"
#include "WoodAmbience.h"
#include "EngineUtils.h"
#include "Engine/World.h"
#include "GameFramework/PlayerController.h"
AWoodGameMode::AWoodGameMode() { DefaultPawnClass=AWoodCharacter::StaticClass(); }
void AWoodGameMode::BeginPlay() {
 Super::BeginPlay();
 if(!TActorIterator<AWoodWorld>(GetWorld())) GetWorld()->SpawnActor<AWoodWorld>();
 if(!TActorIterator<AWoodAmbience>(GetWorld())) GetWorld()->SpawnActor<AWoodAmbience>();
}
void AWoodGameMode::RestartPlayer(AController* NewPlayer) {
 // RestartPlayer can run before GameMode BeginPlay: terrain must exist first.
 AWoodWorld* Environment=nullptr;
 for(TActorIterator<AWoodWorld> It(GetWorld());It;++It) { Environment=*It; break; }
 if(!Environment) Environment=GetWorld()->SpawnActor<AWoodWorld>();
 if(!Environment) { UE_LOG(LogTemp,Error,TEXT("Cannot spawn generated environment")); return; }
 // A resume restores the saved transform; it is consumed by the first spawn only.
 FVector Resumed;
 FRotator ResumedView;
 if(Environment->TakeResumedPlayer(Resumed,ResumedView)) {
  RestartPlayerAtTransform(NewPlayer,FTransform(FRotator(0,ResumedView.Yaw,0),Resumed));
  NewPlayer->SetControlRotation(ResumedView);
  return;
 }
 FVector Position=Environment->ExplorerStart();
 Position.Z=Environment->GroundAt(Position.X,Position.Y)+100;
 // Trailhead lot faces north (+Y, yaw 90); wilderness start keeps its old heading.
 RestartPlayerAtTransform(NewPlayer,FTransform(FRotator(0,Environment->StartsAtTrailhead()?90:40,0),Position));
}
