param([int]$Seed=12345,[ValidateSet('Forest','Stream','Ridge','Grassland','Taiga','Highlands','Roots','Ruins')][string]$View='Forest',[double]$Time=0)
$ErrorActionPreference='Stop'
$taskRoot=Split-Path $PSScriptRoot -Parent
$editor='C:/Program Files/Epic Games/UE_5.8/Engine/Binaries/Win64/UnrealEditor-Cmd.exe'
$review=Join-Path $taskRoot 'Saved/Review'
New-Item -ItemType Directory -Force -Path $review | Out-Null
$startX=-180;$startY=-180
$frame=@(); if($View -eq 'Ruins') { $frame=@('-WoodFrameRuin') }
if($View -in 'Grassland','Taiga','Highlands') { $frame=@("-WoodFrameBiome=$View") }
$start=Get-Date
$name="${Seed}-${View}-${Time}"
$log=Join-Path $review "$name.log"
& $editor "$taskRoot/TheWood.uproject" /Game/Maps/VisualBenchmark -game -RenderOffscreen -unattended -nosplash -windowed -WoodFresh -ResX=1280 -ResY=720 "-WoodSeed=$Seed" "-WoodTime=$Time" "-WoodStartX=$startX" "-WoodStartY=$startY" @frame '-ini:Engine:[DevOptions.Shaders]:bAllowAsynchronousShaderCompiling=False' "-ExecCmds=WoodCapture $View 2" -benchmark -seconds=4 "-abslog=$log" *> (Join-Path $review "$name-output.log")
if($LASTEXITCODE -ne 0) { throw "Review render failed: $log" }
$photo=Get-ChildItem -LiteralPath "$taskRoot/Saved/Photos" -Filter '*.png' | Where-Object LastWriteTime -GE $start | Sort-Object LastWriteTime -Descending | Select-Object -First 1
if(!$photo) { throw "No photograph generated: $log" }
$target=Join-Path $review "$name.png"
Copy-Item -LiteralPath $photo.FullName -Destination $target
Write-Output $target
