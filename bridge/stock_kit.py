"""Walk to base, drain chests, craft a useful kit, sort inventory."""
from __future__ import annotations
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from agent import Agent  # noqa: E402


# Resource targets after this script runs (rough). Tuned to my current inventory.
KIT_TARGET = {
    'burner-inserter': 10,
    'burner-mining-drill': 3,
    'stone-furnace': 5,
    'wooden-chest': 10,
    'iron-gear-wheel': 20,
    'pipe': 15,
    'small-electric-pole': 5,
    'transport-belt': 30,
    'copper-cable': 20,
    'electronic-circuit': 5,
}


def drain_chests(a: Agent) -> dict:
    """Move iron/coal/copper from base chests into character inventory."""
    print("=== drain base chests ===")
    grabbed = {}
    for label, x, y, item in [
        ('iron chest', -13.5, 55.5, 'iron-plate'),
        ('copper chest', -10.5, 54.5, 'copper-plate'),
    ]:
        in_chest = a.inventory.chest_count(x, y, item)
        if in_chest and in_chest > 0:  # chest_count returns None on error
            res = a.inventory.take_from_chest(x, y, item, in_chest)
            grabbed[item] = res.get('moved', 0)
            print(f"  {label}: +{grabbed[item]} {item}")
    return grabbed


def fetch_coal(a: Agent) -> int:
    """Walk to coal chest, take some coal for fuel."""
    print("=== fetch coal from far chest (54.5, -46.5) ===")
    a.movement.walk_chunked(54, -46, chunk_size=30, radius_final=3)
    in_chest = a.inventory.chest_count(54.5, -46.5, 'coal')
    if in_chest and in_chest > 5:  # chest_count returns None on error
        take = min(in_chest, 30)
        res = a.inventory.take_from_chest(54.5, -46.5, 'coal', take)
        moved = res.get('moved', 0)
        print(f"  took {moved} coal (chest had {in_chest})")
        return moved
    print(f"  coal chest only has {in_chest}, leaving it")
    return 0


def craft_kit(a: Agent) -> dict:
    """Compute shortfall, craft each missing item. Stone-furnace ingredients
    for drills come from extra stone-furnace crafts."""
    print("=== compute + craft kit ===")
    shortfall = a.inventory.have_at_least(KIT_TARGET)
    print(f"  shortfall: {shortfall}")
    if not shortfall:
        print("  already stocked!")
        return {}

    # Craft order: dependencies first.
    # gear is needed by inserter (1), belt (1), drill (3), pole (no)
    # furnace is needed by drill (1)
    # cable is needed by circuit (3), pole (1)
    # circuit is needed by belt (no), drill (no), basic stuff doesn't need it but lab does
    # Compute total deps roughly:
    needed_gears = (shortfall.get('iron-gear-wheel', 0)
                    + shortfall.get('burner-inserter', 0)
                    + shortfall.get('transport-belt', 0)
                    + shortfall.get('burner-mining-drill', 0) * 3)
    needed_furnaces = (shortfall.get('stone-furnace', 0)
                       + shortfall.get('burner-mining-drill', 0))
    needed_cables = (shortfall.get('copper-cable', 0)
                     + shortfall.get('electronic-circuit', 0) * 3
                     + shortfall.get('small-electric-pole', 0) * 2)

    order = [
        ('stone-furnace', needed_furnaces),
        ('iron-gear-wheel', needed_gears),
        ('copper-cable', max(0, needed_cables // 2)),  # recipe gives 2 per craft
        ('electronic-circuit', shortfall.get('electronic-circuit', 0)),
        ('burner-mining-drill', shortfall.get('burner-mining-drill', 0)),
        ('burner-inserter', shortfall.get('burner-inserter', 0)),
        ('wooden-chest', shortfall.get('wooden-chest', 0)),
        ('transport-belt', shortfall.get('transport-belt', 0)),
        ('pipe', shortfall.get('pipe', 0)),
        ('small-electric-pole', max(0, shortfall.get('small-electric-pole', 0) // 2)),  # gives 2 per
    ]
    results = {}
    for recipe, count in order:
        if count <= 0:
            continue
        print(f"  craft {recipe} x{count} ...")
        st = a.inventory.craft(recipe, count)
        results[recipe] = st.get('status')
    return results


def main():
    with Agent.connect() as a:
        print(f"position: {a.position()}  hp={a.health()}")

        # Step 1: walk to base
        print("\nwalking to base (-11, 53)...")
        a.movement.walk_chunked(-11, 53, chunk_size=30, radius_final=2)

        # Step 2: drain plate chests
        drain_chests(a)

        # Step 3: walk to coal chest, grab some coal
        fetch_coal(a)

        # Step 4: walk back to base to craft
        a.movement.walk_chunked(-11, 53, chunk_size=30, radius_final=2)

        # Step 5: craft kit
        craft_kit(a)

        # Step 6: sort inventory
        print("\n=== sort inventory ===")
        sorted_ok = a.inventory.sort()
        print(f"  {'OK' if sorted_ok else 'FAIL'}")

        # Step 7: print final state
        print("\n=== final inventory ===")
        inv = a.inventory.list()
        for n, c in sorted(inv.items(), key=lambda kv: -kv[1]):
            target = KIT_TARGET.get(n)
            marker = f" (kit: {target}+)" if target else ""
            print(f"  {n}: {c}{marker}")


if __name__ == '__main__':
    main()
