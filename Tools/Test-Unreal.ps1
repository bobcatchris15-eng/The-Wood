param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8')
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$editor=Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
$output=Join-Path $taskRoot '.cache/unreal-tests.log'
$report=Join-Path $taskRoot 'Saved/Automation'
New-Item -ItemType Directory -Force -Path (Join-Path $taskRoot '.cache') | Out-Null
& $editor (Join-Path $taskRoot 'TheWood.uproject') -unattended -nosplash -nullrhi -WoodFresh -WoodWild '-ExecCmds=Automation RunTests Wood.Runtime' '-TestExit=Automation Test Queue Empty' "-ReportExportPath=$report" *> $output
if ($LASTEXITCODE -ne 0) { throw "Unreal test process failed; see $output" }
$results=Get-Content (Join-Path $report 'index.json') -Raw | ConvertFrom-Json
# index.json splits passes into 'succeeded' (clean) and 'succeededWithWarnings'; count both as passes.
$passStates=@('Success','SucceededWithWarnings')
$tests=@($results.tests)
$passed=@($tests | Where-Object { $_.state -in $passStates }).Count
$failed=[Math]::Max([int]$results.failed, @($tests | Where-Object { $_.state -notin $passStates }).Count)
if ($failed -gt 0 -or $passed -lt 1) {
 $tests | ForEach-Object { $_.entries.event | Where-Object type -eq Error | ForEach-Object { Write-Output $_.message } }
 throw 'Unreal runtime tests failed'
}
Write-Output "PASS: $passed Unreal runtime test, $failed failures"
