# Fixed-length frame-time capture (CsvProfile) at 1920x1080 windowed, driven by the in-game autopilot.
# Mode: -Exe <packaged exe> runs without -game; otherwise UnrealEditor.exe <uproject> -game.
# Route: -WoodAutopilot=<Seconds> walks the fixed route in AWoodCharacter::TickAutopilot. The game starts CsvProfile
#        at route start, stops it at route end, and quits. -WoodWild gives the wilderness start the route assumes.
# Dev machine, editor -game, not packaged: not the acceptance target (see Docs/Status.md).
# -Seed / -View are passed as -Seed= / -View= for tooling; the game does not consume them.
# Stop: the game quits itself; the script waits Seconds + 300 s for load and route, then closes and kills if needed.
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
$common = @('-windowed','-ResX=1920','-ResY=1080','-nosplash','-log','-WoodFresh','-WoodWild',"-WoodAutopilot=$Seconds",'-ExecCmds="stat unit"')
if ($Seed -ge 0) { $common += "-Seed=$Seed" }
if ($View) { $common += "-View=$View" }
$argList = (@($lead + $common)) -join ' '
if ($DryRun) {
 Write-Output "DRYRUN: `"$exePath`" $argList"
 Write-Output "DRYRUN: game quits after $Seconds s autopilot route; copy newest CSV to Saved/FrameTime/<timestamp>.csv"
 exit 0
}
if (!(Test-Path -LiteralPath $exePath)) { throw "Executable not found: $exePath" }
$start = Get-Date
$proc = Start-Process -FilePath $exePath -ArgumentList $argList -PassThru
# The autopilot clock starts after editor load, so the wait allows load time on top of the route.
if (!$proc.WaitForExit([int](($Seconds + 300) * 1000))) {
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
$summarizer = Join-Path $PSScriptRoot 'Summarize-FrameTime.py'
$py = Get-Command python -ErrorAction SilentlyContinue
if ($py) { & $py.Source $summarizer $dest } else { Write-Output "NOTE: python not on PATH; run Tools\Summarize-FrameTime.py on $dest" }
