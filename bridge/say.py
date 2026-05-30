"""
Send a chat message into the game from 'Claude'.

The message shows up in everyone's chat box, prefixed with [Claude] and
colored light blue so it's visually distinct from human players.

Run:
    set FACTORIO_RCON_PASSWORD=<same password as in start-server.bat>
    python bridge/say.py hello world from claude
"""

import sys

from rcon_client import RconClient


def main() -> int:
    if len(sys.argv) < 2:
        print('usage: python bridge/say.py "your message here"', file=sys.stderr)
        return 1
    msg = " ".join(sys.argv[1:])

    # Escape so the message is safe to drop inside a Lua single-quoted string.
    # Order matters: escape backslashes first, then single quotes.
    escaped = msg.replace("\\", "\\\\").replace("'", "\\'")
    # Strip stray newlines — Lua single-quoted strings can't contain raw \n.
    escaped = escaped.replace("\r", " ").replace("\n", " ")

    lua = (
        "game.print('[Claude] " + escaped + "', "
        "{color={r=0.6,g=0.8,b=1}})"
    )

    with RconClient() as r:
        out = r.command("/silent-command " + lua).strip()

    if out:
        # If the Lua errored, the server returns the error text here.
        print(f"[say] server: {out}", file=sys.stderr)
        return 2
    print("[say] sent")
    return 0


if __name__ == "__main__":
    sys.exit(main())
