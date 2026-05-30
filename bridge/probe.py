"""
Tiny end-to-end ping for the Claude Agentic Player bridge.

Connects to the Factorio server over RCON, asks it the game version and
current tick, and prints the result. If this prints sensible numbers,
the whole pipe (Python -> RCON -> server -> Lua -> game state) is alive.

Run:
    set FACTORIO_RCON_PASSWORD=<same password as in start-server.bat>
    python bridge/probe.py
"""

import sys

from rcon_client import RconClient


def main() -> int:
    with RconClient() as r:
        print(f"[bridge] connected to {r.host}:{r.port}")
        version = r.command("/version").strip()
        snapshot = r.command(
            "/silent-command rcon.print("
            "'tick=' .. game.tick "
            ".. ' surfaces=' .. #game.surfaces "
            ".. ' players_online=' .. #game.connected_players)"
        ).strip()
    print(f"[bridge] server version: {version}")
    print(f"[bridge] {snapshot}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
