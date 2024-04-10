@echo off
setlocal enabledelayedexpansion

rem Set the directory containing your Python scripts (current directory)
set "scripts_dir=%CD%"

rem Loop through all .py files in the directory
for %%i in ("%scripts_dir%\*.py") do (
    echo Processing: %%i
    pyinstaller --noconfirm --onefile --console "%%i"
)

pause
