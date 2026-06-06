#requires -Version 5.1
<#
.SYNOPSIS
Restart the Factorio server with the latest companion mod deployed +
(if new) published to the mod portal.

.DESCRIPTION
One-stop script for the "restart with new mod" workflow:
  1. If a factorio.exe is running, ask it to save (RCON /silent-command),
     then stop it gracefully.
  2. Run mod/deploy.ps1 to rebuild the zip into C:\FactorioServer\mods\
     and mod/dist/.
  3. Run mod/publish.py to upload to the mod portal. If the version is
     already on the portal, publish.py exits non-zero with a 400 — we
     swallow that and continue.
  4. Start the server via start-server.bat.
  5. Poll RCON until it answers (or 45s timeout).
  6. Print a one-line summary.

.PARAMETER SkipSave
Don't save the running game first (use when the server is already crashed).

.PARAMETER SkipPublish
Don't try to publish to the mod portal (use when you're offline or
just want a local restart).

.EXAMPLE
.\server\restart.ps1
.\server\restart.ps1 -SkipPublish

.NOTES
The RCON password is read from C:\FactorioServer\start-server.bat so we
don't have to duplicate it. If you change the password, update both.
#>
param(
  [switch]$SkipSave,
  [switch]$SkipPublish
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$rconPwd = (Select-String -Path "C:\FactorioServer\start-server.bat" `
  -Pattern '--rcon-password "([^"]+)"').Matches[0].Groups[1].Value

function Send-ChatWarning {
  [CmdletBinding()]
  param([string]$Message)
  $proc = Get-CimInstance Win32_Process -Filter "Name='factorio.exe'" -ErrorAction SilentlyContinue
  if (-not $proc) { return }
  $env:FACTORIO_RCON_PASSWORD = $rconPwd
  try {
    & python (Join-Path $repoRoot "bridge\say.py") $Message | Out-Null
  } catch {
    # Best-effort; don't fail the restart on a chat hiccup.
  }
}

function Save-IfRunning {
  $proc = Get-CimInstance Win32_Process -Filter "Name='factorio.exe'" -ErrorAction SilentlyContinue
  if (-not $proc) { Write-Output "[restart] no running factorio.exe to save"; return $false }
  Write-Output "[restart] saving running server (PID $($proc.ProcessId)) ..."
  $env:FACTORIO_RCON_PASSWORD = $rconPwd
  try {
    # Save to 'server' name. Factorio writes to its own data dir
    # (%APPDATA%\Roaming\Factorio\saves\server.zip), NOT the path we pass
    # to --start-server. We then copy it over so the start-server reload
    # actually gets the latest state. Without this copy, every restart
    # loads from an old server.zip.
    & python (Join-Path $repoRoot "bridge\_exec.py") "game.server_save('server') rcon.print('saved')" | Out-Null
    Start-Sleep -Seconds 2  # let factorio finish writing
    $srcSave = "C:\Users\pmarc\AppData\Roaming\Factorio\saves\server.zip"
    $dstSave = "C:\FactorioServer\saves\server.zip"
    if (Test-Path $srcSave) {
      Copy-Item $srcSave $dstSave -Force -ErrorAction SilentlyContinue
      Write-Output "[restart] save OK -> copied $srcSave -> $dstSave"
    } else {
      Write-Output "[restart] WARNING: src save not found at $srcSave"
    }
  } catch {
    Write-Output "[restart] save command errored (continuing anyway): $_"
  }
  return $true
}

function Stop-Factorio {
  $proc = Get-CimInstance Win32_Process -Filter "Name='factorio.exe'" -ErrorAction SilentlyContinue
  if (-not $proc) { return }
  $parentId = $proc.ParentProcessId
  Stop-Process -Id $proc.ProcessId -Force
  Write-Output "[restart] stopped factorio PID $($proc.ProcessId)"
  Start-Sleep -Milliseconds 600
  $parent = Get-CimInstance Win32_Process -Filter "ProcessId=$parentId" -ErrorAction SilentlyContinue
  if ($parent -and $parent.Name -eq 'cmd.exe') {
    Stop-Process -Id $parentId -Force -ErrorAction SilentlyContinue
    Write-Output "[restart] closed parent cmd.exe PID $parentId"
  }
}

function Install-Mod {
  $deployScript = Join-Path $repoRoot "mod\deploy.ps1"
  Write-Output "[restart] deploying mod ..."
  & $deployScript
  if ($LASTEXITCODE -ne 0) { throw "deploy.ps1 failed (exit $LASTEXITCODE)" }
}

function Publish-Mod {
  if ($SkipPublish) { Write-Output "[restart] skipping publish (-SkipPublish)"; return }
  $pub = Join-Path $repoRoot "mod\publish.py"
  Write-Output "[restart] publishing to mod portal ..."
  # Wrap in try/catch and temporary ErrorActionPreference change because
  # PowerShell's ErrorActionPreference=Stop treats native exe stderr as a
  # terminating error even when we check $LASTEXITCODE.
  $prev = $ErrorActionPreference
  $ErrorActionPreference = "Continue"
  try {
    $output = & python $pub 2>&1
  } catch {
    $output = $_.Exception.Message
  }
  $ErrorActionPreference = $prev
  if ($LASTEXITCODE -eq 0) {
    Write-Output "[restart] publish OK"
  } else {
    $tail = ($output | Select-Object -Last 4) -join "`n"
    Write-Output "[restart] publish returned exit $LASTEXITCODE (continuing). tail:`n$tail"
  }
}

function Start-Server {
  $bat = "C:\FactorioServer\start-server.bat"
  if (-not (Test-Path $bat)) { throw "$bat not found" }
  Start-Process -FilePath $bat
  Write-Output "[restart] launched $bat"
}

function Wait-ForRcon {
  param([int]$TimeoutSec = 45)
  $deadline = (Get-Date).AddSeconds($TimeoutSec)
  while ((Get-Date) -lt $deadline) {
    try {
      $tcp = New-Object System.Net.Sockets.TcpClient
      $tcp.Connect("127.0.0.1", 27015)
      $tcp.Close()
      Write-Output "[restart] RCON up"
      return $true
    } catch { Start-Sleep -Milliseconds 500 }
  }
  Write-Output "[restart] RCON TIMEOUT after ${TimeoutSec}s"
  return $false
}

# ---- main ----
Send-ChatWarning "Server restarting in 5s to deploy latest mod. Reconnect after."
Start-Sleep -Seconds 5
if (-not $SkipSave) { Save-IfRunning | Out-Null }
Stop-Factorio
Install-Mod
Publish-Mod
Start-Server
$ok = Wait-ForRcon
if ($ok) {
  $env:FACTORIO_RCON_PASSWORD = $rconPwd
  $ping = & python (Join-Path $repoRoot "bridge\_exec.py") `
    "rcon.print(helpers.table_to_json(remote.call('claude','ping')))"
  Write-Output "[restart] mod ping: $ping"
} else {
  Write-Output "[restart] server not responding via RCON; check the .bat window"
  exit 1
}
