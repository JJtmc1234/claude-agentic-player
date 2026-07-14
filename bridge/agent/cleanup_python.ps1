# cleanup_python.ps1 — kill leftover / duplicate / dead Project-BRAIN python processes.
#
# Keeps ONE companion_brain process per employee (--name), kills duplicates + any orphan
# companion_brain with no name, and clears hung one-off _exec.py probes. Safe to run anytime.
#   ./bridge/agent/cleanup_python.ps1            # de-dupe: keep one brain per employee
#   ./bridge/agent/cleanup_python.ps1 -All       # kill ALL project python (full stop)

param([switch]$All)

$py = Get-CimInstance Win32_Process -Filter "Name='python.exe' OR Name='pythonw.exe'"

if ($All) {
  $targets = $py | Where-Object { $_.CommandLine -like '*companion_brain*' -or $_.CommandLine -like '*bridge*' }
  foreach ($p in $targets) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }
  Write-Output ("killed ALL " + $targets.Count + " project python process(es).")
  return
}

# 1) de-dupe brains: keep the NEWEST process per --name, kill the rest (+ any un-named brain)
$brains = $py | Where-Object { $_.CommandLine -like '*companion_brain*' }
$seen = @{}
$killed = 0
foreach ($p in ($brains | Sort-Object CreationDate -Descending)) {
  $name = if ($p.CommandLine -match '--name\s+(\S+)') { $matches[1] } else { $null }
  if (-not $name -or $seen.ContainsKey($name)) {
    Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue
    $killed++
  } else {
    $seen[$name] = $p.ProcessId
  }
}

# 2) kill stray one-off probes that somehow lingered (these are meant to be instant)
$stray = $py | Where-Object { $_.CommandLine -like '*_exec.py*' }
foreach ($p in $stray) { Stop-Process -Id $p.ProcessId -Force -ErrorAction SilentlyContinue }

Write-Output ("kept brains: " + (($seen.Keys | Sort-Object) -join ', '))
Write-Output ("killed " + $killed + " duplicate/orphan brain(s), " + $stray.Count + " stray probe(s).")
