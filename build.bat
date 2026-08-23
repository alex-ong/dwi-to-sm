@echo off
setlocal

uv sync

set PYINSTALLER_ARGS=--noconfirm --clean --distpath dist --workpath build
set DO_ZIP=0

for %%A in (%*) do (
    if /i "%%A"=="zip" set DO_ZIP=1
)

uv run pyinstaller main.spec %PYINSTALLER_ARGS%
if errorlevel 1 exit /b %errorlevel%

if %DO_ZIP%==1 (
    pwsh -NoProfile -Command "$name = 'dist\dwi-to-sm-' + (Get-Date -Format yyyyMMdd-HHmmss) + '.zip'; Compress-Archive -Path 'dist\dwi-to-sm.exe' -DestinationPath $name -Force; Write-Host ('Created ' + $name)"
)

endlocal