"""One-command bootstrap: from a freshly-spawned Claude character, set up
iron line + copper smelter + coal mine + copper mine autonomously.

Pre-conditions:
- Server running (via `server\\restart.ps1`)
- FACTORIO_RCON_PASSWORD set
- A spawned character exists (run `python bridge\\_spawn_claude.py` first if not).

Uses bridge/agent/ library — no inline snap math, no inline RCON wrapping.

NOTE: This script was authored offline (server stopped) on 2026-06-20. It
should be smoke-tested once before relying on it. The coordinates are
TIED TO the current biter-world save's resource layout (iron at -14.5,50.5,
copper at 87.5,37.5, coal at 53.5,-48.5). On a different world, scout
first and parameterize.
"""
from __future__ import annotations
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from agent import (
    Agent,
    plan_iron_smelt_line,
    plan_drill_to_chest,
)
from agent.layouts import execute_layout
from agent.geometry import DIR_SOUTH


# Tunable: resource centers from day-2 scout. Verify with find_nearest_resource
# on a fresh world before relying.
IRON_PATCH = (-14.5, 50.5)
COPPER_PATCH = (87.5, 37.5)   # actual rich tile near here
COAL_PATCH = (53.5, -48.5)    # best-amount tile found day 2


def step_say(msg: str):
    print(f"\n=== {msg} ===")


def craft_until(a: Agent, recipes: list, min_inventory: dict | None = None):
    """Craft recipes in order, optionally re-crafting until min_inventory met."""
    for recipe, count in recipes:
        print(f"  craft {recipe} x{count} ...")
        st = a.inventory.craft(recipe, count)
        if st.get('status') not in ('completed', 'idle'):
            print(f"    WARN: {st}")
    if min_inventory:
        inv = a.inventory.list()
        for name, need in min_inventory.items():
            if inv.get(name, 0) < need:
                print(f"  WARN low {name}: have {inv.get(name, 0)} need {need}")


def build_iron_line(a: Agent):
    step_say("iron smelt line near iron patch")
    a.movement.walk_chunked(IRON_PATCH[0], IRON_PATCH[1] - 4, chunk_size=30, radius_final=2)
    # Craft anything we'll need that isn't in starter inv (inserter)
    craft_until(a, [
        ('iron-gear-wheel', 1),
        ('burner-inserter', 1),
    ])
    spec = plan_iron_smelt_line(IRON_PATCH[0], IRON_PATCH[1])
    print(f"  layout: {spec.name}")
    for p in spec.placements:
        print(f"    place {p.item} @ ({p.x},{p.y}) dir={p.direction}  -- {p.note}")
    execute_layout(a, spec)
    # Verify by reading chest
    chest_xy = (spec.placements[-1].x, spec.placements[-1].y)
    time.sleep(15)
    plates = a.inventory.chest_count(chest_xy[0], chest_xy[1], 'iron-plate')
    print(f"  after 15s: iron-plate in chest = {plates}")


def build_copper_mine(a: Agent):
    step_say("copper mine (drill+chest, no inserter)")
    a.movement.walk_chunked(COPPER_PATCH[0], COPPER_PATCH[1] + 6, chunk_size=30, radius_final=2)
    craft_until(a, [
        ('iron-gear-wheel', 3),
        ('stone-furnace', 1),  # ingredient for burner-mining-drill
        ('burner-mining-drill', 1),
    ])
    spec = plan_drill_to_chest(COPPER_PATCH[0], COPPER_PATCH[1] + 4.5)  # offset south of patch center
    print(f"  layout: {spec.name}")
    for p in spec.placements:
        print(f"    place {p.item} @ ({p.x},{p.y}) dir={p.direction}")
    execute_layout(a, spec)
    chest_xy = (spec.placements[-1].x, spec.placements[-1].y)
    time.sleep(15)
    ore = a.inventory.chest_count(chest_xy[0], chest_xy[1], 'copper-ore')
    print(f"  after 15s: copper-ore in chest = {ore}")


def build_coal_mine(a: Agent):
    step_say("coal mine (drill+chest)")
    a.movement.walk_chunked(COAL_PATCH[0], COAL_PATCH[1] + 6, chunk_size=30, radius_final=2)
    craft_until(a, [
        ('iron-gear-wheel', 3),
        ('stone-furnace', 1),
        ('burner-mining-drill', 1),
    ])
    # Hand-mine 3 coal first so we have fuel for the drill
    print("  hand-mining 3 coal for fuel...")
    a.mining.mine_nearest('coal', n=3)
    spec = plan_drill_to_chest(COAL_PATCH[0], COAL_PATCH[1])
    print(f"  layout: {spec.name}")
    execute_layout(a, spec)
    chest_xy = (spec.placements[-1].x, spec.placements[-1].y)
    time.sleep(15)
    coal = a.inventory.chest_count(chest_xy[0], chest_xy[1], 'coal')
    print(f"  after 15s: coal in chest = {coal}")


def main():
    with Agent.connect() as a:
        x, y = a.position()
        print(f"Claude at ({x:.1f}, {y:.1f}), hp={a.health()}")

        # Chop wood for initial fuel reserve
        step_say("chop 15 trees for fuel reserve")
        chopped = a.mining.chop_trees(15, search_radius=100)
        print(f"  chopped {chopped} trees, wood now = {a.inventory.have('wood')}")

        build_iron_line(a)
        build_coal_mine(a)
        build_copper_mine(a)

        # Final inventory
        step_say("final inventory")
        for name, count in sorted(a.inventory.list().items(), key=lambda kv: -kv[1]):
            print(f"  {name}: {count}")


if __name__ == '__main__':
    main()
