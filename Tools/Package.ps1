# Packaged Win64 build via RunUAT BuildCookRun.
# -DryRun prints the exact command and exits without running UAT.
param(
 [string]$EngineRoot = 'C:/Program Files/Epic Games/UE_5.8',
 [ValidateSet('Development','Shipping')][string]$Config = 'Development',
 [string]$Out = 'Saved/Package',
 [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$project = Join-Path $taskRoot 'TheWood.uproject'
$uat = Join-Path $EngineRoot 'Engine/Build/BatchFiles/RunUAT.bat'
$outDir = if ([System.IO.Path]::IsPathRooted($Out)) { $Out } else { Join-Path $taskRoot $Out }
$uatArgs = @(
 'BuildCookRun',
 "-project=$project",
 '-platform=Win64',
 "-clientconfig=$Config",
 '-build','-cook','-stage','-pak','-archive',
 "-archivedirectory=$outDir",
 '-noP4','-unattended'
)
$cmd = "`"$uat`" " + ($uatArgs -join ' ')
if ($DryRun) {
 Write-Output "DRYRUN: $cmd"
 Write-Output "DRYRUN: archive dir $outDir"
 exit 0
}
if (!(Test-Path -LiteralPath $uat)) { throw "RunUAT not found at $uat" }
& $uat @uatArgs
if ($LASTEXITCODE -ne 0) { throw "BuildCookRun failed (exit $LASTEXITCODE)" }
$archive = Join-Path $outDir 'WindowsNoEditor'
if (Test-Path -LiteralPath $archive) { Write-Output "ARCHIVE: $archive" } else { Write-Output "ARCHIVE: $outDir" }
