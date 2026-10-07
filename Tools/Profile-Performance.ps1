param(
 [Parameter(Mandatory=$true)][string]$EngineRoot,
 [ValidateSet('Development','Shipping')][string]$Configuration='Development',
 [int]$Seed=12345,
 [int]$Width=1920,
 [int]$Height=1080,
 [double]$TargetFps=60,
 [ValidateRange(5,600)][double]$PhaseSeconds=24,
 [ValidateRange(1,64)][int]$PhotoCaptures=4,
 [double]$BudgetMs=0,
 [double]$StallThresholdMs=0,
 [string[]]$Scalability=@(),
 [int]$ColdStartX=22000,
 [int]$ColdStartY=22000,
 [switch]$Fullscreen,
 [switch]$SkipBuild,
 [switch]$Strict
)
# Packaged-build performance harness for Docs/Specification.md section 12.
# Acceptance is 1920x1080 at 60 fps on a recorded mainstream gaming PC, with CPU, GPU, RAM,
# driver, engine patch, resolution and scalability settings captured alongside measured frame
# times. Average frame rate is reported but is not the acceptance signal: stall events during
# chunk realisation and photography are counted separately from steady state.
#
# Frame times come from the engine CSV Profiler (csvprofile start/stop), which needs no project
# source change. Each activity class runs in its own packaged session so stalls are attributed by
# construction instead of by correlating wall-clock windows with frame indices:
#   steady       warm walk of the fixed route, no captures; warm-up frames excluded
#   realisation  cold start away from the streaming centre, so the route neighbourhood is
#                generated during the measured window
#   capture      warm walk of the same route with Photograph commands issued from the console
$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$project = Join-Path $taskRoot 'TheWood.uproject'
$uat = Join-Path $EngineRoot 'Engine/Build/BatchFiles/RunUAT.bat'
$packageRoot = Join-Path $taskRoot 'Saved/Performance/Package'
if (!$BudgetMs) { $BudgetMs = [math]::Round(1000.0 / $TargetFps, 3) }
if (!$StallThresholdMs) { $StallThresholdMs = [math]::Round($BudgetMs * 2, 3) }
$routeName = '{0}-{1}-{2}x{3}' -f (Get-Date -Format 'yyyyMMdd-HHmmss'), $Seed, $Width, $Height
$runRoot = Join-Path $taskRoot "Saved/Performance/$routeName"

function Get-WoodEngineVersion {
 param([string]$Root)
 # Concatenated rather than Join-Path: Join-Path throws on a drive that does not exist.
 $file = "$Root/Engine/Build/Build.version"
 if (!(Test-Path -LiteralPath $file -ErrorAction SilentlyContinue)) { throw "Unreal build descriptor not found at $file" }
 $version = Get-Content -LiteralPath $file -Raw | ConvertFrom-Json
 if ($version.MajorVersion -ne 5 -or $version.MinorVersion -ne 8) { throw 'This project is pinned to Unreal 5.8. Use an installed 5.8 release.' }
 return [ordered]@{
  EngineRoot = $Root
  MajorVersion = $version.MajorVersion
  MinorVersion = $version.MinorVersion
  PatchVersion = $version.PatchVersion
  Changelist = $version.Changelist
  BranchName = $version.BranchName
 }
}

