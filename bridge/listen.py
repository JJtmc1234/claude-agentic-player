"""
Read in-game chat from the claude-companion mod's buffer.

Unlike bridge/chat.py (which tails the server's console.log file), this
talks to the mod's remote interface and gets a structured list of messages
with tick numbers and player names — no log parsing.

Calls remote.call("claude", "drain_chat") which returns AND clears the buffer.
So this is a "since last drain" stream. Don't run two drainers in parallel
unless you want to race.

Run:
    python bridge/listen.py             # one-shot drain + print
    python bridge/listen.py --follow    # poll every 0.5s, stream as it arrives
"""

import argparse
import json
import sys
import time

from rcon_client import RconClient


DRAIN_LUA = (
    "rcon.print(helpers.table_to_json(remote.call('claude','drain_chat')))"
)


def drain(r: RconClient) -> list[dict]:
    out = r.command("/silent-command " + DRAIN_LUA).strip()
    if not out:
        return []
    if out.startswith("Cannot execute command"):
        raise RuntimeError(f"server error: {out}")
    data = json.loads(out)
    msgs = data.get("messages")
    # An empty Lua table serializes to JSON {} not [], so msgs can be either
    # an empty dict or a list. Both fall through as no-messages.
    if not msgs:
        return []
    if isinstance(msgs, dict):
        # If somehow keyed by integer-strings, take values in order.
        return [msgs[k] for k in sorted(msgs, key=lambda x: int(x))]
    return msgs


def format_msg(m: dict) -> str:
    return f"[tick {m['tick']}] {m['player']}: {m['message']}"


def main() -> int:
    p = argparse.ArgumentParser(description="Read in-game chat via the mod buffer.")
    p.add_argument("--follow", "-f", action="store_true",
                   help="poll every 0.5s, print new chat as it arrives (Ctrl+C stops)")
    args = p.parse_args()

    with RconClient() as r:
        if not args.follow:
            for m in drain(r):
                print(format_msg(m))
            return 0
        print("[listen] polling every 0.5s (Ctrl+C to stop)", file=sys.stderr)
        try:
            while True:
                for m in drain(r):
                    print(format_msg(m), flush=True)
                time.sleep(0.5)
        except KeyboardInterrupt:
            print("\n[listen] stopped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
