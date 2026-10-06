param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8')
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$editor=Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
$output=Join-Path $taskRoot '.cache/unreal-tests.log'
$report=Join-Path $taskRoot 'Saved/Automation'
New-Item -ItemType Directory -Force -Path (Join-Path $taskRoot '.cache') | Out-Null
& $editor (Join-Path $taskRoot 'TheWood.uproject') -unattended -nosplash -nullrhi '-ExecCmds=Automation RunTests Wood.Runtime' '-TestExit=Automation Test Queue Empty' "-ReportExportPath=$report" *> $output
if ($LASTEXITCODE -ne 0) { throw "Unreal test process failed; see $output" }
$results=Get-Content (Join-Path $report 'index.json') -Raw | ConvertFrom-Json
if ($results.failed -gt 0 -or $results.succeeded -lt 1) {
 $results.tests.entries.event | Where-Object type -eq Error | ForEach-Object { Write-Output $_.message }
 throw 'Unreal runtime tests failed'
}
Write-Output "PASS: $($results.succeeded) Unreal runtime test, $($results.failed) failures"
