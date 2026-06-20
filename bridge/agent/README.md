# bridge/agent — agentic-play library

Distillation of the ~40 ad-hoc scripts written during day-1 and day-2 of agentic
play. Encapsulates the alignment math, character control loops, and crafting
flows so future agentic-play sessions don't repeat the same mistakes.

## Usage

```python
import os
os.environ['FACTORIO_RCON_PASSWORD'] = '<from start-server.bat>'

from agent import Agent, plan_iron_smelt_line, execute_layout

with Agent.connect() as a:
    a.walk_to(-14, 51)
    spec = plan_iron_smelt_line(drill_ore_x=-14.5, drill_ore_y=50.5)
    execute_layout(a, spec)
```

## Modules

| File | Purpose | Lines |
|---|---|---|
| `core.py` | `Agent` class — RCON connection, character context, lazy sub-modules | ~110 |
| `movement.py` | walking + pathfinding, chunked long-distance walks, step-aside | ~50 |
| `placement.py` | snap-aware placement, blocker clearing, take-back, relocate | ~75 |
| `mining.py` | mine_at (with walk-in retry), mine_nearest, chop_trees | ~70 |
| `fuel.py` | single-slot-aware fueling, fuel_chain for batches | ~50 |
| `inventory.py` | character inv listing, chest transfers, craft+wait | ~60 |
| `lua.py` | silent-command escape helpers | ~30 |
| `geometry.py` | snap math constants (1×1/2×2/3×3), drill_drop_position, inserter pickup helpers | ~80 |
| `layouts.py` | declarative chain plans (drill→chest, iron line, power) | ~110 |

All modules stay under ~150 lines per project convention.

## Why this exists

Day-1 + day-2 of agentic play (2026-06-20) produced ~40 one-off scripts in
`bridge/_*.py` that each rewrote the same boilerplate (RCON connect,
character lookup, snap math, fuel-by-name-not-position, walk-then-poll loop).
Several misalignments cost real time and JJ's patience to debug:

- Inserter direction is the **pickup side**, not where it drops to
- 2×2 furnace + 1×1 inserter: inserter Y = furnace_Y + 1, NOT +2
- Burner-mining-drill drops at center + (0.5, 1.3) in 2.0, NOT +2
- 2x2 entities snap to integer centers; 1x1 to *.5 centers
- Offshore-pump output direction is auto-detected from terrain, not the `direction` arg

All of these are now baked into `geometry.py` and the layout plans, so the
caller never has to think about them.

## Caveats

- Library was written offline (JJ playing on the save) without a runtime
  smoke test against the live server. Smoke-test before relying on it.
- `plan_power_chain` is intentionally incomplete — boiler N/S water inputs
  + auto-direction pump make a clean linear chain hard. See `POWER_CHAIN.md`
  for the discovery-driven deploy procedure.
