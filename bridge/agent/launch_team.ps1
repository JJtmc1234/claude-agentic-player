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

$team = @(
  @{ name = 'miner';   role = 'Mine and haul raw resources (iron, copper, coal, stone / rocks) and keep supply chests stocked for the team.' },
  @{ name = 'smelter'; role = 'Smelt ore into iron/copper plates: build and feed burner furnaces, keep them fueled, bank plates.' },
  @{ name = 'builder'; role = 'Build and expand the base: power (pump/boilers/engines/poles), assemblers, labs, belts, and a mall.' },
  @{ name = 'gunner';  role = 'Defense: stay armed and equipped, kill biters, wall the base, and protect JJ and the other workers.' }
)

foreach ($e in $team) {
  $args = "bridge/agent/companion_brain.py --name $($e.name) --role `"$($e.role)`""
  Start-Process python -ArgumentList $args -WorkingDirectory $dir -WindowStyle Minimized
  Write-Output "launched BRAIN: $($e.name)  ($($e.role))"
  Start-Sleep -Milliseconds 800
}
Write-Output "All 4 employee BRAINs launched. They coordinate via bridge/agent/team_status/."
