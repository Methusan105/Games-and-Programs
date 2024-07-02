@echo off
setlocal enabledelayedexpansion

for /L %%i in (1,1,31) do (
    set "url=https://github.com/Methusan105/Games-and-Programs/releases/download/HZD/Horizon.Zero.Dawn-%%i.bin"
    "C:\Program Files (x86)\Internet Download Manager\IDMan.exe" /a /d "!url!" from -%%i.bin to -%%i.bin
)

endlocal