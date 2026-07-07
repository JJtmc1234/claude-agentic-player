"""
Run an arbitrary /silent-command Lua snippet against the server.

This is the "ad-hoc probe" — for quick one-off Lua experiments before
they earn a dedicated script. Pass the Lua code as the argument.

Examples:
    python bridge/_exec.py "rcon.print(game.tick)"
    python bridge/_exec.py "rcon.print(#game.forces.player.technologies)"
"""

import os
import re
import sys
from pathlib import Path

from rcon_client import RconClient


def _ensure_password() -> None:
    """If FACTORIO_RCON_PASSWORD isn't in the environment, resolve it from
    start-server.bat so `python bridge/_exec.py` works standalone (matches the
    scoped allow-rule without needing an env-setting prefix). No-op if already
    set or the bat is unreadable."""
    if os.environ.get("FACTORIO_RCON_PASSWORD"):
        return
    bat = Path(r"C:\FactorioServer\start-server.bat")
    if bat.exists():
        m = re.search(r'--rcon-password "([^"]+)"', bat.read_text())
        if m:
            os.environ["FACTORIO_RCON_PASSWORD"] = m.group(1)


def main() -> int:
    if len(sys.argv) < 2:
        print("usage: python bridge/_exec.py '<lua code>'", file=sys.stderr)
        return 1
    _ensure_password()
    lua = " ".join(sys.argv[1:])
    with RconClient() as r:
        out = r.command("/silent-command " + lua)
    print(out, end="" if out.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
