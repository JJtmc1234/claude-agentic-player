# launch_team.ps1 — start the 4 "employee" BRAINs, each driving its own character with a role.
# Each is a full JJ-centric companion_brain: obeys JJ, coordinates via the team blackboard
# (bridge/agent/team_status/), specializes on its role when JJ isn't directing.
#
# Prereqs: game hosted + claude-companion mod ENABLED. Run:  ./bridge/agent/launch_team.ps1
# NOTE: this runs 4 Opus-driven loops -> ~4x the API cost of one. Stop with stop_team.ps1
# (or close the windows).

$env:ANTHROPIC_API_KEY = [Environment]::GetEnvironmentVariable('ANTHROPIC_API_KEY','User')
$dir = "C:\Users\pmarc\OneDrive\Desktop\Projects\Claude Agentic Player"
Set-Location $dir

# K2SE, NO enemies -> no defender role. Use the modpack's real recipes/entities (query live).
$team = @(
  @{ name = 'miner';    role = 'Mine and haul raw resources and keep supply chests stocked for the team (use the modpack''s actual ores/drills).' },
  @{ name = 'smelter';  role = 'Smelt ore into plates: build + fuel + feed the modpack''s furnaces, keep the plate supply full.' },
  @{ name = 'builder';  role = 'Build and expand the base: power, assemblers, labs, belts, and a mall (clean + organized).' },
  @{ name = 'engineer'; role = 'Advanced production + science: circuits, K2 mid-game chains, science packs, and driving research up the tech tree.' }
)

foreach ($e in $team) {
  $args = "bridge/agent/companion_brain.py --name $($e.name) --role `"$($e.role)`""
  Start-Process python -ArgumentList $args -WorkingDirectory $dir -WindowStyle Minimized
  Write-Output "launched BRAIN: $($e.name)  ($($e.role))"
  Start-Sleep -Milliseconds 800
}
Write-Output "All 4 employee BRAINs launched. They coordinate via bridge/agent/team_status/."
