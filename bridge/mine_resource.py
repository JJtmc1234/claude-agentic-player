"""
TEoC mines N units of a resource by walking patch -> patch -> patch.

Loop:
  1. find_nearest_resource(<name>) -> get one ore tile's position
  2. walk_to that tile (within mining reach)
  3. start_mining(tile_position)
  4. wait until mining done (single tile, ~ore.mining_time seconds)
  5. if we still need more, repeat (a new tile is now nearest because the
     old one was destroyed)

This is bridge-side orchestration over mod primitives. Slow but simple
(many RCON round-trips per tile). A faster version would push the loop
into the mod's on_tick so the character mines a whole patch without
bridge involvement.

Run:
    python bridge/mine_resource.py iron-ore 50
    python bridge/mine_resource.py coal 20
"""

import argparse
import sys
import time

from _claude import NAME, UNIT, call_mod, get_inventory_count
from rcon_client import RconClient

MINING_REACH = 2.0
WALK_TIMEOUT_S = 30
MINE_TIMEOUT_S = 15
POLL = 0.25


def wait_walk(r):
    deadline = time.monotonic() + WALK_TIMEOUT_S
    while time.monotonic() < deadline:
        time.sleep(POLL)
        s = call_mod(r, "get_walk_status", UNIT)
        if s.get("status") in ("completed", "error", "idle"):
            return s
    call_mod(r, "cancel_walk", UNIT)
    return {"status": "timeout"}


def wait_mine(r):
    deadline = time.monotonic() + MINE_TIMEOUT_S
    while time.monotonic() < deadline:
        time.sleep(POLL / 2)
        s = call_mod(r, "get_mining_status", UNIT)
        if not s.get("mining"):
            return s
    return {"status": "timeout"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("resource", help="resource name (iron-ore, copper-ore, coal, stone, ...)")
    p.add_argument("count", type=int, help="target count to gather")
    args = p.parse_args()

    with RconClient() as r:
        start_count = get_inventory_count(r, args.resource)
        target_total = start_count + args.count
        print(f"[mine] {NAME} starting with {start_count} {args.resource}, target +{args.count}")
        no_progress_streak = 0

        while True:
            current = get_inventory_count(r, args.resource)
            gained = current - start_count
            if gained >= args.count:
                print(f"[mine] target reached: +{gained} {args.resource} (total {current})")
                return 0

            info = call_mod(r, "find_nearest_resource", UNIT, args.resource)
            if not info.get("ok"):
                print(f"[mine] {info.get('error')}; got +{gained} of {args.count}", file=sys.stderr)
                return 1
            tx, ty = info["position"]["x"], info["position"]["y"]

            walk_res = call_mod(r, "walk_to", UNIT, tx, ty, MINING_REACH)
            if walk_res.get("ok") and walk_res.get("status") != "already_at_goal":
                wait_walk(r)

            mine_res = call_mod(r, "start_mining", UNIT, tx, ty)
            if not mine_res.get("ok"):
                no_progress_streak += 1
                if no_progress_streak >= 5:
                    print(f"[mine] 5 consecutive failures; aborting at +{gained}", file=sys.stderr)
                    return 2
                continue
            wait_mine(r)
            new_count = get_inventory_count(r, args.resource)
            if new_count == current:
                no_progress_streak += 1
                if no_progress_streak >= 5:
                    print(f"[mine] no inventory progress for 5 tries; aborting at +{gained}", file=sys.stderr)
                    return 3
            else:
                no_progress_streak = 0
                # Print a progress beat every 10 ore gathered, not every tile.
                gained_after = new_count - start_count
                if gained_after // 10 != gained // 10:
                    print(f"[mine] +{gained_after} / {args.count} {args.resource}")


if __name__ == "__main__":
    sys.exit(main())
