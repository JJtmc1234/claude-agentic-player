# stop_team.ps1 — stop the employee BRAIN processes ONLY. The in-game characters are LEFT
# ALIVE on purpose so they keep their inventory (JJ-delivered items); a relaunched BRAIN
# reuses the same named character. (Do NOT destroy/remove chars here -> that loses items.)
Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
  Where-Object { $_.CommandLine -like '*companion_brain*' } |
  ForEach-Object { Stop-Process -Id $_.ProcessId -Force; Write-Output "stopped BRAIN pid $($_.ProcessId)" }
Write-Output "done (processes killed; characters + their items kept)."
