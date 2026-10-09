#pragma once
#include "CoreMinimal.h"
#include "Widgets/SCompoundWidget.h"

class SBorder;
struct FSlateDynamicImageBrush;

// Photo gallery over Saved/Photos, newest first. Escape steps back from full view, then closes.
class SWoodGallery : public SCompoundWidget {
public:
 SLATE_BEGIN_ARGS(SWoodGallery) {}
  SLATE_EVENT(FSimpleDelegate, OnRequestClose)
 SLATE_END_ARGS()

 void Construct(const FArguments& InArgs);
 virtual bool SupportsKeyboardFocus() const override { return true; }
 virtual FReply OnKeyDown(const FGeometry& MyGeometry, const FKeyEvent& InKeyEvent) override;

private:
 FSimpleDelegate CloseDelegate;
 TSharedPtr<SBorder> ContentArea;
 TArray<FString> Photos;
 TArray<TSharedPtr<FSlateDynamicImageBrush>> Brushes;
 TSharedPtr<FSlateDynamicImageBrush> FullBrush;
 int32 Selected=INDEX_NONE;

 void Rescan();
 void ShowGrid();
 void ShowFull(int32 Index);
 void ShowConfirm(int32 Index);
 void DeletePhoto(int32 Index);
};
