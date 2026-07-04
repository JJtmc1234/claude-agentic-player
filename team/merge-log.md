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

_(empty — no merges tracked yet in the 6-team era. Pre-team commits
listed below for reference.)_

## Pre-team (single-Claude era, 2026-06 → 2026-07)

Selected milestones. Full history: `git log --oneline`.

- 2026-06-27 beed976 — mod 0.10.5: hand-mine decrements amount.
- 2026-06-20 8494086 — cleanup: drop 61 superseded one-off scripts.
- 2026-06-20 c7cc96b — layouts: multi-drill parallel chain.
- 2026-06-20 bcb55d4 — live-fix: drill placed LAST in iron layout.
- 2026-06-20 ecbef8c — inventory.sort + kit-check + power solver.
- 2026-07-04 5c40042 — docs: refresh what-im-doing.txt.
