#pragma once
#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

// Player-facing settings. Engine-owned values (scalability, resolution, fullscreen) live in
// UGameUserSettings / GameUserSettings.ini. Game-owned values live in Saved/Config/WoodSettings.ini.
struct FWoodSettings {
 float MouseSensitivity=1.0f;
 bool bInvertY=false;
 float FOV=80.0f;
 float MasterVolume=1.0f;
 float AmbientVolume=1.0f;
 int32 ScalabilityLevel=3;
 int32 ResX=1920;
 int32 ResY=1080;
 bool bFullscreen=true;

 static FWoodSettings Load();
 void Save() const;
 void ApplyEngine() const;
};

DECLARE_DELEGATE_OneParam(FOnWoodSettingsEvent, FWoodSettings);

class SWoodSettings : public SCompoundWidget {
public:
 SLATE_BEGIN_ARGS(SWoodSettings) {}
  SLATE_ARGUMENT(FWoodSettings, Initial)
  SLATE_EVENT(FOnWoodSettingsEvent, OnChanged)
  SLATE_EVENT(FOnWoodSettingsEvent, OnClosed)
 SLATE_END_ARGS()

 void Construct(const FArguments& InArgs);
 virtual bool SupportsKeyboardFocus() const override { return true; }
 virtual FReply OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) override;
 const FWoodSettings& GetValues() const { return Values; }

private:
 FWoodSettings Values;
 FOnWoodSettingsEvent OnChangedDelegate;
 FOnWoodSettingsEvent OnClosedDelegate;
 void Changed();
 void CloseRequested();
};
