# Fixed-length frame-time capture (CsvProfile) at 1920x1080 windowed.
# Mode: -Exe <packaged exe> runs without -game; otherwise UnrealEditor.exe <uproject> -game.
# Walk: no autopilot/benchmark flag exists in source, so the view is static (trailhead via -WoodFresh).
# -Seed / -View are passed as -Seed= / -View= for tooling; the game does not consume them yet.
# Stop: graceful CloseMainWindow after -Seconds; CSV flush on exit is best effort.
# -DryRun prints the command and exits without launching.
param(
 [int]$Seconds = 120,
 [int]$Seed = -1,
 [ValidateSet('','Forest','Stream','Ridge','Grassland','Taiga','Highlands','Roots','Ruins')][string]$View = '',
 [string]$Exe = '',
 [string]$EngineRoot = 'C:/Program Files/Epic Games/UE_5.8',
 [switch]$DryRun
)
$ErrorActionPreference = 'Stop'
if ($Seconds -lt 1) { throw 'Seconds must be >= 1' }
$taskRoot = Split-Path $PSScriptRoot -Parent
$project = Join-Path $taskRoot 'TheWood.uproject'
if ($Exe) {
 $exePath = $Exe
 $lead = @()
} else {
 $exePath = Join-Path $EngineRoot 'Engine/Binaries/Win64/UnrealEditor.exe'
 $lead = @("`"$project`"", '-game')
}
$common = @('-windowed','-ResX=1920','-ResY=1080','-nosplash','-log','-WoodFresh','-ExecCmds="stat unit;CsvProfile Start"')
if ($Seed -ge 0) { $common += "-Seed=$Seed" }
if ($View) { $common += "-View=$View" }
$argList = (@($lead + $common)) -join ' '
if ($DryRun) {
 Write-Output "DRYRUN: `"$exePath`" $argList"
 Write-Output "DRYRUN: stop after $Seconds s, copy newest CSV to Saved/FrameTime/<timestamp>.csv"
 exit 0
}
if (!(Test-Path -LiteralPath $exePath)) { throw "Executable not found: $exePath" }
$start = Get-Date
$proc = Start-Process -FilePath $exePath -ArgumentList $argList -PassThru
Start-Sleep -Seconds $Seconds
if (!$proc.HasExited) {
 [void]$proc.CloseMainWindow()
 if (!$proc.WaitForExit(20000)) { $proc.Kill() }
}
$csv = Get-ChildItem -Path (Join-Path $taskRoot 'Saved') -Recurse -Filter *.csv -ErrorAction SilentlyContinue |
 Where-Object { $_.LastWriteTime -ge $start } |
 Sort-Object LastWriteTime -Descending | Select-Object -First 1
if (!$csv) { throw 'No CSV produced after capture; inspect Saved/Profiling' }
$outDir = Join-Path $taskRoot 'Saved/FrameTime'
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
$dest = Join-Path $outDir ((Get-Date -Format 'yyyyMMdd-HHmmss') + '.csv')
Copy-Item -LiteralPath $csv.FullName -Destination $dest
Write-Output $dest