function Get-WoodMachineProfile {
 # WMI reports only a small dedicated allocation for the integrated GPU on the development
 # reference machine; the note keeps that caveat attached to the record (Docs/Hardware.md).
 $cpu = @(Get-CimInstance Win32_Processor)[0]
 $gpu = @(Get-CimInstance Win32_VideoController)
 $system = Get-CimInstance Win32_ComputerSystem
 $os = Get-CimInstance Win32_OperatingSystem
 $display = @($gpu | Where-Object { $_.Name -notmatch 'Microsoft Basic Render' })
 return [ordered]@{
  TimestampUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
  Machine = "$($system.Manufacturer) $($system.Model)"
  Cpu = "$($cpu.Name.Trim()) ($($cpu.NumberOfCores) cores / $($cpu.NumberOfLogicalProcessors) threads, $($cpu.MaxClockSpeed) MHz)"
  RamGB = [math]::Round($system.TotalPhysicalMemory / 1GB, 2)
  Os = "$($os.Caption) $($os.Version) build $($os.BuildNumber)"
  Gpu = @($display | ForEach-Object {
   $ram = if ($_.AdapterRAM) { '{0} GB dedicated reported' -f [math]::Round($_.AdapterRAM / 1GB, 2) } else { 'dedicated memory not reported' }
   $driver = if ($_.DriverDate) { ([datetime]$_.DriverDate).ToString('yyyy-MM-dd') } else { 'not reported' }
  "$($_.Name.Trim()) | driver $($_.DriverVersion) ($driver) | $ram | $($_.CurrentHorizontalResolution)x$($_.CurrentVerticalResolution)"
  })
  GpuNote = 'Integrated GPUs report a nominal dedicated allocation; total usable shared memory is not described by WMI.'
 }
}

