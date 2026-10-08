$ErrorActionPreference = 'Stop'
$taskRoot = Split-Path $PSScriptRoot -Parent
$compiler = Join-Path $taskRoot '.cache/toolchain/ziglang/zig.exe'
if (!(Test-Path -LiteralPath $compiler)) { throw 'Install the test compiler: python -m pip install --target .cache/toolchain ziglang==0.13.0' }
$outputDir = Join-Path $taskRoot '.cache/tests'
New-Item -ItemType Directory -Force -Path $outputDir | Out-Null
$exe = Join-Path $outputDir 'generation-tests.exe'
& $compiler c++ -std=c++17 -Wall -Wextra -Werror -I "$taskRoot/Source/TheWood/Public" "$taskRoot/Source/TheWood/Private/Generation/WoodGeneration.cpp" "$taskRoot/Source/TheWood/Private/Generation/WoodDiscovery.cpp" "$taskRoot/Source/TheWood/Private/Generation/WoodEntrance.cpp" "$taskRoot/Tests/GenerationTests.cpp" -o $exe
if ($LASTEXITCODE -ne 0) { throw 'C++ test compilation failed' }
& $exe
if ($LASTEXITCODE -ne 0) { throw 'Generation tests failed' }
