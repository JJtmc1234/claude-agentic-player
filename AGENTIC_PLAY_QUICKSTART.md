# Agentic Play — Quickstart

How to use the `bridge/agent/` library next session.

## Prereqs

1. Server running: `server\restart.ps1` (handles save→stop→deploy→start→ping)
2. `FACTORIO_RCON_PASSWORD` env var set (read it from `C:\FactorioServer\start-server.bat`)
3. A Claude character spawned: `python bridge\_spawn_claude.py` (only needed if `storage.claude_char_unum` is unset, e.g. on a fresh world)

## Common one-liners

```powershell
# Set the env var once per shell session
$env:FACTORIO_RCON_PASSWORD = (Select-String -Path "C:\FactorioServer\start-server.bat" -Pattern '--rcon-password "([^"]+)"').Matches[0].Groups[1].Value

# Drive me via in-game chat (open Factorio chat, type "claude: where")
python bridge\chat_loop.py

# Bootstrap a starter base on a fresh character (iron + copper + coal mines)
python bridge\build_starter_base.py

# Keep existing factory chains alive (refuel, chop wood, status)
python bridge\autopilot.py --interval 60

# Try the autonomous power chain builder near a water tile
python -c "import sys; sys.path.insert(0, 'bridge'); from agent import Agent, build_power_chain; \
           with Agent.connect() as a: print(build_power_chain(a, -41, 21))"
```

## In-game chat commands (via `chat_loop.py`)

Type these in Factorio chat as IdBaj98 or factoriobrine — handles are
filtered, anything else is ignored. Destructive keywords (delete/remove/kill)
are blocked even from trusted handles.

| Command | Effect |
|---|---|
| `claude: where` | reports position + HP |
| `claude: status` | top-5 inventory items |
| `claude: walk x y` | walks to (x, y), chunked for long distances |
| `claude: chop N` | chops up to N nearby trees (cap 20) |
| `claude: mine resource N` | mines N tiles of resource (cap 15) |
| `claude: stop` | cancels any active walk/mining |

## Library API at a glance

```python
from agent import Agent

with Agent.connect() as a:
    # Movement
    a.walk_to(x, y, radius=1.5)
    a.movement.walk_chunked(x, y, chunk_size=30)  # long distances

    # Placement (auto-snaps to correct grid for 2x2 / 1x1 / 3x3)
    a.place('burner-mining-drill', -14.5, 50.5, direction=8)

    # Mining
    a.mining.mine_at(x, y)  # auto walks closer on out-of-reach
    a.mining.mine_nearest('iron-ore', n=5)
    a.mining.chop_trees(10)

    # Fueling (single-slot aware, won't error on mixed fuels)
    a.fuel.fuel('burner-mining-drill', -14, 51, fuel_item='wood', want_amount=5)

    # Inventory + chests
    inv = a.inventory.list()  # {name: count}
    a.inventory.take_from_chest(x, y, 'iron-plate', count=40)
    a.inventory.put_in_chest(x, y, 'wood', count=20)
    a.inventory.craft('burner-inserter', 1)  # waits for completion

    # Declarative layouts
    from agent import plan_iron_smelt_line
    from agent.layouts import execute_layout
    spec = plan_iron_smelt_line(-14.5, 50.5)
    execute_layout(a, spec)
```

## Geometry helpers (if writing custom layouts)

```python
from agent.geometry import (
    snap_2x2_center,        # for drills, furnaces
    snap_1x1_center,        # for chests, inserters, pipes, poles
    drill_drop_position,    # exact drop coord for a south-facing burner drill
    inserter_pickup_for_drill,
    inserter_pickup_for_furnace,
    DIR_NORTH, DIR_EAST, DIR_SOUTH, DIR_WEST,
)
```

All snap math uses **round-half-up** (matches Factorio, NOT Python's banker's).

## Power chain — the hard one

Pump direction in 2.0 is auto-detected by terrain (the `direction` arg is
ignored). Boiler 3×2 water inputs are perpendicular to flow (N and S of the
west column for east-facing). See `POWER_CHAIN.md` for the discovery-driven
deploy procedure, or just try `build_power_chain(a, water_hint_x, water_hint_y)`
which implements it autonomously (untested live).

## Things to verify before relying on the library

It was written offline (server stopped while JJ played) on 2026-06-20.
Smoke-test against live server first:

1. `python bridge\agent\test_geometry.py` — pure math, passes locally (11/11)
2. `python bridge\agent\test_layouts.py` — pure math, passes (14/14)
3. `python bridge\_who_am_i.py` — verifies character + RCON connection
4. Try a single library call (e.g. `Agent.connect()` then `a.position()`)

If any of those fail, fix before running `build_starter_base.py` or `autopilot.py`.
