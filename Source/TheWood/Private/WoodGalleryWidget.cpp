#include "WoodGalleryWidget.h"
#include "Brushes/SlateDynamicImageBrush.h"
#include "Styling/CoreStyle.h"
#include "HAL/FileManager.h"
#include "Misc/Paths.h"
#include "Widgets/Layout/SBorder.h"
#include "Widgets/Layout/SBox.h"
#include "Widgets/SBoxPanel.h"
#include "Widgets/Layout/SScrollBox.h"
#include "Widgets/Layout/SUniformGridPanel.h"
#include "Widgets/Input/SButton.h"
#include "Widgets/Images/SImage.h"
#include "Widgets/Text/STextBlock.h"

namespace {
 const int32 WoodGalleryColumns=4;
 const int32 WoodGalleryMaxThumbs=48;
 FString WoodPhotoDir() { return FPaths::Combine(FPaths::ProjectSavedDir(),TEXT("Photos")); }
 TSharedRef<SWidget> Caption(const FString& Text,int32 Size) {
  return SNew(STextBlock).Text(FText::FromString(Text)).Font(FCoreStyle::GetDefaultFontStyle(TEXT("Regular"),Size));
 }
 TSharedRef<SWidget> Btn(const FString& Text,TFunction<void()> Fn) {
  return SNew(SButton).Text(FText::FromString(Text)).OnClicked_Lambda([Fn]{ Fn(); return FReply::Handled(); });
 }
}

void SWoodGallery::Construct(const FArguments& InArgs) {
 CloseDelegate=InArgs._OnRequestClose;
 ChildSlot.HAlign(HAlign_Fill).VAlign(VAlign_Fill)[
  SAssignNew(ContentArea,SBorder).BorderBackgroundColor(FLinearColor(0.0f,0.0f,0.0f,0.85f)).Padding(FMargin(32.0f))
 ];
 Rescan();
 ShowGrid();
}

void SWoodGallery::Rescan() {
 Photos.Reset();
 Brushes.Reset();
 FullBrush.Reset();
 Selected=INDEX_NONE;
 const FString Dir=WoodPhotoDir();
 TArray<FString> Names;
 IFileManager::Get().FindFiles(Names,*FPaths::Combine(Dir,TEXT("*.png")),true,false);
 // Filenames start with YYYYMMDD-HHMMSS, so descending lexical order is newest first.
 Names.Sort([](const FString& A,const FString& B){ return FCString::Strcmp(*A,*B)>0; });
 for(const FString& Name:Names) Photos.Add(FPaths::Combine(Dir,Name));
 Brushes.SetNum(Photos.Num());
}

void SWoodGallery::ShowGrid() {
 Selected=INDEX_NONE;
 FullBrush.Reset();
 if(Photos.Num()==0) {
  TSharedRef<SVerticalBox> Empty=SNew(SVerticalBox);
  Empty->AddSlot().AutoHeight()[ Caption(TEXT("No photos yet. Press C or right mouse to take one."),16) ];
  Empty->AddSlot().AutoHeight().Padding(0,16,0,0)[ Btn(TEXT("Close"),[this]{ CloseDelegate.ExecuteIfBound(); }) ];
  ContentArea->SetContent(Empty);
  return;
 }

 TSharedRef<SUniformGridPanel> Grid=SNew(SUniformGridPanel).SlotPadding(FMargin(6.0f));
 const int32 Count=FMath::Min(Photos.Num(),WoodGalleryMaxThumbs);
 for(int32 i=0;i<Count;++i) {
  if(!Brushes[i].IsValid()) Brushes[i]=MakeShared<FSlateDynamicImageBrush>(FName(*Photos[i]),FVector2D(160.0f,90.0f));
  Grid->AddSlot(i%WoodGalleryColumns,i/WoodGalleryColumns)[
   SNew(SButton).ContentPadding(FMargin(0.0f)).OnClicked_Lambda([this,i]{ ShowFull(i); return FReply::Handled(); })[
    SNew(SImage).Image(Brushes[i].Get())
   ]
  ];
 }

 TSharedRef<SScrollBox> Scroll=SNew(SScrollBox);
 Scroll->AddSlot()[ Grid ];

 TSharedRef<SVerticalBox> Body=SNew(SVerticalBox);
 Body->AddSlot().FillHeight(1.0f)[ Scroll ];
 Body->AddSlot().AutoHeight().Padding(0,12,0,0)[ Caption(FString::Printf(TEXT("%d photos, newest %d shown"),Photos.Num(),Count),14) ];
 Body->AddSlot().AutoHeight().Padding(0,12,0,0)[ Btn(TEXT("Close"),[this]{ CloseDelegate.ExecuteIfBound(); }) ];
 ContentArea->SetContent(Body);
}

void SWoodGallery::ShowFull(int32 Index) {
 if(!Photos.IsValidIndex(Index)) return;
 Selected=Index;
 FullBrush=MakeShared<FSlateDynamicImageBrush>(FName(*Photos[Index]),FVector2D(1280.0f,720.0f));

 TSharedRef<SHorizontalBox> Buttons=SNew(SHorizontalBox);
 Buttons->AddSlot().AutoWidth().Padding(8,0)[ Btn(TEXT("Back"),[this]{ ShowGrid(); }) ];
 Buttons->AddSlot().AutoWidth().Padding(8,0)[ Btn(TEXT("Delete"),[this,Index]{ ShowConfirm(Index); }) ];

 TSharedRef<SVerticalBox> Body=SNew(SVerticalBox);
 Body->AddSlot().FillHeight(1.0f).HAlign(HAlign_Center).VAlign(VAlign_Center)[ SNew(SImage).Image(FullBrush.Get()) ];
 Body->AddSlot().AutoHeight().HAlign(HAlign_Center).Padding(0,12,0,0)[ Buttons ];
 ContentArea->SetContent(Body);
}

void SWoodGallery::ShowConfirm(int32 Index) {
 if(!Photos.IsValidIndex(Index)) return;
 TSharedRef<SHorizontalBox> Buttons=SNew(SHorizontalBox);
 Buttons->AddSlot().AutoWidth().Padding(8,0)[ Btn(TEXT("Delete"),[this,Index]{ DeletePhoto(Index); }) ];
 Buttons->AddSlot().AutoWidth().Padding(8,0)[ Btn(TEXT("Cancel"),[this,Index]{ ShowFull(Index); }) ];

 TSharedRef<SVerticalBox> Body=SNew(SVerticalBox);
 Body->AddSlot().AutoHeight()[ Caption(TEXT("Delete this photo? This cannot be undone."),16) ];
 Body->AddSlot().AutoHeight().Padding(0,16,0,0)[ Buttons ];
 ContentArea->SetContent(Body);
}

void SWoodGallery::DeletePhoto(int32 Index) {
 if(!Photos.IsValidIndex(Index)) return;
 IFileManager::Get().Delete(*Photos[Index]);
 Photos.RemoveAt(Index);
 if(Brushes.IsValidIndex(Index)) Brushes.RemoveAt(Index);
 ShowGrid();
}

FReply SWoodGallery::OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) {
 const FKey Key=InKeyEvent.GetKey();
 if(Key==EKeys::Escape&&Selected!=INDEX_NONE) {
  ShowGrid();
  return FReply::Handled();
 }
 if(Key==EKeys::Escape||Key==EKeys::G) {
  CloseDelegate.ExecuteIfBound();
  return FReply::Handled();
 }
 return SCompoundWidget::OnKeyDown(MyGeometry,InKeyEvent);
}