function Get-WoodFrameTimes {
 # Reads one CSV Profiler capture and returns the FrameTime column in milliseconds.
 # The profiler appends summary rows after the frame rows, so capture stops at the first
 # non-numeric row. Frames with no sample in the column are dropped.
 param([Parameter(Mandatory=$true)][string]$Path)
 if (!(Test-Path -LiteralPath $Path)) { throw "CSV profiler output not found: $Path" }
 $times = New-Object 'System.Collections.Generic.List[double]'
 $column = -1
 foreach ($line in [IO.File]::ReadLines($Path)) {
  if ($column -lt 0) {
   $cells = $line.Split(',')
   for ($i = 0; $i -lt $cells.Count; $i++) {
    if ($cells[$i].Trim().Trim('"') -eq 'FrameTime') { $column = $i; break }
   }
   continue
  }
  $cells = $line.Split(',')
  if ($column -ge $cells.Count) { break }
  # The profiler appends 'Average'/'Maximum' summary rows after the frame rows; only rows
  # carrying a whole-number frame index in the first column are frame samples.
  $frame = 0.0
  if (![double]::TryParse($cells[0].Trim().Trim('"'), [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$frame)) { break }
  if ($frame -lt 0 -or $frame -ne [math]::Floor($frame)) { break }
  $value = $cells[$column].Trim().Trim('"')
  if (!$value) { continue }
  $sample = 0.0
  if (![double]::TryParse($value, [Globalization.NumberStyles]::Float, [Globalization.CultureInfo]::InvariantCulture, [ref]$sample)) { break }
  $times.Add($sample)
 }
 if (!$times.Count) { throw "CSV profiler capture has no FrameTime samples: $Path" }
 return $times.ToArray()
}

function Get-WoodPercentile {
 # Linear interpolation between nearest ranks, matching the usual percentile convention.
 param([double[]]$Sorted, [double]$Percent)
 if (!$Sorted -or $Sorted.Count -eq 0) { throw 'Percentile of an empty sample set' }
 if ($Percent -le 0) { return $Sorted[0] }
 if ($Percent -ge 100) { return $Sorted[$Sorted.Count - 1] }
 $position = ($Sorted.Count - 1) * ($Percent / 100.0)
 $lower = [math]::Floor($position)
 $upper = [math]::Ceiling($position)
 if ($lower -eq $upper) { return $Sorted[$lower] }
 return $Sorted[$lower] + ($Sorted[$upper] - $Sorted[$lower]) * ($position - $lower)
}

function New-WoodFrameSummary {
 param([double[]]$Times, [double]$Budget, [double]$Stall)
 $sorted = @($Times | Sort-Object)
 $stalls = @($sorted | Where-Object { $_ -gt $Stall })
 $breaches = @($sorted | Where-Object { $_ -gt $Budget })
 $total = 0.0
 foreach ($t in $sorted) { $total += $t }
 $mean = $total / $sorted.Count
 return [PSCustomObject]@{
  Samples = $sorted.Count
  MeanMs = [math]::Round($mean, 3)
  P50Ms = [math]::Round((Get-WoodPercentile $sorted 50), 3)
  P95Ms = [math]::Round((Get-WoodPercentile $sorted 95), 3)
  P99Ms = [math]::Round((Get-WoodPercentile $sorted 99), 3)
  MaxMs = [math]::Round($sorted[-1], 3)
  MeanFps = [math]::Round(1000.0 / $mean, 1)
  StallEvents = $stalls.Count
  StallWorstMs = if ($stalls.Count) { [math]::Round($stalls[-1], 3) } else { 0 }
  BudgetBreachFrames = $breaches.Count
 }
}

function Initialize-WoodInput {
 # Synthetic keyboard for the packaged client, so the fixed route can be walked without
 # adding console commands to the game module.
 if ('WoodInput' -as [type]) { return }
 Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class WoodInput {
 [StructLayout(LayoutKind.Sequential)] struct KeyEvent { public ushort VirtualKey; public ushort ScanCode; public uint Flags; public uint Time; public IntPtr Extra; }
 [StructLayout(LayoutKind.Sequential)] struct InputEvent { public uint Type; public KeyEvent Key; }
 [DllImport("user32.dll")] static extern uint SendInput(uint Count, InputEvent[] Events, int Size);
 [DllImport("user32.dll")] public static extern bool SetForegroundWindow(IntPtr Handle);
 [DllImport("user32.dll")] public static extern bool ShowWindow(IntPtr Handle, int Command);
 static void Send(KeyEvent Key) { InputEvent[] Events = new InputEvent[1]; Events[0].Type = 1; Events[0].Key = Key; SendInput(1, Events, Marshal.SizeOf(typeof(InputEvent))); }
 static KeyEvent Make(ushort VirtualKey, ushort ScanCode, uint Flags) { KeyEvent Key = new KeyEvent(); Key.VirtualKey = VirtualKey; Key.ScanCode = ScanCode; Key.Flags = Flags; Key.Time = 0; Key.Extra = IntPtr.Zero; return Key; }
 public static void Down(ushort VirtualKey) { Send(Make(VirtualKey, 0, 0)); }
 public static void Up(ushort VirtualKey) { Send(Make(VirtualKey, 0, 2)); }
 public static void Tap(ushort VirtualKey) { Send(Make(VirtualKey, 0, 0)); Send(Make(VirtualKey, 0, 2)); }
 public static void Text(string Value) {
  foreach (char Character in Value) {
   if (Character == ' ') { Tap(0x20); continue; }
   Send(Make(0, Character, 4));
   Send(Make(0, Character, 6));
  }
 }
}
'@
}

function Send-WoodConsoleCommand {
 param([Parameter(Mandatory=$true)][IntPtr]$Window, [Parameter(Mandatory=$true)][string]$Command)
 [WoodInput]::SetForegroundWindow($Window) | Out-Null
 [WoodInput]::Tap(0xC0)
 Start-Sleep -Milliseconds 250
 [WoodInput]::Text($Command)
 [WoodInput]::Tap(0x0D)
 Start-Sleep -Milliseconds 400
}

function Get-WoodProfileCapture {
 param([string[]]$Roots, [datetime]$After, [Parameter(Mandatory=$true)][string]$Label)
 $found = @()
 foreach ($root in $Roots) {
  if (!(Test-Path -LiteralPath $root)) { continue }
  $found += @(Get-ChildItem -LiteralPath $root -Recurse -Filter '*.csv' -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -GE $After })
 }
 if (!$found.Count) { throw "No CSV Profiler capture written for phase '$Label'. Confirm the engine build was compiled with CSV profiling enabled; see the phase log." }
 # Newest first: a capture can be flushed as an empty stub, so only return one that has samples.
 foreach ($candidate in @($found | Sort-Object LastWriteTime -Descending)) {
  try { $null = Get-WoodFrameTimes $candidate.FullName; return $candidate.FullName } catch { }
 }
 throw "CSV Profiler captures for phase '$Label' contain no frame samples: $($found[0].FullName)"
}

