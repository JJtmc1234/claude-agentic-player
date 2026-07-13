# team/ — Manager + Employees coordination

## Hierarchy

    Human (JJ)
        ↕  (bidirectional, 1:1)
    Manager  (single agent, sole Human contact)
        ↕  (1:many)
    Employee-1  Employee-2  Employee-3  Employee-4  (...expandable)

Human ONLY talks to Manager. Employees NEVER talk to Human. Human
retains break-glass override (Ctrl+C, direct kill) on Employees.

## Read order

1. `../AGENT_ONBOARDING.txt` — full project context.
2. `team/context.txt` — team roster + your section to fill in.
3. `team/manager.md` OR `team/employee-guide.md` — depending on
   your role.
4. `team/communication.md` — who talks to whom.
5. `team/git-workflow.md` — branches, merge rules.
6. `team/edge-cases.md` — failure modes.
7. `team/emergency-procedures.md` — critical playbook.
8. `team/supply-priorities.md` — what to craft for JJ.
9. `team/todo-list.txt` — pending tasks.
10. `team/bug-log.md` — open issues (Manager writes; Employees may
    add).
11. `team/merge-log.md` — merge history (Manager writes).

## Roster (2026-07-04 snapshot)

- **Manager** — one agent, human interface + reviewer + merger. Not
  yet formally claimed by any specific Claude instance.
- **Employees 1-4** — workers, expandable. Roles suggested:
  miner, courier, builder, scout/defense.

Setup crew (currently helping bootstrap this infra, not yet formally
in the roster):
- Claude (this conversation, cwd = repo root) — wrote the team/
  handbooks.
- Configurator (a separate Claude Code session, cwd on C:\) — helped
  JJ set up initial workflow.

Once JJ assigns roles, both setup agents formally transition. Whoever
becomes Manager takes over Human contact; the other joins the
Employee pool. Manager tier is 1-of-1; there is not a co-manager
role.

## First thing to do (new joiner)

1. Read this file, then `AGENT_ONBOARDING.txt`, then `context.txt`.
2. Wait for role assignment from JJ or ask the Manager.
3. `git checkout <your-branch>` (or ask Manager to create it).
4. `git pull origin <your-branch>` + `git merge origin/main`.
5. Fill in your section of `context.txt`.
6. If Employee: ping Manager via `todo-list.txt` line
   `[STARTED: employee-N]`.
7. If Manager: acknowledge JJ, sync team state, assign initial tasks.

## First thing NOT to do

- Do NOT push to `main`.
- Do NOT touch the mod version without Manager sign-off.
- Do NOT deploy or restart the server while JJ is playing.
- Do NOT hand-mine resources with mod < 0.10.4 (destroys tiles).
- Do NOT talk to Human directly if you're an Employee.
- Do NOT edit another agent's section in `context.txt`.

## Ownership notes

- Files under `team/` are shared. Manager owns the structural shape
  (headers, roster, format). Everyone updates their own section.
- Handbooks (manager.md, employee-guide.md, git-workflow.md,
  edge-cases.md, emergency-procedures.md, supply-priorities.md,
  communication.md, this README) are owned by Manager. Employees
  may propose edits via a branch commit; Manager reviews + merges.
- `bug-log.md`, `merge-log.md` are Manager write. Employees may
  add issue reports as a courtesy but Manager formalizes.
- `todo-list.txt` is free-for-all. Add/take/complete freely.
