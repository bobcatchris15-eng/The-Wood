#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Character.h"
#include "WoodCharacter.generated.h"
class UCameraComponent;
class AWoodWorld;
class SWoodGallery;
class SWoodSettings;
struct FWoodSettings;

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
 UFUNCTION(Exec) void WoodDumpView(float RadiusM=60.0f);
 // Sprint hold state (Left Shift). Public so automation can drive it without input.
 void SetSprintHeld(bool bHeld);
private:
 bool bSprintHeld=false;
 float SprintAlpha=0.0f; // 0 = walk, 1 = full sprint; linear ramp, eased into FOV kick
 float BaseFOV=80.0f;    // settings FOV; sprint adds a kick on top
 UPROPERTY() TObjectPtr<UCameraComponent> Camera;
 UPROPERTY() TObjectPtr<AWoodWorld> Environment;
 double LastPhotoSeconds=-10;
 TSharedPtr<SWoodGallery> Gallery;
 TSharedPtr<SWoodSettings> SettingsMenu;
 float MouseSensitivity=1.0f;
 bool bInvertY=false;
 void ToggleGallery();
 void ToggleSettings();
 void CloseMenu();
 void ApplyRuntimeSettings(const FWoodSettings& S);
 void HandleSettingsChanged(FWoodSettings S);
 void HandleSettingsClosed(FWoodSettings S);
 void Forward(float Value);
 void Right(float Value);
 void Turn(float Value);
 void Look(float Value);
 void Sit();
 void Accelerate();
 void StartJump();
 void StartSprint();
 void StopSprint();
};
