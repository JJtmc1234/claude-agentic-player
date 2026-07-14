# launch_team.ps1 — PARKED (2026-07-13). The 4-employee team is DISABLED.
#
# JJ said "just have the one" and "done playing" after a runaway on 2026-07-13 where repeated
# team launches piled up ~30 brain processes (invisible to the old python.exe-only killers) that
# spawned dozens of characters and carpeted the district with belts. Until the team behavior is
# re-hardened (self-serve grab, no belt-spam, verified stable), single-companion mode is the
# supported path.
#
# To run the teammate:   ./bridge/agent/launch_one.ps1
#
# The old 4-employee logic is preserved in git history (and each brain is now singleton-guarded
# + spawn-capped), but launching it is intentionally blocked here to prevent accidental re-runs.

Write-Output "launch_team.ps1 is PARKED. Use ./bridge/agent/launch_one.ps1 for the single companion."
Write-Output "(4-employee mode disabled on 2026-07-13 after the runaway; re-enable deliberately.)"
exit 0
