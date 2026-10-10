@echo off
setlocal enabledelayedexpansion

set "SCRIPT_DIR=%~dp0"
set "REPO_ROOT=%SCRIPT_DIR%.."
pushd "%REPO_ROOT%"

REM Check if cl.exe is already available in PATH
where cl >nul 2>&1
if %ERRORLEVEL% EQU 0 goto COMPILE_MSVC

REM Attempt to locate vcvars64.bat using vswhere
set "VSWHERE=%ProgramFiles(x86)%\Microsoft Visual Studio\Installer\vswhere.exe"
if not exist "!VSWHERE!" (
    set "VSWHERE=%ProgramFiles%\Microsoft Visual Studio\Installer\vswhere.exe"
)

if exist "!VSWHERE!" (
    for /f "usebackq tokens=*" %%i in (`"!VSWHERE!" -latest -products * -requires Microsoft.VisualStudio.Component.VC.Tools.x86.x64 -property installationPath`) do (
        set "VS_DIR=%%i"
    )
)

if defined VS_DIR (
    if exist "!VS_DIR!\VC\Auxiliary\Build\vcvars64.bat" (
        call "!VS_DIR!\VC\Auxiliary\Build\vcvars64.bat" >nul
        goto CHECK_CL
    )
)

REM Fallback well-known paths
if exist "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files (x86)\Microsoft Visual Studio\2022\BuildTools\VC\Auxiliary\Build\vcvars64.bat" >nul
    goto CHECK_CL
)

if exist "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Community\VC\Auxiliary\Build\vcvars64.bat" >nul
    goto CHECK_CL
)

if exist "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Professional\VC\Auxiliary\Build\vcvars64.bat" >nul
    goto CHECK_CL
)

if exist "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat" (
    call "C:\Program Files\Microsoft Visual Studio\2022\Enterprise\VC\Auxiliary\Build\vcvars64.bat" >nul
    goto CHECK_CL
)

:CHECK_CL
where cl >nul 2>&1
if %ERRORLEVEL% EQU 0 goto COMPILE_MSVC

REM Check for Zig fallback
where zig >nul 2>&1
if %ERRORLEVEL% EQU 0 goto COMPILE_ZIG

echo [ERROR] Neither MSVC cl.exe nor Zig C++ could be found.
popd
exit /b 1

:COMPILE_MSVC
if not exist "Binaries" mkdir "Binaries"
echo Compiling LandmarkTests with MSVC (/W4 /O2)...
cl /nologo /O2 /std:c++17 /W4 /O2 /EHsc /I "Source\TheWood\Public" /I "Source\TheWood\Public\Generation" "Source\TheWood\Private\Generation\WoodLandmarks.cpp" "Source\TheWood\Private\Generation\WoodGeneration.cpp" "Source\TheWood\Private\Generation\WoodDiscovery.cpp" "Source\TheWood\Private\Generation\WoodEntrance.cpp" "Tests\LandmarkTests.cpp" /Fe:"Binaries\LandmarkTests.exe" /Fo:"Binaries\\"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Compilation failed.
    popd
    exit /b %ERRORLEVEL%
)
goto RUN_TESTS

:COMPILE_ZIG
if not exist "Binaries" mkdir "Binaries"
echo Compiling LandmarkTests with Zig C++ (-Wall -Wextra -Werror -O2)...
zig c++ -std=c++17 -O2 -Wall -Wextra -Werror -I "Source/TheWood/Public" -I "Source/TheWood/Public/Generation" "Source/TheWood/Private/Generation/WoodLandmarks.cpp" "Source/TheWood/Private/Generation/WoodGeneration.cpp" "Source/TheWood/Private/Generation/WoodDiscovery.cpp" "Source/TheWood/Private/Generation/WoodEntrance.cpp" "Tests/LandmarkTests.cpp" -o "Binaries/LandmarkTests.exe"
if %ERRORLEVEL% NEQ 0 (
    echo [ERROR] Compilation failed.
    popd
    exit /b %ERRORLEVEL%
)
goto RUN_TESTS

:RUN_TESTS
echo Running LandmarkTests.exe...
"Binaries\LandmarkTests.exe"
set "TEST_EXIT=!ERRORLEVEL!"
popd
exit /b !TEST_EXIT!
