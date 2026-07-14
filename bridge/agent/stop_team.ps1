# stop_team.ps1 — stop ALL employee/companion BRAIN processes. The in-game characters are LEFT
# ALIVE on purpose so they keep their inventory (JJ-delivered items); a relaunched BRAIN
# reuses the same named character. (Do NOT destroy/remove chars here -> that loses items.)
#
# CRITICAL: on this box Python runs as `python3.13.exe`, NOT `python.exe`. Matching only
# 'python.exe' silently misses every brain (that let a runaway pile up unkillable on 2026-07-13).
# We match on the COMMAND LINE, across any python*/pwsh host, and exclude our own shell ($PID).
$self = $PID
$pat  = 'companion' + '_brain|bridge.agent|launch_team'   # split literal so this script won't self-match
$targets = Get-CimInstance Win32_Process | Where-Object {
  $_.ProcessId -ne $self -and
  ($_.Name -like 'python*' -or $_.Name -eq 'powershell.exe' -or $_.Name -eq 'pwsh.exe') -and
  $_.CommandLine -match $pat
}
foreach ($p in $targets) {
  try { Stop-Process -Id $p.ProcessId -Force -ErrorAction Stop; Write-Output "stopped $($p.Name) pid $($p.ProcessId)" } catch {}
}
Start-Sleep -Milliseconds 600
$left = @(Get-CimInstance Win32_Process | Where-Object {
  $_.ProcessId -ne $self -and $_.Name -like 'python*' -and $_.CommandLine -match $pat }).Count
Write-Output "done ($(@($targets).Count) killed, $left still alive; characters + their items kept)."
