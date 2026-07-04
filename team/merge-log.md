# Merge Log

Every merge Manager lands on `main`. Newest at top.

## Format

```
### YYYY-MM-DD HH:MM — <branch> → main
sha: <merge-sha>
Reviewed-by: Manager
Squash / FF / merge-commit
Summary: one-line description.
Files: <count> changed, <insertions>+, <deletions>-.
Notes: any deviations from clean-merge (rebase needed, conflict
resolved, follow-up bug filed, etc.).
```

Manager updates this file in the SAME commit as the merge itself
(or immediately after) so history stays consistent.

---

### 2026-07-04 (fresh Manager session) — employee-2 → master
sha: a06f99b (squash of employee-2 @ 77ea20c)
Reviewed-by: Manager (Opus 4.8)
Squash
Summary: doc-only — employee-2 session-start HOLD updates in context.txt +
  todo-list.txt; independently flagged that RCON pong now reports 0.10.6
  (deploy status question).
Files: 2 changed, 25+, 2-.
Notes: no code touched, no injection. Prompt-injection scan clean. Confirmed
  the 0.10.6-deployed observation live (list_chars resolves) — reconciled in
  in-game-owner.txt + Manager context section.

### 2026-07-04 ~12:2x — mod 0.10.6 multi-char → master
sha: bcc2b2f (merge of worktree 72fcbf9)
Reviewed-by: Manager (Opus 4.8)
merge-commit (--no-ff)
Summary: adds spawn_named_char / list_chars / remove_char to the `claude`
  remote interface + storage.claude_chars map + on_configuration_changed
  migration (legacy claude_char_unum -> {main=unum}, idempotent).
Files: 2 changed, 82+, 3-.
Notes: NOT DEPLOYED. luac -p OK, but in-game spawn + migration-firing are
  UNVERIFIED (need running server + JJ present). Deploy this in a
  controlled window; validate spawn_named_char round-trip before relying
  on it. Author sub-agent forked from master pre-team-doc-commit; clean
  merge (disjoint from docs).

### 2026-07-04 ~12:3x — bridge connect_named + placement fix + team.py → master
sha: (this merge) (merge of worktree 54506e3)
Reviewed-by: Manager (Opus 4.8)
merge-commit (--no-ff)
Summary: (A) Agent.connect_named(name) resolves unum via mod list_chars with
  graceful single-char fallback; (B) placement._mine_resources now
  decrements resource amount instead of destroy() (was wiping whole ore
  tiles — mirrors control.lua 0.10.4 fix); (C) new bridge/team.py
  scaffolding (bootstrap/assign_task).
Files: 4 changed, 305+, 4-.
Notes: tests green on master post-merge — test_placement 15/15,
  test_geometry 11/11, test_layouts 23/23, compileall OK. list_chars
  round-trip UNVERIFIED (mod 0.10.6 not deployed); connect_named happy
  path only exercised against the {name->unum} contract, not live RCON.

### 2026-07-04 ~12:4x — layouts expansion helpers → master
sha: 42e2e83 (merge of worktree 7cf0080)
Reviewed-by: Manager (Opus 4.8)
merge-commit (--no-ff)
Summary: plan_electric_drill_array(patch_center, rows, cols) (3x3 drills +
  east-west belt lanes + small-pole coverage, all electric) and
  plan_belt_run(start, end) (straight/L belt path); +5 geometry helpers &
  constants for electric-drill/small-pole.
Files: 4 changed, 314+, 5-.
Notes: constants sourced from base prototypes (electric-drill
  vector_to_place_result {0,-1.85} X-centered 3x3; small-pole supply 2.5 /
  wire 7.5). Tests on master post-merge: test_geometry 19/19, test_layouts
  49/49, test_placement 15/15, compileall OK. NOT in-game verified —
  planners return specs; execute_layout round-trip untested live.

_(pre-team commits below for reference.)_

## Pre-team (single-Claude era, 2026-06 → 2026-07)

Selected milestones. Full history: `git log --oneline`.

- 2026-06-27 beed976 — mod 0.10.5: hand-mine decrements amount.
- 2026-06-20 8494086 — cleanup: drop 61 superseded one-off scripts.
- 2026-06-20 c7cc96b — layouts: multi-drill parallel chain.
- 2026-06-20 bcb55d4 — live-fix: drill placed LAST in iron layout.
- 2026-06-20 ecbef8c — inventory.sort + kit-check + power solver.
- 2026-07-04 5c40042 — docs: refresh what-im-doing.txt.
