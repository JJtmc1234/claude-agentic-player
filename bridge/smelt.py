"""
TEoC uses nearby furnaces to smelt ore into plates.

Strategy:
  1. Find furnaces within radius of TEoC (defaults to 30 tiles).
  2. For each furnace: walk to it, top up fuel (coal), insert ore.
  3. Wait briefly for furnaces to cook.
  4. For each furnace: walk to it, take the output plates.
  5. Repeat until plates in inventory >= target.

This is a simple round-robin. A smarter implementation would parallelize
better, balance ore distribution by furnace state, etc. For now, simple
loop. Assumes character has coal + ore in inventory before running.

Run:
    python bridge/smelt.py iron-ore iron-plate 50      # use iron-ore -> iron-plate
    python bridge/smelt.py copper-ore copper-plate 50
    python bridge/smelt.py stone stone-brick 20
"""

import argparse
import sys
import time

from _claude import NAME, UNIT, call_mod, get_inventory_count
from rcon_client import RconClient

POLL = 0.25
WALK_REACH = 1.5
COAL_PER_LOAD = 2
ORE_PER_LOAD = 5

# defines.inventory values that we actually pass to the mod's insert/take.
# These are stable integer constants from Factorio 2.0.
INV_FUEL = 1
INV_FURNACE_SOURCE = 2
INV_FURNACE_RESULT = 3


FIND_FURNACES_LUA = f"""
local c = game.get_entity_by_unit_number({UNIT})
if not c or not c.valid then
  rcon.print(helpers.table_to_json({{error='no character'}})); return
end
local fs = c.surface.find_entities_filtered{{
  type = 'furnace', position = c.position, radius = 30,
}}
local out = {{}}
for _, f in ipairs(fs) do
  if f.valid then
    table.insert(out, {{
      name = f.name,
      position = {{ x = f.position.x, y = f.position.y }},
      unit_number = f.unit_number,
    }})
  end
end
rcon.print(helpers.table_to_json({{ok=true, furnaces=out}}))
"""


def wait_walk(r, timeout=20):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        time.sleep(POLL)
        s = call_mod(r, "get_walk_status", UNIT)
        if s.get("status") in ("completed", "error", "idle"):
            return s
    call_mod(r, "cancel_walk", UNIT)
    return {"status": "timeout"}


def find_furnaces(r):
    import json
    out = r.command("/silent-command " + FIND_FURNACES_LUA).strip()
    return json.loads(out)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("ore", help="ore item name (iron-ore, copper-ore, stone)")
    p.add_argument("plate", help="plate item name (iron-plate, copper-plate, stone-brick)")
    p.add_argument("count", type=int, help="target plates to produce")
    args = p.parse_args()

    with RconClient() as r:
        info = find_furnaces(r)
        if info.get("error"):
            print(f"[smelt] {info['error']}", file=sys.stderr)
            return 1
        furnaces = info.get("furnaces") or []
        if not furnaces:
            print("[smelt] no furnaces within 30 tiles of TEoC", file=sys.stderr)
            return 2
        print(f"[smelt] found {len(furnaces)} furnaces near {NAME}")

        start_plates = get_inventory_count(r, args.plate)
        target_total = start_plates + args.count
        print(f"[smelt] starting with {start_plates} {args.plate}, target +{args.count}")

        while True:
            plates = get_inventory_count(r, args.plate)
            gained = plates - start_plates
            if gained >= args.count:
                print(f"[smelt] target reached: +{gained} {args.plate} (total {plates})")
                return 0

            ore_left = get_inventory_count(r, args.ore)
            coal_left = get_inventory_count(r, "coal")
            if ore_left <= 0:
                print(f"[smelt] out of {args.ore} (have {plates}/{target_total} plates); stop", file=sys.stderr)
                return 3

            # Round 1: load fuel + ore into each furnace.
            for f in furnaces:
                fx, fy = f["position"]["x"], f["position"]["y"]
                walk_res = call_mod(r, "walk_to", UNIT, fx, fy, WALK_REACH)
                if walk_res.get("ok") and walk_res.get("status") != "already_at_goal":
                    wait_walk(r)
                if coal_left > 0:
                    call_mod(r, "insert_into_entity", UNIT, fx, fy, "coal", COAL_PER_LOAD, INV_FUEL)
                    coal_left = get_inventory_count(r, "coal")
                if ore_left > 0:
                    call_mod(r, "insert_into_entity", UNIT, fx, fy, args.ore, ORE_PER_LOAD, INV_FURNACE_SOURCE)
                    ore_left = get_inventory_count(r, args.ore)
                if ore_left <= 0:
                    break

            # Wait for the furnaces to do their thing. Stone-furnace: 3.2s per
            # plate. Loaded 5 ore => 16s for that furnace's batch.
            print(f"[smelt] loaded furnaces; cooking ~16s ...")
            time.sleep(16)

            # Round 2: harvest output from each furnace.
            for f in furnaces:
                fx, fy = f["position"]["x"], f["position"]["y"]
                walk_res = call_mod(r, "walk_to", UNIT, fx, fy, WALK_REACH)
                if walk_res.get("ok") and walk_res.get("status") != "already_at_goal":
                    wait_walk(r)
                call_mod(r, "take_from_entity", UNIT, fx, fy, args.plate, 99, INV_FURNACE_RESULT)

            plates_after = get_inventory_count(r, args.plate)
            print(f"[smelt]   round done: +{plates_after - plates} this round, "
                  f"total gained {plates_after - start_plates} / {args.count}")


if __name__ == "__main__":
    sys.exit(main())
