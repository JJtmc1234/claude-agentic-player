# Kickoff prompts

Paste one of these into a fresh Claude Code session (in a WezTerm pane
or elsewhere) to spin up an agent with the right context and role.

## Files

- `manager.txt` — for the Manager (single instance).
- `employee-1.txt` — for Employee-1 (suggested role: MINER).
- `employee-2.txt` — for Employee-2 (suggested role: COURIER).
- `employee-3.txt` — for Employee-3 (suggested role: BUILDER).
- `employee-4.txt` — for Employee-4 (suggested role: SCOUT / DEFENSE).

## Suggested WezTerm layout

- Pane 1 (top wide): Manager. Watches everything, talks to JJ.
- Pane 2 (bottom-left): Employee-1 (miner).
- Pane 3 (bottom-center-left): Employee-2 (courier).
- Pane 4 (bottom-center-right): Employee-3 (builder).
- Pane 5 (bottom-right): Employee-4 (scout).

## Order to launch

1. Start Manager first. Wait for it to read the handbooks and post
   its Manager-section update to `team/context.txt`.
2. Start Employees in any order. Each fills in their section and
   posts a `[STARTED]` line to `team/todo-list.txt`.
3. Manager sees the STARTED lines and assigns first tasks.

## If JJ wants to change an Employee's role

- Manager updates the "Current task" field in that Employee's
  `context.txt` section.
- Manager sends the Employee a SendMessage (Claude Code SDK) with
  the new task.
- Employee acknowledges by updating their "Recent changes" line.

## If a Claude session dies mid-work

- Manager notices via context.txt not updating.
- JJ opens a new WezTerm pane, pastes the same kickoff file, and the
  fresh Claude resumes at the branch tip. The `[STARTED]` line goes
  in with the new timestamp.
- If the crashed session had uncommitted work, it's lost — commit
  often.