function Get-WoodScalability {
 param([string]$SearchRoot)
 $file = @(Get-ChildItem -LiteralPath $SearchRoot -Recurse -Filter 'Engine.ini' -File -ErrorAction SilentlyContinue | Where-Object { $_.FullName -match 'Saved[\\/]Config' } | Sort-Object LastWriteTime -Descending)[0]
 if (!$file) { return 'Scalability groups not written by this build; project defaults were in force.' }
 $values = [ordered]@{}
 $inGroup = $false
 foreach ($line in Get-Content -LiteralPath $file.FullName) {
  if ($line -match '^\s*\[(.+)\]') { $inGroup = ($Matches[1] -eq 'ScalabilityGroups'); continue }
  if ($inGroup -and $line -match '^\s*(sg\.[^=]+)=(.*)$') { $values[$Matches[1]] = $Matches[2] }
 }
 if (!$values.Count) { return 'No [ScalabilityGroups] entries recorded; project defaults were in force.' }
 return (($values.GetEnumerator() | ForEach-Object { "$($_.Key)=$($_.Value)" }) -join '; ')
}

if (!(Test-Path -LiteralPath $uat)) { throw "Unreal build tool not found at $uat" }
$engine = Get-WoodEngineVersion $EngineRoot
New-Item -ItemType Directory -Force -Path $runRoot | Out-Null

if (!$SkipBuild) {
 # BuildCookRun produces the packaged client; an editor build cannot certify the target.
 $packageLog = Join-Path $runRoot 'package.log'
 & $uat BuildCookRun -project="$project" -nop4 -utf8output -platform=Win64 "-clientconfig=$Configuration" -build -cook -stage -pak -package -archive "-archivedirectory=$packageRoot" "-abslog=$packageLog"
 if ($LASTEXITCODE -ne 0) { throw "Packaged build failed; see $packageLog" }
}
$client = @(Get-ChildItem -LiteralPath $packageRoot -Recurse -Filter 'TheWood.exe' -File -ErrorAction SilentlyContinue)[0]
if (!$client) { throw "Packaged client not found under $packageRoot" }

# The fixed acceptance route: named waypoints the client already exposes through WoodView,
# each walked forward for a fixed time so every phase covers the same ground.
$route = @(
 @{ Leg = 1; Waypoint = 'Forest'; Seconds = $PhaseSeconds }
 @{ Leg = 2; Waypoint = 'Stream'; Seconds = $PhaseSeconds }
 @{ Leg = 3; Waypoint = 'Ridge'; Seconds = $PhaseSeconds }
 @{ Leg = 4; Waypoint = 'Ruins'; Seconds = $PhaseSeconds }
)

