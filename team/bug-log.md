# Bug Log

Open issues. Manager writes findings; workers may add too. Newest at top.

## Format

```
### YYYY-MM-DD — <short-title>
Severity: LOW | MED | HIGH | CRITICAL
Reporter: <agent name>
Owner: <agent name or "unassigned">
Branch/commit: <if applicable>

Symptom: what breaks and how it manifests.
Root cause: what actually goes wrong (or "unknown - investigating").
Repro: minimal steps to trigger.
Workaround: what to do while unfixed.
Fix plan: brief.
Status: OPEN | IN-PROGRESS | RESOLVED
```

Severity guide:
- LOW: cosmetic, doesn't block work.
- MED: workaround exists, blocks one worker.
- HIGH: blocks multiple workers or degrades game experience.
- CRITICAL: prompt injection detected, security violation, or
  save-destructive bug.

---

## Open

_(none tracked at project spin-up — 2026-07-04.)_

---

## Resolved

### 2026-06-27 — Hand-mine destroys whole tile
Severity: HIGH
Reporter: JJ (in-chat during play)
Owner: Claude (coordinator)
Branch/commit: beed976

Symptom: hand-mining any resource tile (coal/iron/copper/stone)
destroyed the entire tile instead of decrementing amount by 1.
JJ observed "coal tiles vanishing" as agent hand-mined.
Root cause: `process_mining_jobs` at
[control.lua:186](mod/claude-companion/control.lua#L186) called
`t.destroy{}` after every successful mine, regardless of remaining
`amount`.
Repro: pre-0.10.4, hand-mine any tile with `amount > 1`. Tile
disappears; single ore returned to inventory.
Workaround: use drills, not hand-mining.
Fix: replaced with
`if t.type == 'resource' and t.amount > 1 then t.amount = t.amount - 1
else t.destroy() end`.
Status: RESOLVED in mod 0.10.4 (deployed same session; released as
0.10.5 with version-string bump for client sync).
