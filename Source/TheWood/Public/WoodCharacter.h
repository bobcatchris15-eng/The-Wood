#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "WoodCharacter.generated.h"
class UCameraComponent;
class AWoodWorld;

UCLASS()
class THEWOOD_API AWoodCharacter : public ACharacter {
 GENERATED_BODY()
public:
 AWoodCharacter();
 virtual void BeginPlay() override;
 virtual void Tick(float DeltaSeconds) override;
 virtual void SetupPlayerInputComponent(UInputComponent* Input) override;
 UFUNCTION(Exec) void WoodView(const FString& View);
 UFUNCTION(Exec) void WoodCapture(const FString& View,float Delay=1.0f);
 UFUNCTION(Exec) void Photograph();
private:
 UPROPERTY() TObjectPtr<UCameraComponent> Camera;
 UPROPERTY() TObjectPtr<AWoodWorld> Environment;
 double LastPhotoSeconds=-10;
 void Forward(float Value);
 void Right(float Value);
 void Turn(float Value);
 void Look(float Value);
 void Sit();
 void Accelerate();
 void StartJump();
};
