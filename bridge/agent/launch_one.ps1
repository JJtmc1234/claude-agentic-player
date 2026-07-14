# launch_one.ps1 — run ONE companion BRAIN (JJ's teammate). This is the default mode:
# "just have the one" (JJ, 2026-07-13). It first clears any stray brains, then launches a
# single companion in the background. The brain's named-mutex singleton guarantees only one
# 'companion' can run even if this is invoked twice.
#
#   ./bridge/agent/launch_one.ps1
# Stop it with:  ./bridge/agent/stop_team.ps1   (kills brains, keeps the character + items)

$env:ANTHROPIC_API_KEY = [Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')
$dir = "C:\Users\pmarc\OneDrive\Desktop\Projects\Claude Agentic Player"
Set-Location $dir

# clear any strays first so we truly have just the one
& "$dir\bridge\agent\cleanup_python.ps1" -All | Out-Null

# single general teammate: no --district (works the whole map alongside JJ), name 'companion'
Start-Process python -ArgumentList "bridge/agent/companion_brain.py --name companion" `
  -WorkingDirectory $dir -WindowStyle Minimized
Write-Output "launched ONE companion BRAIN (singleton-guarded). It waits for the game if it's down."
