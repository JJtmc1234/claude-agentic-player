"""Autopilot — keeps factory chains running without JJ's intervention.

Loop:
  1. Scan known entities (drills, furnaces, inserters) for fuel level
  2. Refuel anything low (prefer coal > wood)
  3. If wood inventory is low, walk to nearest trees and chop until topped up
  4. Drain chests that are nearly full into character (warning only — could move to a depot in future)
  5. Print one-line status, sleep, repeat

Stop with Ctrl+C. Respects [[feedback-driving]] — won't open new directions,
only maintains what's already built. Won't restart server, won't deploy mods,
won't push to git.

KNOWN ENTITIES (from day 2 state on the biter world):
  - iron drill (-14, 51), iron furnace (-14, 53), iron inserter (-13.5, 54.5), iron chest (-13.5, 55.5)
  - copper furnace (-11, 52), copper inserter (-10.5, 53.5), copper chest (-10.5, 54.5)
  - copper drill (87, 42), copper-ore chest (87.5, 43.5)
  - coal drill (54, -48), coal chest (54.5, -46.5)

Adjust the WATCHED list below if you've changed/added/relocated entities.
"""
from __future__ import annotations
import argparse
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from agent import Agent  # noqa: E402


@dataclass
class WatchedEntity:
    name: str  # display name
    entity_name: str  # Factorio entity name (e.g. 'burner-mining-drill')
    x: float
    y: float
    fuelable: bool = True


# Edit this list to match your world
WATCHED = [
    WatchedEntity('iron drill', 'burner-mining-drill', -14, 51),
    WatchedEntity('iron furnace', 'stone-furnace', -14, 53),
    WatchedEntity('iron inserter', 'burner-inserter', -13.5, 54.5),
    WatchedEntity('copper furnace', 'stone-furnace', -11, 52),
    WatchedEntity('copper inserter', 'burner-inserter', -10.5, 53.5),
    WatchedEntity('copper drill (far)', 'burner-mining-drill', 87, 42, fuelable=True),
    WatchedEntity('coal drill (far)', 'burner-mining-drill', 54, -48, fuelable=True),
]
CHESTS_TO_WATCH = [
    ('iron chest', 'iron-plate', -13.5, 55.5),
    ('copper chest', 'copper-plate', -10.5, 54.5),
    ('copper-ore chest', 'copper-ore', 87.5, 43.5),
    ('coal chest', 'coal', 54.5, -46.5),
]

WOOD_TOP_UP_THRESHOLD = 20  # if char wood < this, go chop
WOOD_TOP_UP_TARGET = 80
FUEL_LOW_THRESHOLD = 3  # refuel if entity has <= this many fuel items


def fuel_level(agent: Agent, e: WatchedEntity) -> int:
    """Return wood+coal count in entity's fuel inv. -1 if entity missing."""
    body = (
        f"local s = game.surfaces['nauvis']; "
        f"local ent = s.find_entities_filtered{{position={{{e.x}, {e.y}}}, "
        f"radius=0.6, name='{e.entity_name}'}}[1]; "
        "if not ent then rcon.print(-1); return end; "
        "local fi = ent.get_fuel_inventory(); "
        "if not fi then rcon.print(-2); return end; "
        "local total = 0; "
        "for _, st in ipairs(fi.get_contents()) do total = total + st.count end; "
        "rcon.print(total)"
    )
    out = agent.rcon.command('/silent-command ' + body).strip()
    try:
        return int(out)
    except ValueError:
        return -3


def refuel_low(agent: Agent, verbose: bool = True) -> dict:
    """Refuel any watched entity below threshold. Returns {entity_name: result}."""
    inv = agent.inventory.list()
    have_coal = inv.get('coal', 0)
    have_wood = inv.get('wood', 0)
    results = {}
    for e in WATCHED:
        if not e.fuelable:
            continue
        lvl = fuel_level(agent, e)
        if lvl == -1:
            results[e.name] = 'missing'
            continue
        if lvl > FUEL_LOW_THRESHOLD:
            continue
        fuel = 'coal' if have_coal > 0 else 'wood' if have_wood > 0 else None
        if fuel is None:
            results[e.name] = 'no-fuel-in-inv'
            continue
        res = agent.fuel.fuel(e.entity_name, e.x, e.y, fuel_item=fuel, want_amount=5)
        if res.get('ok'):
            moved = res.get('moved', 0)
            if fuel == 'coal': have_coal -= moved
            else: have_wood -= moved
            results[e.name] = f"+{moved} {fuel}"
            if verbose:
                print(f"  refueled {e.name}: +{moved} {fuel}")
        else:
            results[e.name] = res.get('reason', 'fail')
    return results


def maybe_chop_wood(agent: Agent, verbose: bool = True) -> int:
    wood = agent.inventory.have('wood')
    if wood >= WOOD_TOP_UP_THRESHOLD:
        return 0
    if verbose:
        print(f"  wood low ({wood}) — chopping...")
    need = (WOOD_TOP_UP_TARGET - wood) // 4 + 1
    chopped = agent.mining.chop_trees(min(need, 15), search_radius=100)
    if verbose:
        print(f"  chopped {chopped} trees, wood now = {agent.inventory.have('wood')}")
    return chopped


def chest_status(agent: Agent) -> dict:
    out = {}
    for name, item, x, y in CHESTS_TO_WATCH:
        out[name] = agent.inventory.chest_count(x, y, item)
    return out


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--interval', type=int, default=60, help='seconds between cycles')
    p.add_argument('--cycles', type=int, default=0, help='0 = infinite')
    args = p.parse_args()

    print(f"autopilot online. interval={args.interval}s. cycles={args.cycles or 'inf'}.")
    print(f"watching {len(WATCHED)} entities + {len(CHESTS_TO_WATCH)} chests.")
    print("Ctrl+C to stop.")

    cycle = 0
    with Agent.connect() as agent:
        while args.cycles == 0 or cycle < args.cycles:
            cycle += 1
            print(f"\n=== cycle {cycle} @ {time.strftime('%H:%M:%S')} ===")
            try:
                maybe_chop_wood(agent)
                refuel_results = refuel_low(agent)
                chests = chest_status(agent)
                chest_line = ', '.join(f"{n}={c}" for n, c in chests.items())
                inv = agent.inventory.list()
                fuel_line = f"wood={inv.get('wood', 0)} coal={inv.get('coal', 0)}"
                print(f"  chests: {chest_line}")
                print(f"  inv: {fuel_line}")
            except KeyboardInterrupt:
                print("\nstopping.")
                break
            except Exception as e:
                print(f"  cycle error: {e}")
            time.sleep(args.interval)


if __name__ == '__main__':
    main()
