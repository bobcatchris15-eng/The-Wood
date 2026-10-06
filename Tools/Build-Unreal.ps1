param([Parameter(Mandatory=$true)][string]$EngineRoot, [switch]$InitializeContent)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$project = Join-Path $taskRoot 'TheWood.uproject'
$build = Join-Path $EngineRoot 'Engine/Build/BatchFiles/Build.bat'
$editor = Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
if (!(Test-Path -LiteralPath $build)) { throw "Unreal build tool not found at $build" }
$version = Get-Content (Join-Path $EngineRoot 'Engine/Build/Build.version') -Raw | ConvertFrom-Json
if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 8) { throw 'This project is pinned to Unreal 5.8. Use an installed 5.8 release.' }
& $build TheWoodEditor Win64 Development "-Project=$project" -WaitMutex
if ($LASTEXITCODE -ne 0) { throw 'Unreal Editor build failed' }
if ($InitializeContent) {
 $bootstrapLog=Join-Path $taskRoot 'Saved/Logs/ContentBootstrap.log'
 & $editor $project "-ExecutePythonScript=$taskRoot/Tools/BootstrapEditor.py" "-abslog=$bootstrapLog" -unattended -nosplash -nullrhi -stdout -FullStdOutLogOutput
 if ($LASTEXITCODE -ne 0) { throw 'Content bootstrap failed; inspect Saved/Logs' }
 if (Select-String -LiteralPath $bootstrapLog -Pattern 'LogPython: Error:|Python script executed with errors' -Quiet) { throw 'Content bootstrap Python failed; inspect Saved/Logs/ContentBootstrap.log' }
 foreach ($asset in @('Content/Maps/VisualBenchmark.umap','Content/Wood/DA_BenchmarkPalette.uasset')) {
  if (!(Test-Path -LiteralPath (Join-Path $taskRoot $asset))) { throw "Content bootstrap did not create $asset; inspect Saved/Logs for Python errors" }
 }
}

