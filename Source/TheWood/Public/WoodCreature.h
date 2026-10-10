#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Generation/WoodFauna.h"
#include "WoodCreature.generated.h"

class UStaticMeshComponent;
class AWoodWorld;

// Placeholder fauna actor. Behaviour comes entirely from the engine-free wood::fauna core.
UCLASS()
class THEWOOD_API AWoodCreature : public AActor {
 GENERATED_BODY()
public:
 AWoodCreature();
 // Called once after spawn. Terrain supplies ground height for retreat moves; HeadingDeg is the fallback retreat direction.
 void Init(wood::fauna::CreatureKind Kind, AWoodWorld* Terrain, double HeadingDeg);
 virtual void Tick(float DeltaSeconds) override;
 // Capture/review: while true no creature moves or turns (the FSM is not stepped).
 static bool bFreezeAll;
 wood::fauna::CreatureState CurrentState() const { return StateValue; }
private:
 UPROPERTY() TObjectPtr<UStaticMeshComponent> Body;
 TWeakObjectPtr<AWoodWorld> Ground;
 wood::fauna::CreatureKind KindValue=wood::fauna::CreatureKind::Deer;
 wood::fauna::CreatureState StateValue=wood::fauna::CreatureState::Idle;
 wood::fauna::CreatureMind Mind;
 double HeadingDeg=0;
};
