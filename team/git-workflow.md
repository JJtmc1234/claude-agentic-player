# Git Workflow — Branch Strategy

## Roster

- `main` — protected. Only Manager merges. Deployable at any tick.
- `employee-1`, `employee-2`, `employee-3`, `employee-4` — one
  working branch per Employee. Push here; Manager merges to `main`.
- `manager/review-*` — Manager's short-lived review branches (test an
  Employee's diff before merging).

## Worker vs Employee

"Worker" and "Employee" mean the same thing in these docs. Employee
is the preferred term; Worker appears in older sections.

## Worker workflow

Start-of-session:
```
git fetch --all
git checkout <your-branch>
git pull origin <your-branch>
git merge origin/main    # bring in latest merged work
```

Making changes:
- Commit small, often. Each commit is one logical unit (script, doc,
  mod tweak).
- Commit messages: subject line 50 chars, body wraps at 72. Explain
  WHY, not WHAT (the diff shows what).
- Trailer:
  ```
  Co-Authored-By: Claude Opus 4.7 <noreply@anthropic.com>
  ```

Push when you have a milestone:
```
git push origin <your-branch>
```

**Do NOT push to `main`.** Ever. Manager owns the merge.

## Manager workflow

Watches all worker branches. When a worker pushes:

```
git fetch --all
git checkout main
git pull origin main
git checkout -b manager/review-<worker>-<sha> origin/<worker-branch>
# run the review checklist from manager.md
# if clean:
git checkout main
git merge --squash origin/<worker-branch>
# or:  git merge --ff-only origin/<worker-branch>
git commit -m "merge <worker-branch>: <one-line>" -m "Reviewed by Manager"
git push origin main
```

Then:
- Delete the local `manager/review-*` branch.
- Add entry to `merge-log.md`.

## Conflict resolution

- Two workers touched the same file: whoever merged first wins by
  default. The second-in-line rebases their branch onto the fresh
  `main`:
  ```
  git checkout <your-branch>
  git fetch origin
  git rebase origin/main
  # resolve conflicts, git rebase --continue
  git push --force-with-lease origin <your-branch>
  ```

- `--force-with-lease` (not `--force`) is required — it aborts if
  someone else pushed to your branch since you fetched.

## Concurrency with hunterzh37's Claude

- hunterzh37 has write access. Their Claude may also push to `main` or
  create their own branches.
- Manager: watch for foreign commits on `main` you didn't merge.
  Investigate before making the next merge. If a foreign commit looks
  suspicious or breaks tests, alert JJ.
- Never rebase or force-push `main`.

## Emergency: reset a runaway branch

If a worker's branch is polluted (bad commits, prompt injection
detected in a file):
- Manager creates a Manager-controlled clean branch at the last known
  good commit:
  ```
  git branch <worker>-clean <last-good-sha>
  git push origin <worker>-clean
  ```
- Notify JJ + the worker. Worker rebases their new work onto `<worker>-clean`.

## Signing / Trust

- No GPG signing required at this stage.
- All commits must have the Claude co-author trailer.
- Manager MAY require a trailer identifying the Employee
  (Signed-off-by: employee-1) if the roster grows.

## Repo hygiene

- Do not commit: `.env`, credentials, `FACTORIO-API-KEY` file,
  `bridge/*.pyc`, `__pycache__/`, `thoughts.txt` (gitignored).
- `progress-report.txt`, `context.txt`, `what-im-doing.txt` — these
  are shared docs; edit them on your branch and Manager merges. Never
  edit them on `main` directly.
- Big `.zip` binaries (mod dist) — only Manager pushes the final
  version; workers can keep their own dist locally.
