"""
Run ONE arena episode with a random policy. This is the "first episode."

Sequence:
  1. arena_reset    -> wipe + refill input chest with 100 iron-plate
  2. build phase    -> up to 50 random (entity, tile, direction) actions
                       until a no-op action is rolled OR budget hit
  3. arena_start_simulate(3600 ticks) -> game.speed = 64, world runs
  4. poll arena_get_sim_status until done
  5. arena_score -> compute reward (random policy probably scores -100,
                    that's expected)

Assumes the mod's arena_setup has been called once already this session.

Run:
    python bridge/random_episode.py
"""

import random
import sys
import time

from functools import partial

from _claude import call_mod as _call_mod
from rcon_client import RconClient

# arena_* functions live on the claude_rl interface, not the default 'claude'.
call_mod = partial(_call_mod, interface="claude_rl")

MAX_BUILD_ACTIONS = 50
SIM_MAX_TICKS = 3600
SIM_POLL_INTERVAL = 0.5
SIM_POLL_MAX = 240   # ~120 sec wall-clock budget (with auto_pause off, sim is ~1s at 64x)


def main() -> int:
    random.seed()
    with RconClient() as r:
        # 1. Reset
        reset = call_mod(r, "arena_reset")
        print(f"[reset] {reset}")
        if not reset.get("ok"):
            print(f"[ERROR] reset failed: {reset.get('error')}", file=sys.stderr)
            return 1

        # 2. Random build phase — bias toward BIGGER entities first
        # (place 3x3 assemblers while space is open, fill with belts/inserters later)
        placements = {"belt": 0, "inserter": 0, "assembler": 0}
        invalids = 0
        ENTITIES = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}
        for step in range(1, MAX_BUILD_ACTIONS + 1):
            # Early steps: heavy on assemblers. Later: heavy on belts/inserters.
            if step <= 10:
                weights = [0.15, 0.20, 0.55, 0.10]  # belt, inserter, assembler, no-op
            elif step <= 25:
                weights = [0.30, 0.35, 0.20, 0.15]
            else:
                weights = [0.40, 0.35, 0.05, 0.20]
            entity = random.choices([0, 1, 2, 3], weights=weights, k=1)[0]
            # tile_index range = 16*16 = 256 for the new 16x16 arena
            tile = random.randint(0, 255)
            dir_idx = random.randint(0, 3)
            res = call_mod(r, "arena_place", entity, tile, dir_idx)
            if entity == 3:
                print(f"[build {step}] no-op rolled, ending build phase")
                break
            if res.get("noop"):
                print(f"[build {step}] no-op")
                break
            if res.get("ok"):
                name = {0: "belt", 1: "inserter", 2: "assembler"}[entity]
                placements[name] += 1
            else:
                invalids += 1
        print(
            f"[build phase done] placed: {placements['belt']} belts, "
            f"{placements['inserter']} inserters, {placements['assembler']} assemblers; "
            f"{invalids} invalid attempts"
        )

        # 3. Simulate
        sim = call_mod(r, "arena_start_simulate", SIM_MAX_TICKS)
        print(f"[simulate] start: {sim}")
        for poll in range(SIM_POLL_MAX):
            time.sleep(SIM_POLL_INTERVAL)
            status = call_mod(r, "arena_get_sim_status")
            if not status.get("simulating"):
                print(f"[simulate] done: ticks_taken={status.get('ticks_taken')} "
                      f"output={status.get('final_output')} "
                      f"timed_out={status.get('timed_out')}")
                break
        else:
            print("[simulate] WARNING: poll timed out before sim ended")

        # 4. Score
        score = call_mod(r, "arena_score")
        print(f"[score] total={score.get('total')} reached={score.get('reached')}")
        if score.get("components"):
            for k, v in score["components"].items():
                print(f"          {k}: {v}")
        return 0


if __name__ == "__main__":
    sys.exit(main())
