@echo off
setlocal enabledelayedexpansion

for /L %%i in (1,1,28) do (
    set "url=https://github.com/Methusan105/Games-and-Programs/releases/download/GOT/Ghost.of.Tsushima.Director.s.Cut.zip.%%03d"
    set "number=00%%i"
    set "number=!number:~-3!"
    set "url=!url:%%03d=!number!"
    "C:\Program Files (x86)\Internet Download Manager\IDMan.exe" /a /d "!url!"
)

endlocal
