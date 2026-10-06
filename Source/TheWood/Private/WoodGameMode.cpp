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
 FVector Position=Environment->ExplorerStart();
 Position.Z=Environment->GroundAt(Position.X,Position.Y)+100;
 RestartPlayerAtTransform(NewPlayer,FTransform(FRotator(0,40,0),Position));
}
