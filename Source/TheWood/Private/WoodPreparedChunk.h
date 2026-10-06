#pragma once
#include "CoreMinimal.h"
#include "WoodGrounding.h"

// Pure value data produced by a worker; component creation remains on the game thread.
struct FWoodPreparedChunk {
 wood::Chunk Chunk;
 TArray<FVector> Normals;
 TArray<FVector2D> HabitatUV;
 TArray<FLinearColor> BiomeColors;
 TArray<TArray<FTransform>> Placements;
};

FWoodPreparedChunk WoodPrepareChunk(const wood::World& World,int X,int Y,
 const TArray<wood::Kind>& Kinds,const TArray<FWoodPlacementProfile>& Profiles,
 const TArray<bool>& Available,bool Details=true);
