#pragma once
#include "CoreMinimal.h"
#include "GameFramework/GameModeBase.h"
#include "WoodGameMode.generated.h"
UCLASS()
class THEWOOD_API AWoodGameMode : public AGameModeBase {
 GENERATED_BODY()
public:
 AWoodGameMode();
 virtual void BeginPlay() override;
 virtual void RestartPlayer(AController* NewPlayer) override;
};
