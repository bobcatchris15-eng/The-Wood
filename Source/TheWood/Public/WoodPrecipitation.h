#pragma once
#include "CoreMinimal.h"
#include "GameFramework/Actor.h"
#include "Components/SceneComponent.h"
#include "WoodWeatherComponent.h"
#include "WoodPrecipitation.generated.h"

class UInstancedStaticMeshComponent;
class UStaticMesh;
class UMaterialInterface;

// One rain streak or snowflake. Position is world space, cm.
struct FWoodFlake {
 FVector Pos=FVector::ZeroVector;
 float Speed=1.0f;
 int32 Atlas=0;
};

// Camera-centred precipitation without Niagara: two instanced quad pools (rain streaks, snowflakes)
// recycled each tick inside a 30 m box. Quads billboard to the camera yaw and sample a 4x4 atlas.
UCLASS()
class THEWOOD_API AWoodPrecipitation : public AActor {
 GENERATED_BODY()
public:
 AWoodPrecipitation();
 // Called by AWoodWorld each frame. Active count = capacity x Intensity; Clear and Overcast show nothing.
 void Drive(float DeltaSeconds, FVector CenterCm, EWoodPrecip Kind, float Intensity, float WindMps, float CameraYawDeg);
private:
 bool bReady=false;
 uint32 Draws=0;
 UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> RainPool;
 UPROPERTY() TObjectPtr<UInstancedStaticMeshComponent> SnowPool;
 TArray<FWoodFlake> RainFlakes;
 TArray<FWoodFlake> SnowFlakes;
 void Initialize();
 UInstancedStaticMeshComponent* MakePool(const TCHAR* Name,UStaticMesh* Mesh,UMaterialInterface* Material,int32 Count);
 void Step(UInstancedStaticMeshComponent* Pool,TArray<FWoodFlake>& Flakes,int32 Active,float Dt,FVector CenterCm,FVector DriftCmPerS,float FallCmPerS,FVector Scale,float CameraYawDeg,uint32 Salt);
};
