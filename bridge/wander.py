"""
Walk character #454 in a square pattern, narrating each leg in chat.

For each of (north, east, south, west):
  - set_walking(dir, true)
  - sleep SECONDS_PER_LEG seconds
  - set_walking(dir, false)
  - post chat message with the position reached

If the character bumps a wall / water / tree mid-leg, it will sit there
unable to move forward and the next leg starts from wherever it ended.
"""

import sys
import time

from rcon_client import RconClient

UNIT = 454
SECONDS_PER_LEG = 3

LEGS = [
    ("north", "north"),
    ("east", "east"),
    ("south", "south"),
    ("west", "west"),
]


def walk_leg(r: RconClient, direction: str, duration: float) -> None:
    r.command(
        f"/silent-command remote.call('claude','set_walking',{UNIT},"
        f"defines.direction.{direction},true)"
    )
    time.sleep(duration)
    r.command(
        f"/silent-command remote.call('claude','set_walking',{UNIT},"
        f"defines.direction.{direction},false)"
    )


def say(r: RconClient, msg: str) -> None:
    safe = (
        msg.replace("\\", "\\\\")
           .replace("'", "\\'")
           .replace("\r", " ")
           .replace("\n", " ")
    )
    lua = (
        "game.print('[Claude] " + safe + "', "
        "{color={r=0.6,g=0.8,b=1}})"
    )
    r.command("/silent-command " + lua)


def get_pos(r: RconClient):
    out = r.command(
        f"/silent-command local c=game.get_entity_by_unit_number({UNIT}) "
        "if c and c.valid then rcon.print(c.position.x..','..c.position.y) "
        "else rcon.print('') end"
    ).strip()
    if not out:
        return None
    x, y = out.split(",")
    return float(x), float(y)


def main() -> int:
    with RconClient() as r:
        start = get_pos(r)
        if not start:
            print(f"character #{UNIT} not found", file=sys.stderr)
            return 1
        print(f"start at ({start[0]:.2f}, {start[1]:.2f})")
        say(r, f"Walking a square from ({start[0]:.0f}, {start[1]:.0f}).")
        for label, direction in LEGS:
            print(f"walking {label} for {SECONDS_PER_LEG}s ...")
            walk_leg(r, direction, SECONDS_PER_LEG)
            pos = get_pos(r)
            if not pos:
                print("character lost mid-walk", file=sys.stderr)
                return 2
            print(f"  -> ({pos[0]:.2f}, {pos[1]:.2f})")
            say(r, f"After walking {label}: ({pos[0]:.0f}, {pos[1]:.0f}).")
        end = get_pos(r)
        say(r, f"Done. Ended at ({end[0]:.0f}, {end[1]:.0f}).")
        print(f"end at ({end[0]:.2f}, {end[1]:.2f})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
