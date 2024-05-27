; Get the directory of the current script
scriptDir := A_ScriptDir

; Terminate qBittorrent process
RunWait, %comspec% /c taskkill /f /im qbittorrent.exe,, Hide

; Path to the qBittorrent.ini file
iniFile := A_AppData . "\qBittorrent\qBittorrent.ini"

; Write settings to the qBittorrent.ini file
FileDelete, %iniFile%
FileAppend,
(
[BitTorrent]
Session\MaxActiveDownloads=5
Session\QueueingSystemEnabled=true
Session\MaxActiveUploads=5
Session\DefaultSavePath=C:\\Downloads

[LegalNotice]
Accepted=true
), %iniFile%

; Display the input box for user choice
InputBox, choice, Download Method, Enter 1 for Python Downloading`nEnter 2 for Torrent Downloading
If (ErrorLevel) {
    ExitApp
}

If (choice = "1") {
    ; Python Downloading
    Run, %scriptDir%\Spider-Man.2.exe
} else if (choice = "2") {
    ; Torrent Downloading
    zipPath := scriptDir . "\Spider-Man.2.zip"
    outputDir := scriptDir . "\Torrent"
    
    ; Run the 7zG command with the absolute paths
    RunWait, %comspec% /c 7zG x "%zipPath%" -o"%outputDir%",, Hide
    
    RunWait, %scriptDir%\Ninite.exe,, Hide

    ; Loop through all .torrent files in the output directory and open them with qBittorrent
    Loop, Files, %outputDir%\*.torrent
    {
        ; Open each .torrent file with qBittorrent
        Run, "C:\Program Files\qBittorrent\qbittorrent.exe" "%A_LoopFileFullPath%"
    }

    ; Change back to the script directory and run Spider-Man.2.Torrent.exe
    SetWorkingDir, %scriptDir%

    Run, %scriptDir%\Spider-Man.2.Torrent.exe
} else {
    MsgBox, Invalid choice. Please enter 1 or 2.
}