$phases = @(
 @{ Name = 'steady'; Cold = $false; Captures = 0; Measures = 'steady-state walking, warm-up frames excluded' }
 @{ Name = 'realisation'; Cold = $true; Captures = 0; Measures = 'chunk realisation from a cold start' }
 @{ Name = 'capture'; Cold = $false; Captures = $PhotoCaptures; Measures = 'photography during warm walking' }
)
$results = @()
foreach ($phase in $phases) {
 $phaseRoot = Join-Path $runRoot $phase.Name
 $log = Join-Path $phaseRoot "$routeName.log"
 New-Item -ItemType Directory -Force -Path $phaseRoot | Out-Null
 $start = Get-Date
 # The realisation phase starts away from the route so the neighbourhood is generated in-window.
 $startX = if ($phase.Cold) { "$ColdStartX" } else { '0' }
 $startY = if ($phase.Cold) { "$ColdStartY" } else { '0' }
 $window = if ($Fullscreen) { '-fullscreen' } else { '-windowed' }
 $clientArgs = @(
  "-ResX=$Width", "-ResY=$Height", $window,
  '-nosplash', '-NoLoadingScreen', '-log',
  "-WoodSeed=$Seed", "-WoodStartX=$startX", "-WoodStartY=$startY",
  "-abslog=$log", '-stdout', '-FullStdOutLogOutput'
 )
 if ($Scalability.Count) { $clientArgs += "-ExecCmds=$($Scalability -join ',')" }
 $process = Start-Process -FilePath $client.FullName -ArgumentList $clientArgs -PassThru -RedirectStandardOutput (Join-Path $phaseRoot 'stdout.log') -RedirectStandardError (Join-Path $phaseRoot 'stderr.log')
 $deadline = (Get-Date).AddSeconds(120)
 $window0 = [IntPtr]::Zero
 while ((Get-Date) -lt $deadline) {
  Start-Sleep -Milliseconds 500
  $process.Refresh()
  if ($process.HasExited) { break }
  if ($process.MainWindowHandle -ne [IntPtr]::Zero) { $window0 = $process.MainWindowHandle; break }
 }
 if ($process.HasExited) { throw "Packaged client exited before the window appeared; see $log" }
 if ($window0 -eq [IntPtr]::Zero) { Stop-Process -Id $process.Id -Force; throw "Packaged client produced no window within 120s; see $log" }
 Initialize-WoodInput
 [WoodInput]::ShowWindow($window0, 9) | Out-Null

 Send-WoodConsoleCommand -Window $window0 -Command 'csvprofile start'
 foreach ($leg in $route) {
  Send-WoodConsoleCommand -Window $window0 -Command "WoodView $($leg.Waypoint)"
  [WoodInput]::Down(0x57)
  Start-Sleep -Seconds $leg.Seconds
  [WoodInput]::Up(0x57)
  if ($phase.Captures -gt 0) {
   $perLeg = [math]::Max(1, [int][math]::Ceiling($phase.Captures / $route.Count))
   for ($i = 0; $i -lt $perLeg; $i++) { Send-WoodConsoleCommand -Window $window0 -Command 'Photograph' }
  }
 }
 Send-WoodConsoleCommand -Window $window0 -Command 'csvprofile stop'
 # A packaged build resolves ProjectSavedDir to the staged directory, not the project Saved.
 $savedRoots = @((Join-Path $client.DirectoryName 'TheWood/Saved'), (Join-Path $client.DirectoryName 'Saved'), (Join-Path $taskRoot 'Saved'))
 $capture = $null
 $flush = (Get-Date).AddSeconds(30)
 while ((Get-Date) -lt $flush -and !$capture) {
  Start-Sleep -Milliseconds 500
  try { $capture = Get-WoodProfileCapture -Roots $savedRoots -After $start -Label $phase.Name } catch { $capture = $null }
 }
 Send-WoodConsoleCommand -Window $window0 -Command 'quit'
 if (!$process.WaitForExit(60000)) { Stop-Process -Id $process.Id -Force }
 if (!$capture) { throw "CSV Profiler capture for phase '$($phase.Name)' was never written; see $log" }

 if (!(Select-String -LiteralPath $log -Pattern 'Wood seed' -Quiet)) { throw "Packaged run '$($phase.Name)' produced no generated environment; see $log" }
 $times = Get-WoodFrameTimes $capture
 $warm = 0
 if ($phase.Name -eq 'steady') {
  # Drop the opening frames: the first streamed neighbourhood must not count as steady state.
  $warm = [int][math]::Ceiling($times.Count * 0.2)
  if ($warm -ge $times.Count) { throw "Steady-state run recorded only $($times.Count) frames; increase -PhaseSeconds" }
  $times = @($times[$warm..($times.Count - 1)])
 }
 $summary = New-WoodFrameSummary -Times $times -Budget $BudgetMs -Stall $StallThresholdMs
 # Photographs are written to Saved/Photos under the packaged build's own saved directory.
 $photos = @()
 foreach ($root in $savedRoots) {
  $album = Join-Path $root 'Photos'
  if (!(Test-Path -LiteralPath $album -ErrorAction SilentlyContinue)) { continue }
  $photos += @(Get-ChildItem -LiteralPath $album -Filter '*.png' -File -ErrorAction SilentlyContinue | Where-Object { $_.LastWriteTime -GE $start })
 }
 if ($phase.Captures -gt 0 -and $photos.Count -lt $phase.Captures) { throw "Photo capture phase wrote $($photos.Count) of $($phase.Captures) photographs; see $log" }
 $results += [PSCustomObject]@{
  Phase = $phase.Name
  Measures = $phase.Measures
  WarmupFramesExcluded = $warm
  Capture = $capture
  Photographs = $photos.Count
  Log = $log
  FrameTimes = $summary
 }
}

