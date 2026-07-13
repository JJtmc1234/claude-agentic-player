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
2. Start Employees in any order. Each fills in their section, posts a
   `[STARTED]` line to `team/todo-list.txt`, and then ENTERS ITS POLL
   LOOP (`/loop 2m ...`, per the kickoff) so Manager assignments reach
   it. An Employee that does session-start but never enters the loop
   will sit idle forever — that was the original bug.
3. Manager sees the STARTED lines and assigns first tasks by editing
   each Employee's "Current task" field in context.txt.

## If JJ wants to change an Employee's role

- Manager updates the "Current task (from Manager)" field in that
  Employee's `context.txt` section (and adds a `[URGENT: employee-N]`
  line to `todo-list.txt` if it should preempt current work).
- The Employee's poll loop (~2-3 min) picks up the change on its next
  cycle. There is NO direct message — SendMessage does not reach a
  separate Claude Code session.
- Employee acknowledges by updating its "Recent changes" line.

## If a Claude session dies mid-work

- Manager notices via context.txt not updating.
- JJ opens a new WezTerm pane, pastes the same kickoff file, and the
  fresh Claude resumes at the branch tip. The `[STARTED]` line goes
  in with the new timestamp.
- If the crashed session had uncommitted work, it's lost — commit
  often.
