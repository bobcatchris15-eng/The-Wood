#include "WoodSettingsWidget.h"
#include "GameFramework/GameUserSettings.h"
#include "Misc/ConfigCacheIni.h"
#include "Misc/Paths.h"
#include "HAL/FileManager.h"
#include "Styling/CoreStyle.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Input/SSlider.h"
#include "Widgets/Input/SCheckBox.h"
#include "Widgets/Text/STextBlock.h"

namespace {
 const TCHAR* const WoodSection=TEXT("/Script/TheWood.WoodSettings");
 FString WoodIniPath() { return FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Config/WoodSettings.ini")); }
 TSharedRef<SWidget> Caption(const FString& Text,int32 Size) {
  return SNew(STextBlock).Text(FText::FromString(Text)).Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"),Size));
 }
 TSharedRef<SWidget> Btn(const FString& Text,TFunction<void()> Fn) {
  return SNew(SButton).Text(FText::FromString(Text)).OnClicked_Lambda([Fn]{ Fn(); return FReply::Handled(); });
 }
}

FWoodSettings FWoodSettings::Load() {
 FWoodSettings S;
 if(UGameUserSettings* G=UGameUserSettings::GetGameUserSettings()) {
  S.ScalabilityLevel=G->GetOverallScalabilityLevel();
  const FIntPoint R=G->GetScreenResolution();
  S.ResX=R.X;
  S.ResY=R.Y;
  S.bFullscreen=G->GetFullscreenMode()!=EWindowMode::Windowed;
 }
 const FString Path=WoodIniPath();
 GConfig->LoadFile(Path);
 GConfig->GetFloat(WoodSection,TEXT("MouseSensitivity"),S.MouseSensitivity,Path);
 GConfig->GetBool(WoodSection,TEXT("InvertY"),S.bInvertY,Path);
 GConfig->GetFloat(WoodSection,TEXT("FOV"),S.FOV,Path);
 GConfig->GetFloat(WoodSection,TEXT("MasterVolume"),S.MasterVolume,Path);
 GConfig->GetFloat(WoodSection,TEXT("AmbientVolume"),S.AmbientVolume,Path);
 S.MouseSensitivity=FMath::Clamp(S.MouseSensitivity,0.2f,3.0f);
 S.FOV=FMath::Clamp(S.FOV,70.0f,100.0f);
 S.MasterVolume=FMath::Clamp(S.MasterVolume,0.0f,1.0f);
 S.AmbientVolume=FMath::Clamp(S.AmbientVolume,0.0f,1.0f);
 return S;
}

void FWoodSettings::Save() const {
 const FString Path=WoodIniPath();
 IFileManager::Get().MakeDirectory(*FPaths::GetPath(Path),true);
 GConfig->SetFloat(WoodSection,TEXT("MouseSensitivity"),MouseSensitivity,Path);
 GConfig->SetBool(WoodSection,TEXT("InvertY"),bInvertY,Path);
 GConfig->SetFloat(WoodSection,TEXT("FOV"),FOV,Path);
 GConfig->SetFloat(WoodSection,TEXT("MasterVolume"),MasterVolume,Path);
 GConfig->SetFloat(WoodSection,TEXT("AmbientVolume"),AmbientVolume,Path);
 GConfig->Flush(false,Path);
}

void FWoodSettings::ApplyEngine() const {
 UGameUserSettings* G=UGameUserSettings::GetGameUserSettings();
 if(!G) return;
 G->SetOverallScalabilityLevel(ScalabilityLevel);
 G->SetScreenResolution(FIntPoint(ResX,ResY));
 G->SetFullscreenMode(bFullscreen?EWindowMode::WindowedFullscreen:EWindowMode::Windowed);
 G->ApplySettings(false);
 G->SaveSettings();
}

void SWoodSettings::Construct(const FArguments& InArgs) {
 Values=InArgs._Initial;
 OnChangedDelegate=InArgs._OnChanged;
 OnClosedDelegate=InArgs._OnClosed;

 TSharedRef<SVerticalBox> Body=SNew(SVerticalBox);
 Body->AddSlot().AutoHeight().Padding(0,0,0,16)[ Caption(TEXT("Settings"),22) ];

 Body->AddSlot().AutoHeight().Padding(0,4)[
  SNew(STextBlock).Text_Lambda([this]{ return FText::FromString(FString::Printf(TEXT("Mouse sensitivity  %.2f"),Values.MouseSensitivity)); })
   .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"),14))
 ];
 Body->AddSlot().AutoHeight()[
  SNew(SSlider)
   .Value_Lambda([this]{ return (Values.MouseSensitivity-0.2f)/2.8f; })
   .OnValueChanged_Lambda([this](float T){ Values.MouseSensitivity=0.2f+2.8f*FMath::Clamp(T,0.0f,1.0f); Changed(); })
 ];
 Body->AddSlot().AutoHeight().Padding(0,8,0,0)[
  SNew(SCheckBox)
   .IsChecked_Lambda([this]{ return Values.bInvertY?ECheckBoxState::Checked:ECheckBoxState::Unchecked; })
   .OnCheckStateChanged_Lambda([this](ECheckBoxState S){ Values.bInvertY=(S==ECheckBoxState::Checked); Changed(); })
  [ Caption(TEXT("Invert Y"),14) ]
 ];

 Body->AddSlot().AutoHeight().Padding(0,12,0,4)[
  SNew(STextBlock).Text_Lambda([this]{ return FText::FromString(FString::Printf(TEXT("Field of view  %.0f"),Values.FOV)); })
   .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"),14))
 ];
 Body->AddSlot().AutoHeight()[
  SNew(SSlider)
   .Value_Lambda([this]{ return (Values.FOV-70.0f)/30.0f; })
   .OnValueChanged_Lambda([this](float T){ Values.FOV=70.0f+30.0f*FMath::Clamp(T,0.0f,1.0f); Changed(); })
 ];

 Body->AddSlot().AutoHeight().Padding(0,12,0,4)[
  SNew(STextBlock).Text_Lambda([this]{ return FText::FromString(FString::Printf(TEXT("Master volume  %d%%"),FMath::RoundToInt(Values.MasterVolume*100.0f))); })
   .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"),14))
 ];
 Body->AddSlot().AutoHeight()[
  SNew(SSlider)
   .Value_Lambda([this]{ return Values.MasterVolume; })
   .OnValueChanged_Lambda([this](float T){ Values.MasterVolume=FMath::Clamp(T,0.0f,1.0f); Changed(); })
 ];
 Body->AddSlot().AutoHeight().Padding(0,12,0,4)[
  SNew(STextBlock).Text_Lambda([this]{ return FText::FromString(FString::Printf(TEXT("Ambient volume  %d%%"),FMath::RoundToInt(Values.AmbientVolume*100.0f))); })
   .Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"),14))
 ];
 Body->AddSlot().AutoHeight()[
  SNew(SSlider)
   .Value_Lambda([this]{ return Values.AmbientVolume; })
   .OnValueChanged_Lambda([this](float T){ Values.AmbientVolume=FMath::Clamp(T,0.0f,1.0f); Changed(); })
 ];

 Body->AddSlot().AutoHeight().Padding(0,12,0,4)[ Caption(TEXT("Quality preset"),14) ];
 TSharedRef<SHorizontalBox> QualityRow=SNew(SHorizontalBox);
 static const TCHAR* const QualityNames[]={TEXT("Low"),TEXT("Medium"),TEXT("High"),TEXT("Epic"),TEXT("Cinematic")};
 for(int32 L=0;L<5;++L) {
  QualityRow->AddSlot().AutoWidth().Padding(2,0)[ Btn(QualityNames[L],[this,L]{ Values.ScalabilityLevel=L; Changed(); }) ];
 }
 Body->AddSlot().AutoHeight()[ QualityRow ];

 Body->AddSlot().AutoHeight().Padding(0,12,0,4)[ Caption(TEXT("Resolution"),14) ];
 TSharedRef<SHorizontalBox> ResRow=SNew(SHorizontalBox);
 static const FIntPoint ResList[]={FIntPoint(1280,720),FIntPoint(1920,1080),FIntPoint(2560,1440)};
 static const TCHAR* const ResNames[]={TEXT("720p"),TEXT("1080p"),TEXT("1440p")};
 for(int32 R=0;R<3;++R) {
  ResRow->AddSlot().AutoWidth().Padding(2,0)[ Btn(ResNames[R],[this,R]{ Values.ResX=ResList[R].X; Values.ResY=ResList[R].Y; Changed(); }) ];
 }
 Body->AddSlot().AutoHeight()[ ResRow ];

 Body->AddSlot().AutoHeight().Padding(0,12,0,0)[
  SNew(SCheckBox)
   .IsChecked_Lambda([this]{ return Values.bFullscreen?ECheckBoxState::Checked:ECheckBoxState::Unchecked; })
   .OnCheckStateChanged_Lambda([this](ECheckBoxState S){ Values.bFullscreen=(S==ECheckBoxState::Checked); Changed(); })
  [ Caption(TEXT("Fullscreen"),14) ]
 ];

 Body->AddSlot().AutoHeight().Padding(0,20,0,0).HAlign(HAlign_Right)[ Btn(TEXT("Close"),[this]{ CloseRequested(); }) ];

 ChildSlot.HAlign(HAlign_Center).VAlign(VAlign_Center)[
  SNew(SBorder).BorderBackgroundColor(FLinearColor(0.0f,0.0f,0.0f,0.9f)).Padding(FMargin(32.0f))[
   SNew(SBox).WidthOverride(560.0f)[ Body ]
  ]
 ];
}

FReply SWoodSettings::OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) {
 const FKey Key=InKeyEvent.GetKey();
 if(Key==EKeys::Escape||Key==EKeys::F10) {
  CloseRequested();
  return FReply::Handled();
 }
 return SCompoundWidget::OnKeyDown(MyGeometry,InKeyEvent);
}

void SWoodSettings::Changed() {
 OnChangedDelegate.ExecuteIfBound(Values);
}

void SWoodSettings::CloseRequested() {
 OnClosedDelegate.ExecuteIfBound(Values);
}
