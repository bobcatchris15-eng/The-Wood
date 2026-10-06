@echo off
setlocal
set "TASK_EDITOR=C:\Program Files\Epic Games\UE_5.8\Engine\Binaries\Win64\UnrealEditor.exe"
if not exist "%TASK_EDITOR%" (
 echo Unreal Engine 5.8 was not found at the recorded installation path.
 exit /b 1
)
start "The Wood" "%TASK_EDITOR%" "%~dp0..\TheWood.uproject" /Game/Maps/VisualBenchmark -game -windowed -ResX=1920 -ResY=1080
