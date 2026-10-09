using UnrealBuildTool;
public class TheWood : ModuleRules {
 public TheWood(ReadOnlyTargetRules Target) : base(Target) {
  PCHUsage = PCHUsageMode.UseExplicitOrSharedPCHs;
  CppStandard = CppStandardVersion.Cpp20;
  bEnableExceptions = true;
  PublicDependencyModuleNames.AddRange(new string[] {"Core", "CoreUObject", "Engine", "InputCore", "ProceduralMeshComponent", "UMG", "Slate", "SlateCore"});
 }
}
