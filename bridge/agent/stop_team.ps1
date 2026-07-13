# stop_team.ps1 — stop all running employee BRAINs (companion_brain instances).
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*companion_brain*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Output "stopped BRAIN pid $($_.ProcessId)" }
Write-Output "done."
