@echo off
setlocal
set "TASK_ROOT=%~dp0.."
set "TASK_VS=C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools"
call "%TASK_VS%\Common7\Tools\VsDevCmd.bat" -arch=x64 -host_arch=x64
if errorlevel 1 exit /b 1
if not exist "%TASK_ROOT%\.cache\tests" mkdir "%TASK_ROOT%\.cache\tests"
cl /nologo /std:c++17 /EHsc /W4 /WX /I"%TASK_ROOT%\Source\TheWood\Public" "%TASK_ROOT%\Source\TheWood\Private\Generation\WoodSoundscape.cpp" "%TASK_ROOT%\Tests\SoundscapeTests.cpp" /Fo"%TASK_ROOT%\.cache\tests\\" /Fe"%TASK_ROOT%\.cache\tests\soundscape-msvc.exe"
if errorlevel 1 exit /b 1
"%TASK_ROOT%\.cache\tests\soundscape-msvc.exe"
exit /b %errorlevel%
