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

_(none)_

## Resolved (2.1 migration)

### 2026-07-07 — mod craft() crashes on Factorio 2.1 (recipe.category removed)
Severity: HIGH
Reporter: employee-2 (courier) — flagged "mod craft() broken on 2.1"
Owner: Manager
Branch/commit: master (fix in mod 0.11.1)

Symptom: every `remote.call('claude','craft',...)` threw a Lua error
"LuaRecipePrototype doesn't contain key category" (control.lua:903). No char
could hand-craft -> base bootstrap fully blocked (0 furnaces/drills after 15min).
Root cause: Factorio 2.1 changelog (verified in data/changelog.txt) —
"Removed LuaRecipePrototype::category ... Use categories instead" AND reworked
recipe categories ("removed basic-crafting, added hand-crafting; multiple
categories per recipe"). The mod read the removed singular `recipe.category`
in 3 spots and hardcoded a now-stale category set incl. basic-crafting.
Fix: read the CHARACTER prototype's crafting_categories dynamically
(player_craft_categories/is_hand_craftable helpers) and check recipe.categories
(array) against it — mod-portable across future mod sets (K2/SE/Bob's). Also
fixed get_recipe_info to return .categories instead of .category. Logic verified
live against prototypes (bootstrap recipes hand-craftable; engine-unit/iron-plate
correctly not). Deployed in mod 0.11.1.
Status: FIXED (0.11.1) — pending deploy (server restart).

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
