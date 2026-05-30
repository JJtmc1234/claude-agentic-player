"""
Orchestrator: have TEoC autonomously build all entity-ghosts on his surface.

For each iteration:
  1. analyze_ghosts -> total items needed across all remaining ghosts.
  2. get_character_inventory -> what TEoC already has.
  3. Compute deficit = needed - have.
  4. For each deficit item:
       a. Try chest-sourcing: find chests with the item, walk + take.
       b. If still short, try to craft it: recursively plan ingredients
          (chest-source, then craft, then mine/smelt for raw / smelted).
       c. If raw and not in chests, mine_resource.
       d. If a plate and not in chests, smelt (needs ore + coal + furnace).
  5. Walk to nearest ghost cluster, build_ghosts_in_range.
  6. Repeat until no ghosts remain OR no progress for N iterations.

This is the "AI brain" — the orchestrator. The mod provides primitives;
this script chains them into goal-directed behavior.

Caveats:
- The recipe planner is greedy/naive, not optimal.
- Smelting takes a long time (~3.2s per plate per furnace); the orchestrator
  will appear to pause for tens of seconds during smelt operations.
- For very large blueprints this can take many minutes.
- If a needed item is uncraftable AND has no chest source AND is not a
  known raw/smelted item, the script gives up and reports.

Run:
    python bridge/autobuild.py
    python bridge/autobuild.py --max-iter 50
"""

import argparse
import subprocess
import sys
import time

from _claude import NAME, UNIT, call_mod, get_inventory_count
from rcon_client import RconClient

POLL = 0.5
WALK_REACH = 2.0
BUILD_REACH = 10
CHEST_REACH = 1.5

# Items that come from mining a resource entity of the same name (sort of) —
# we map the item to the resource entity name and use mine_resource.py.
RAW_RESOURCES = {
    "iron-ore": "iron-ore",
    "copper-ore": "copper-ore",
    "coal": "coal",
    "stone": "stone",
    "uranium-ore": "uranium-ore",
    "wood": None,  # wood comes from chopping trees, not a resource entity
}

# Smeltable plates and what raw ore they come from.
SMELT_INPUT = {
    "iron-plate": "iron-ore",
    "copper-plate": "copper-ore",
    "stone-brick": "stone",
    "steel-plate": "iron-plate",  # steel-plate is recursive (smelt iron-plate)
}


def items_to_dict(items_list):
    """Convert mod's [{name, count}, ...] response to a flat {name: count} dict."""
    if not items_list:
        return {}
    if isinstance(items_list, dict):
        # An empty Lua table can come through as a JSON object
        return {}
    return {x["name"]: int(x["count"]) for x in items_list if "name" in x}


def wait_walk(r, timeout=30):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(POLL)
        s = call_mod(r, "get_walk_status", UNIT)
        if s.get("status") in ("completed", "error", "idle"):
            return s
    call_mod(r, "cancel_walk", UNIT)
    return {"status": "timeout"}


def wait_craft(r, timeout=120):
    deadline = time.monotonic() + timeout
    last = 0
    while time.monotonic() < deadline:
        time.sleep(POLL)
        s = call_mod(r, "get_craft_status", UNIT)
        st = s.get("status")
        if st in ("completed", "error", "idle"):
            return s
        cd = s.get("crafted", 0)
        if cd != last:
            print(f"  [craft {s.get('recipe')}] {cd}/{s.get('requested')}")
            last = cd
    call_mod(r, "cancel_craft", UNIT)
    return {"status": "timeout"}


def take_from_chests(r, item: str, amount: int) -> int:
    """Source as much of `item` as possible from chests (up to amount).
    Returns how many were taken into TEoC's inventory.
    """
    chests_info = call_mod(r, "find_chests_with_item", UNIT, item)
    chests = chests_info.get("chests") or []
    if not chests:
        return 0
    taken = 0
    for c in chests:
        if taken >= amount:
            break
        cx, cy = c["position"]["x"], c["position"]["y"]
        walk_res = call_mod(r, "walk_to", UNIT, cx, cy, CHEST_REACH)
        if walk_res.get("ok") and walk_res.get("status") != "already_at_goal":
            wait_walk(r)
        # Inventory.chest slot index = defines.inventory.chest. In Factorio 2.0 it's 1.
        # The mod's transfer_items uses 'to_chest'/'from_chest' high-level. Let's use that.
        res = call_mod(r, "transfer_items", UNIT, cx, cy, item, amount - taken, "from_chest")
        if res.get("ok"):
            moved = res.get("moved", 0)
            taken += moved
            if moved > 0:
                print(f"  [chest] took {moved} {item} (running total {taken}/{amount})")
        else:
            # chest might be empty now; try next
            pass
    return taken


def can_hand_craft(r, item: str):
    """Return the recipe info if `item` is hand-craftable; else None."""
    res = call_mod(r, "get_recipe", item)
    if not res.get("ok"):
        return None
    if not res.get("hand_craftable"):
        return None
    # also need to ensure no fluid ingredients
    for ing in res.get("ingredients") or []:
        if ing.get("type") == "fluid":
            return None
    return res


