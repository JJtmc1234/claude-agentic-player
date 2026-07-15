# launch_classic_team.ps1 — start the 4 CLASSIC agentic-team BRAINs, each driving its own
# named character with a whole-map role (miner / courier / builder / scout). Unlike the K2
# district team (launch_team.ps1, parked), these are general JJ-centric companions that work
# alongside JJ across the whole map — the original agentic-team roles.
#
# Each is a full companion_brain: obeys JJ, coordinates via the team blackboard
# (bridge/agent/team_status/), specializes on its role when JJ isn't directing. Every brain is
# singleton-guarded (per-name mutex) + spawn-rate-limited, so 4 distinct names run safely.
#
# Prereqs: game hosted + claude-companion mod ENABLED. A brain WAITS for the game if it's down.
#   ./bridge/agent/launch_classic_team.ps1
# NOTE: 4 Opus-driven loops -> ~4x the API cost of one. Stop with ./bridge/agent/stop_team.ps1
# (kills brains, keeps characters + their items).

$env:ANTHROPIC_API_KEY = [Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')
$dir = "C:\Users\pmarc\OneDrive\Desktop\Projects\Claude Agentic Player"
Set-Location $dir

# Clean slate first: kill the single companion + any strays so we truly start just these 4.
& "$dir\bridge\agent\cleanup_python.ps1" -All | Out-Null

# Classic whole-map roles (no --district; they work alongside JJ everywhere).
$team = @(
  @{ name = 'miner';   role = 'RESOURCE LEAD: mine ore/coal/stone and place mining drills; keep smelting fed and raw resources flowing to the base. Chase the tightest raw input.' },
  @{ name = 'courier'; role = 'LOGISTICS: craft intermediates (gears, cables, circuits, belts, inserters), haul items between machines, and keep science/assemblers fed. Deliver what teammates need.' },
  @{ name = 'builder'; role = 'INFRA LEAD: build power (offshore-pump -> boiler -> steam or better), smelting furnaces, and assembler lines; physically build and expand the base as materials allow.' },
  @{ name = 'scout';   role = 'SCOUT/FLEX: explore and chart the map, find and report resource patches, watch for threats, and flex to help whichever teammate is behind.' }
)

foreach ($e in $team) {
  $a = "bridge/agent/companion_brain.py --name $($e.name) --role `"$($e.role)`""
  Start-Process python -ArgumentList $a -WorkingDirectory $dir -WindowStyle Minimized
  Write-Output "launched BRAIN: $($e.name)"
  Start-Sleep -Milliseconds 800
}
Write-Output "All 4 classic-team BRAINs launched (miner, courier, builder, scout). They coordinate via bridge/agent/team_status/."
