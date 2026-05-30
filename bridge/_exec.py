"""
Run an arbitrary /silent-command Lua snippet against the server.

This is the "ad-hoc probe" — for quick one-off Lua experiments before
they earn a dedicated script. Pass the Lua code as the argument.

Examples:
    python bridge/_exec.py "rcon.print(game.tick)"
    python bridge/_exec.py "rcon.print(#game.forces.player.technologies)"
"""

import sys

from rcon_client import RconClient


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python bridge/_exec.py '<lua code>'", file=sys.stderr)
        return 1
    lua = " ".join(sys.argv[1:])
    with RconClient() as r:
        out = r.command("/silent-command " + lua)
    print(out, end="" if out.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
