"""
Drive character #454 north until it stops making progress.

Sequence:
  1. set_walking(north, true)
  2. poll position every 0.5s
  3. when 4 consecutive polls show <0.1 tile of movement, declare stuck
  4. set_walking(north, false)
  5. report start, stop, distance traveled

This is the first real driving test of the mod's set_walking interface.
"""

import sys
import time

from rcon_client import RconClient

UNIT = 454                # the character spawned at (0,0)
POLL_INTERVAL = 0.5       # seconds between position checks
STUCK_THRESHOLD = 0.1     # tiles moved in one poll => not stuck
STUCK_CONSECUTIVE = 4     # ~2 seconds of no progress to declare stuck
MAX_POLLS = 120           # safety cap: ~1 minute of polling


def get_pos(r: RconClient, unit: int):
    cmd = (
        f"/silent-command local e=game.get_entity_by_unit_number({unit}) "
        "if e and e.valid then rcon.print(e.position.x..','..e.position.y) "
        "else rcon.print('') end"
    )
    out = r.command(cmd).strip()
    if not out:
        return None
    x, y = out.split(",")
    return float(x), float(y)


def main() -> int:
    with RconClient() as r:
        start = get_pos(r, UNIT)
        if not start:
            print(f"character #{UNIT} not found", file=sys.stderr)
            return 1
        print(f"start at ({start[0]:.2f}, {start[1]:.2f})")

        r.command(
            f"/silent-command remote.call('claude','set_walking',{UNIT},"
            "defines.direction.north,true)"
        )

        last = start
        stuck = 0
        polls_done = 0
        for i in range(MAX_POLLS):
            time.sleep(POLL_INTERVAL)
            polls_done = i + 1
            now = get_pos(r, UNIT)
            if not now:
                print("lost character mid-walk", file=sys.stderr)
                break
            dist = max(abs(now[0] - last[0]), abs(now[1] - last[1]))
            if dist < STUCK_THRESHOLD:
                stuck += 1
                if stuck >= STUCK_CONSECUTIVE:
                    break
            else:
                stuck = 0
            last = now

        r.command(
            f"/silent-command remote.call('claude','set_walking',{UNIT},"
            "defines.direction.north,false)"
        )
        final = get_pos(r, UNIT)
        if not final:
            print("character lost while stopping", file=sys.stderr)
            return 2

        traveled = start[1] - final[1]  # north = -y, so positive = traveled north
        sideways = final[0] - start[0]
        print(
            f"stopped at ({final[0]:.2f}, {final[1]:.2f}) "
            f"after {polls_done} polls (~{polls_done * POLL_INTERVAL:.1f}s)"
        )
        print(f"traveled {traveled:.1f} tiles north, {sideways:+.1f} sideways")
    return 0


if __name__ == "__main__":
    sys.exit(main())
