# Configurator notes → Manager

From the Configurator (Claude session, cwd C:\). We coordinate via git +
team files (see communication.md § Concurrent-Claude notes). This is a
handoff, not an order — you are Manager-tier, not subordinate.

## What I changed (2026-07-04) to fix Manager↔Employee coordination

Root cause of "employees did nothing": their kickoffs did session-start
then WAITED idle — no poll loop — and SendMessage cannot reach a separate
Claude Code session. So your assignments never arrived.

Fixes, all committed to `master`:
1. Each `team/kickoffs/employee-N.txt` now ends by entering a self-poll
   loop: `/loop 2m` → `git merge master`, re-read its "Current task" in
   context.txt + any `[URGENT/TAKE: employee-N]` in todo-list.txt,
   execute, update its section, commit to its branch, repeat.
2. Removed "SendMessage works" from manager.md, communication.md,
   employee-guide.md, kickoffs. Channel = git + team files via POLLING.
   Sub-agent tradeoff documented in manager.md § Reaching Employees.
3. `team/in-game-owner.txt` added — single-driver lock until mod 0.10.6
   is deployed. I set `owner: manager-keepalive` (your keep-alive sub-
   agent). Reassign it when you hand the character to an employee.

## Poll is LOCAL, not origin

All worktrees share ONE git object store on this machine, so employees
use `git merge master` (no fetch) and commit locally (no push) — you see
their branches directly. If you want origin-based sync for hunterzh37's
separate machine, tell JJ and the Configurator will switch the loop to
`git fetch origin && git merge origin/master` + push. Not done by default.

## ACTION NEEDED FROM YOU before employees restart

Assignments in context.txt are partly STALE. These are already merged to
master by your sub-agents and must NOT be redone:
- mod 0.10.6 multi-char
- bridge connect_named + placement decrement fix
- layouts helpers (electric-drill array + belt-run)

Please refresh each employee's "Current task" field to fresh,
non-overlapping work BEFORE they relaunch, so they don't repeat finished
work. Then JJ will relaunch ONE employee to test the poll loop.

## Relaunch procedure (per pane)

The running employee sessions are idle and predate the loop — they will
not start polling until relaunched. To relaunch one: in its worktree run
`git merge master` (to pull these updated docs), then paste
`team/kickoffs/employee-N.txt`. It will re-run session-start and enter
the loop.

## Heads-up: worktree folder names are scrambled vs branches

- C:\ClaudeTeam\worktrees\agent-1 → branch employee-1
- C:\ClaudeTeam\worktrees\agent-2 → branch employee-3
- C:\ClaudeTeam\worktrees\agent-3 → branch employee-2
- C:\ClaudeTeam\worktrees\agent-4 → branch employee-4
Identity = the checked-out BRANCH, not the folder name. The kickoffs now
self-identify via `git branch --show-current`, so this is cosmetic — but
don't be fooled by the folder name. I did NOT re-checkout to fix it
(would disturb running sessions).

Not restarting the server or touching the live base. Pinging JJ that
polling is wired; test with one employee.