def produce(r, item: str, amount: int, depth: int = 0) -> int:
    """Try to put `amount` of `item` into TEoC's inventory by any means.
    Returns total now in inventory of that item (not just gained).
    """
    indent = "  " * depth
    have = get_inventory_count(r, item)
    if have >= amount:
        return have
    need = amount - have
    print(f"{indent}[produce] need {need} more {item} (have {have}, want {amount})")

    # 1. Try chest sourcing
    took = take_from_chests(r, item, need)
    if took > 0:
        have = get_inventory_count(r, item)
        if have >= amount:
            return have
        need = amount - have

    # 2. Try hand-crafting (recursive on ingredients)
    recipe = can_hand_craft(r, item)
    if recipe:
        # ensure ingredients
        for ing in recipe["ingredients"]:
            if ing["type"] == "item":
                ing_need = ing["amount"] * need
                produce(r, ing["name"], ing_need, depth + 1)
        # try to craft; mod will check ingredients again
        print(f"{indent}[craft] crafting {need} x {item}")
        start = call_mod(r, "craft", UNIT, item, need)
        if not start.get("ok"):
            print(f"{indent}[craft] failed to start: {start.get('error')}")
        else:
            cs = wait_craft(r)
            if cs.get("status") != "completed":
                print(f"{indent}[craft] {cs.get('status')}: {cs.get('error')}")
        have = get_inventory_count(r, item)
        if have >= amount:
            return have
        need = amount - have

    # 3. Smelting path
    if item in SMELT_INPUT:
        raw = SMELT_INPUT[item]
        produce(r, raw, need, depth + 1)
        produce(r, "coal", max(1, need // 8 + 1), depth + 1)
        print(f"{indent}[smelt] smelting {need} x {item} from {raw}")
        # Use the smelt.py logic inline via subprocess (cleaner than re-implementing)
        result = subprocess.run(
            [sys.executable, "bridge/smelt.py", raw, item, str(need)],
            capture_output=False,
        )
        have = get_inventory_count(r, item)
        if have >= amount:
            return have
        need = amount - have

    # 4. Mining path (raw resources)
    if item in RAW_RESOURCES:
        resource = RAW_RESOURCES[item]
        if resource is not None:
            print(f"{indent}[mine] mining {need} x {item} from {resource} patches")
            result = subprocess.run(
                [sys.executable, "bridge/mine_resource.py", resource, str(need)],
                capture_output=False,
            )
            have = get_inventory_count(r, item)
            return have

    # Failed
    print(f"{indent}[produce] failed: cannot acquire {need} more {item}")
    return get_inventory_count(r, item)


def find_nearest_ghost(r):
    out = r.command(
        f"/silent-command "
        f"local c = game.get_entity_by_unit_number({UNIT}) "
        "local gs = c.surface.find_entities_filtered{type='entity-ghost', force=c.force} "
        "if #gs == 0 then rcon.print(helpers.table_to_json({count=0})); return end "
        "local best, bd = nil, math.huge "
        "for _, g in pairs(gs) do "
        "  local dx, dy = g.position.x - c.position.x, g.position.y - c.position.y "
        "  local d = dx*dx + dy*dy if d < bd then bd = d; best = g end "
        "end "
        "rcon.print(helpers.table_to_json({count=#gs, x=best.position.x, y=best.position.y}))"
    ).strip()
    import json
    return json.loads(out)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--max-iter", type=int, default=30)
    args = p.parse_args()

    with RconClient() as r:
        for iteration in range(1, args.max_iter + 1):
            info = call_mod(r, "analyze_ghosts", UNIT)
            ghost_count = info.get("ghost_count", 0)
            if ghost_count == 0:
                print(f"[autobuild] done — no ghosts remain. {NAME} finished after {iteration-1} iterations.")
                return 0
            needed = items_to_dict(info.get("items"))
            inv = items_to_dict(call_mod(r, "get_character_inventory", UNIT).get("items"))
            deficit = {k: v - inv.get(k, 0) for k, v in needed.items() if v > inv.get(k, 0)}
            print(f"[autobuild] iter {iteration}: {ghost_count} ghosts remain, "
                  f"{len(deficit)} item types in deficit")
            if deficit:
                # Print top 5 deficits
                top = sorted(deficit.items(), key=lambda kv: -kv[1])[:5]
                for n, c in top:
                    print(f"  - need {c} x {n}")
                # Produce each
                made_progress = False
                for item, count in sorted(deficit.items(), key=lambda kv: -kv[1]):
                    before = get_inventory_count(r, item)
                    produce(r, item, count + before)  # produce up to needed total
                    after = get_inventory_count(r, item)
                    if after > before:
                        made_progress = True
                if not made_progress:
                    print("[autobuild] no progress sourcing items — giving up.")
                    return 4

            # Walk to nearest ghost and build
            ng = find_nearest_ghost(r)
            if ng.get("count", 0) == 0:
                continue
            walk_res = call_mod(r, "walk_to", UNIT, ng["x"], ng["y"], 5.0)
            if walk_res.get("ok") and walk_res.get("status") != "already_at_goal":
                wait_walk(r)
            build = call_mod(r, "build_ghosts_in_range", UNIT, BUILD_REACH)
            built = build.get("built") or []
            missing = build.get("missing") or []
            errors = build.get("errors") or []
            print(f"[autobuild]   built {len(built)}, missing {len(missing)}, errors {len(errors)}")

        print(f"[autobuild] hit max-iter={args.max_iter}, stopping.")
        return 5


if __name__ == "__main__":
    sys.exit(main())
