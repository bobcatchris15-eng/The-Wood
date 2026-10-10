param([string]$EngineRoot='C:/Program Files/Epic Games/UE_5.8')
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$editor=Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
New-Item -ItemType Directory -Force -Path (Join-Path $taskRoot '.cache') | Out-Null
# index.json splits passes into 'succeeded' (clean) and 'succeededWithWarnings'; count both as passes.
$passStates=@('Success','SucceededWithWarnings')
# Pass 1: wilderness start (-WoodWild). Pass 2: real fresh startup at the trailhead (-WoodFresh only).
$passes=@(
 @{ Name='wild';  Log='unreal-tests.log';       Filter='Wood.Runtime'; Flags=@('-WoodFresh','-WoodWild') },
 @{ Name='fresh'; Log='unreal-tests-fresh.log'; Filter='Wood.Fresh';   Flags=@('-WoodFresh') }
)
$totalPassed=0
$totalFailed=0
$perPass=@()
foreach ($p in $passes) {
 $output=Join-Path $taskRoot ".cache/$($p.Log)"
 $report=Join-Path $taskRoot "Saved/Automation/$($p.Name)"
 if (Test-Path $report) { Remove-Item -Recurse -Force $report }
 & $editor (Join-Path $taskRoot 'TheWood.uproject') -unattended -nosplash -nullrhi @($p.Flags) "-ExecCmds=Automation RunTests $($p.Filter)" '-TestExit=Automation Test Queue Empty' "-ReportExportPath=$report" *> $output
 if ($LASTEXITCODE -ne 0) { throw "Unreal test process failed ($($p.Name)); see $output" }
 $results=Get-Content (Join-Path $report 'index.json') -Raw | ConvertFrom-Json
 $tests=@($results.tests)
 $passed=@($tests | Where-Object { $_.state -in $passStates }).Count
 $failed=[Math]::Max([int]$results.failed, @($tests | Where-Object { $_.state -notin $passStates }).Count)
 if ($failed -gt 0 -or $passed -lt 1) {
  $tests | ForEach-Object { $_.entries.event | Where-Object type -eq Error | ForEach-Object { Write-Output $_.message } }
  throw "Unreal runtime tests failed ($($p.Name))"
 }
 $totalPassed+=$passed
 $totalFailed+=$failed
 $perPass+="$($p.Name) $passed"
}
Write-Output "PASS: $totalPassed Unreal runtime test, $totalFailed failures ($($perPass -join ', '))"
