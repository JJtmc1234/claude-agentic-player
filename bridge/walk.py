"""
Drive character #454 in a given direction until it stops making progress.

Sequence per run:
  1. set_walking(<dir>, true)
  2. poll position every 0.5s
  3. when 4 consecutive polls show <0.1 tile of movement, declare stuck
  4. set_walking(<dir>, false)
  5. report start, stop, distance traveled

Run:
    python bridge/walk.py north
    python bridge/walk.py south
    python bridge/walk.py east
    python bridge/walk.py west
    python bridge/walk.py north-east       # accepts hyphen or underscore

Optional second arg: a different unit_number (default 454).
"""

import sys
import time

from rcon_client import RconClient

UNIT_DEFAULT = 454
POLL_INTERVAL = 0.5
STUCK_THRESHOLD = 0.1
STUCK_CONSECUTIVE = 4
MAX_POLLS = 120

# (dx, dy) unit vectors for each direction. Factorio convention: +x = east,
# +y = south. Used only to report distance/heading after the run.
DIR_VECTOR = {
    "north":      ( 0, -1),
    "north_east": ( 1, -1),
    "east":       ( 1,  0),
    "south_east": ( 1,  1),
    "south":      ( 0,  1),
    "south_west": (-1,  1),
    "west":       (-1,  0),
    "north_west": (-1, -1),
}


def normalize_direction(s: str) -> str:
    return s.lower().replace("-", "_")


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
    if len(sys.argv) < 2:
        print("usage: python bridge/walk.py <direction> [unit_number]", file=sys.stderr)
        print(f"directions: {', '.join(DIR_VECTOR)}", file=sys.stderr)
        return 1
    direction = normalize_direction(sys.argv[1])
    if direction not in DIR_VECTOR:
        print(f"unknown direction {direction!r}", file=sys.stderr)
        return 1
    unit = int(sys.argv[2]) if len(sys.argv) >= 3 else UNIT_DEFAULT

    with RconClient() as r:
        start = get_pos(r, unit)
        if not start:
            print(f"character #{unit} not found", file=sys.stderr)
            return 2
        print(f"start at ({start[0]:.2f}, {start[1]:.2f}), walking {direction}")

        r.command(
            f"/silent-command remote.call('claude','set_walking',{unit},"
            f"defines.direction.{direction},true)"
        )

        last = start
        stuck = 0
        polls_done = 0
        for i in range(MAX_POLLS):
            time.sleep(POLL_INTERVAL)
            polls_done = i + 1
            now = get_pos(r, unit)
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
            f"/silent-command remote.call('claude','set_walking',{unit},"
            f"defines.direction.{direction},false)"
        )
        final = get_pos(r, unit)
        if not final:
            print("character lost while stopping", file=sys.stderr)
            return 3

        dx, dy = final[0] - start[0], final[1] - start[1]
        dvx, dvy = DIR_VECTOR[direction]
        forward = dx * dvx + dy * dvy  # projection onto the intended direction
        print(
            f"stopped at ({final[0]:.2f}, {final[1]:.2f}) "
            f"after {polls_done} polls (~{polls_done * POLL_INTERVAL:.1f}s)"
        )
        print(f"forward {forward:.1f} tiles {direction}, drift ({dx:+.1f}, {dy:+.1f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