$report = [ordered]@{
 Route = $routeName
 GeneratedUtc = (Get-Date).ToUniversalTime().ToString('yyyy-MM-ddTHH:mm:ssZ')
 Engine = $engine
 Machine = Get-WoodMachineProfile
 Client = "$($client.FullName) ($Configuration)"
 Resolution = "$Width x $Height"
 WindowMode = if ($Fullscreen) { 'fullscreen' } else { 'windowed' }
 TargetFps = $TargetFps
 BudgetMs = $BudgetMs
 StallThresholdMs = $StallThresholdMs
 ScalabilityOverrides = $Scalability
 ScalabilityRecorded = Get-WoodScalability -SearchRoot $client.DirectoryName
 Seed = $Seed
 Phases = $results
}
$reportPath = Join-Path $runRoot 'profile.json'
$report | ConvertTo-Json -Depth 6 | Set-Content -Encoding utf8 $reportPath

$lines = @("# Packaged performance profile $routeName", '', "Client: $Configuration  $($client.FullName)", "Resolution: $Width x $Height $(if ($Fullscreen) { 'fullscreen' } else { 'windowed' })", "Engine: $($engine.MajorVersion).$($engine.MinorVersion).$($engine.PatchVersion) CL $($engine.Changelist)", "Budget: $BudgetMs ms (p95 target, $TargetFps fps)   Stall threshold: $StallThresholdMs ms", "Scalability: $($report.ScalabilityRecorded)", '')
$lines += '| Phase | Measures | Frames | p50 ms | p95 ms | p99 ms | max ms | mean fps | Stall events | Worst stall ms | Photos |'
$lines += '| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |'
foreach ($result in $results) {
 $f = $result.FrameTimes
 $lines += "| $($result.Phase) | $($result.Measures) | $($f.Samples) | $($f.P50Ms) | $($f.P95Ms) | $($f.P99Ms) | $($f.MaxMs) | $($f.MeanFps) | $($f.StallEvents) | $($f.StallWorstMs) | $($result.Photographs) |"
}
$lines += ''
# Addressed by name, not position, so a phase can never be silently mislabelled.
$byPhase = @{}
foreach ($result in $results) { $byPhase[$result.Phase] = $result }
foreach ($required in 'steady','realisation','capture') {
 if (!$byPhase.ContainsKey($required)) { throw "Phase '$required' produced no result; the profile is incomplete" }
}
$breached = @($results | Where-Object { $_.FrameTimes.P95Ms -gt $BudgetMs })
$lines += 'Average frame rate is not the acceptance signal. Generation and photography stalls are counted per phase, separated from steady state.'
$lines += "Steady state excludes $($byPhase['steady'].WarmupFramesExcluded) opening frames."
$lines += "Chunk realisation stalls: $($byPhase['realisation'].FrameTimes.StallEvents) events over $($byPhase['realisation'].FrameTimes.Samples) frames, worst $($byPhase['realisation'].FrameTimes.StallWorstMs) ms."
$lines += "Photo capture stalls: $($byPhase['capture'].FrameTimes.StallEvents) events over $($byPhase['capture'].FrameTimes.Samples) frames across $($byPhase['capture'].Photographs) photographs, worst $($byPhase['capture'].FrameTimes.StallWorstMs) ms."
if ($breached.Count) {
 $lines += "RESULT: FAIL - p95 over budget in $($breached.Count) phase(s): $(($breached | ForEach-Object { $_.Phase }) -join ', ')"
} else {
 $lines += "RESULT: PASS - every phase held p95 within $BudgetMs ms. Confirm the recorded machine is the certified mainstream gaming baseline before accepting."
}
$summaryPath = Join-Path $runRoot 'summary.md'
Set-Content -Encoding utf8 $summaryPath $lines
$lines | Write-Output
Write-Output $reportPath
if ($Strict -and $breached.Count) { throw "Performance profile failed: $($reportPath)" }