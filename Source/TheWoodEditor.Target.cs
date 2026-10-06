using UnrealBuildTool;
using System.Collections.Generic;
public class TheWoodEditorTarget : TargetRules {
 public TheWoodEditorTarget(TargetInfo Target) : base(Target) {
  Type = TargetType.Editor;
  DefaultBuildSettings = BuildSettingsVersion.V7;
  IncludeOrderVersion = EngineIncludeOrderVersion.Unreal5_8;
  ExtraModuleNames.Add("TheWood");
 }
}

