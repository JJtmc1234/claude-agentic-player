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

# K2 Spaced Out, NO enemies. Employees work INSIDE the 96x96 sandbox district; they build
# there, request resources from outside, and never touch JJ's base. Use REAL K2 recipes.
$district = "127,-225,224,-128"
$team = @(
  @{ name = 'e1'; role = 'STEEL: 2 coke furnaces (6 wood + 6 coal -> kr-coke) feeding 6 steel furnaces (2 kr-coke + 10 iron-plate -> steel). Request wood, coal, iron-plate. Send steel to a chest at the district edge for JJ.' },
  @{ name = 'e2'; role = 'INTERMEDIATES: assemblers for iron-stick, iron-gear-wheel, copper-cable, electronic-circuit, kr-automation-core, kr-blank-tech-card. Request iron-plate + copper-plate.' },
  @{ name = 'e3'; role = 'SCIENCE: assemble automation-science-pack (1 kr-automation-core + 5 kr-blank-tech-card) and logistic science; belt them to a lab feed. Wire internal belts/inserters.' },
  @{ name = 'e4'; role = 'SUPPORT/MALL: build a small mall (gears, cable, inserters, belts, assemblers) for the team and fix the current bottleneck. Keep the district clean + organized.' }
)

foreach ($e in $team) {
  $a = "bridge/agent/companion_brain.py --name $($e.name) --role `"$($e.role)`" --district `"$district`""
  Start-Process python -ArgumentList $a -WorkingDirectory $dir -WindowStyle Minimized
  Write-Output "launched BRAIN: $($e.name)  ($($e.role))"
  Start-Sleep -Milliseconds 800
}
Write-Output "All 4 employee BRAINs launched. They coordinate via bridge/agent/team_status/."
