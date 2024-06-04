#Persistent
SetTitleMatchMode, 2

Loop
{
    ; Activate the qBittorrent window
    IfWinExist, qBittorrent
    {
        ; Make the qBittorrent window active
        WinActivate
        ; Send Ctrl+Q to qBittorrent
        Send, ^q
    }
    
    ; Wait for 15 seconds
    Sleep, 15000
    
    ; Start qBittorrent
    Run, C:\Program Files\qBittorrent\qbittorrent.exe
    
    ; Wait for 5 minutes
    Sleep, 300000
}
