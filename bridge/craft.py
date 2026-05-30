"""
Have TEoC hand-craft N of a recipe.

Calls mod's craft(recipe, count), which registers a job; the mod's on_tick
loop deducts ingredients and adds products one item at a time over the
recipe's craft time (recipe.energy * 60 ticks per item). This is our own
crafting loop because character.begin_crafting() is engine-gated to
player-controlled characters (same as the original mining problem).

Run:
    python bridge/craft.py iron-gear-wheel 10
    python bridge/craft.py electronic-circuit 5
"""

import argparse
import sys
import time

from _claude import NAME, UNIT, call_mod
from rcon_client import RconClient

POLL = 0.5


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("recipe", help="recipe name (iron-gear-wheel, electronic-circuit, etc.)")
    p.add_argument("count", type=int, help="how many to craft")
    args = p.parse_args()

    with RconClient() as r:
        start = call_mod(r, "craft", UNIT, args.recipe, args.count)
        if not start.get("ok"):
            print(f"[craft] {start.get('error')}", file=sys.stderr)
            return 1
        eta = start["eta_ticks"]
        print(f"[craft] {NAME} crafting {args.count} x {args.recipe}, "
              f"~{eta} ticks (~{eta/60:.1f}s)")

        last_crafted = 0
        while True:
            time.sleep(POLL)
            s = call_mod(r, "get_craft_status", UNIT)
            st = s.get("status")
            if st == "idle":
                print("[craft] status went idle without completion (race?)", file=sys.stderr)
                return 2
            if st == "completed":
                gained = s.get("gained") or []
                gained_str = ", ".join(f"{g['count']} {g['name']}" for g in gained)
                print(f"[craft] done: {gained_str}")
                return 0
            if st == "error":
                print(f"[craft] error: {s.get('error')} (crafted {s.get('crafted')}/{s.get('requested')})",
                      file=sys.stderr)
                return 3
            # status == "crafting"
            if s.get("crafted", 0) != last_crafted:
                last_crafted = s["crafted"]
                print(f"[craft]   {last_crafted}/{args.count} done")


if __name__ == "__main__":
    sys.exit(main())
