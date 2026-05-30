"""
Read chat (and related events) from the Factorio server's console log.

The dedicated server prints lines like
    [CHAT] PlayerName: message text
    [JOIN] PlayerName joined the game
    [LEAVE] PlayerName left the game
    [COMMAND] PlayerName: /silent-command ...
to its console (stdout). With --console-log "<path>" added to the server
launch flags, the same stream gets mirrored to a file we can read here.
See server/start-server.example.bat.

Usage:
    python bridge/chat.py               # print recent event lines from the file
    python bridge/chat.py --follow      # stream new lines as they arrive (Ctrl+C to stop)
    python bridge/chat.py --tail 20     # only show the last 20 event lines
    python bridge/chat.py --all         # don't filter to events — show every line

By default the file path is C:\\FactorioServer\\console.log; override with
the FACTORIO_CONSOLE_LOG environment variable or --path.
"""

from __future__ import annotations

import argparse
import os
import re
import sys
import time
from pathlib import Path

DEFAULT_LOG = Path(
    os.environ.get("FACTORIO_CONSOLE_LOG", r"C:\FactorioServer\console.log")
)

# Tags Factorio prints in brackets for player-visible events. Not exhaustive,
# but covers what we care about for "what's happening on the server."
EVENT_RE = re.compile(
    r"\[(CHAT|SHOUT|WHISPER|JOIN|LEAVE|COMMAND|MUTE|UNMUTE|KICK|BAN|UNBAN|PROMOTE|DEMOTE)\]"
)


def is_event_line(line: str) -> bool:
    return bool(EVENT_RE.search(line))


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Show Factorio server chat/events from the console log."
    )
    p.add_argument("--follow", "-f", action="store_true",
                   help="stream new lines as they arrive (like tail -f)")
    p.add_argument("--tail", "-n", type=int, default=None,
                   help="only show the last N matching lines (one-shot mode)")
    p.add_argument("--all", action="store_true",
                   help="don't filter — print every line in the file")
    p.add_argument("--path", default=str(DEFAULT_LOG),
                   help="path to the console log file")
    return p.parse_args()


def filtered(line: str, show_all: bool) -> str | None:
    line = line.rstrip("\r\n")
    if not line:
        return None
    if show_all:
        return line
    return line if is_event_line(line) else None


def main() -> int:
    args = parse_args()
    log_path = Path(args.path)

    if not log_path.exists():
        if not args.follow:
            print(f"[chat] log file not found: {log_path}", file=sys.stderr)
            print(
                "[chat] add --console-log \"<path>\" to the server launch flags "
                "(see server/start-server.example.bat) and restart.",
                file=sys.stderr,
            )
            return 1
        print(f"[chat] waiting for {log_path} to appear ...", file=sys.stderr)
        while not log_path.exists():
            time.sleep(1.0)

    if not args.follow:
        with log_path.open("r", encoding="utf-8", errors="replace") as fp:
            lines = [shown for ln in fp if (shown := filtered(ln, args.all))]
        if args.tail is not None:
            lines = lines[-args.tail:]
        for ln in lines:
            print(ln)
        return 0

    # Follow mode: seek to end, then poll for new lines.
    with log_path.open("r", encoding="utf-8", errors="replace") as fp:
        fp.seek(0, os.SEEK_END)
        print(f"[chat] tailing {log_path} (Ctrl+C to stop)", file=sys.stderr)
        try:
            while True:
                line = fp.readline()
                if not line:
                    time.sleep(0.3)
                    continue
                shown = filtered(line, args.all)
                if shown is not None:
                    print(shown, flush=True)
        except KeyboardInterrupt:
            print("\n[chat] stopped", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
