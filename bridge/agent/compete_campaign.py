"""
compete_campaign.py — auto-advancing "Road to Rocket" tournament.

Runs competition rounds back-to-back (each via compete.py) so the race never stalls, laddering
up resource targets. Standings accumulate across every round (compete.py persists them).

This is the CONTINUOUS race JJ asked for, aimed at the rocket: the early rungs are the raw
materials every rocket needs (ore/coal/stone/wood). Production rungs (plates -> gears/circuits
-> rocket parts) get added as the brains' deterministic race executor learns to smelt/craft;
until then this cycles the gathering ladder with escalating goals.

    python bridge/agent/compete_campaign.py                 # loop the ladder forever
    python bridge/agent/compete_campaign.py --once          # one pass through the ladder

Stop with TaskStop / Ctrl-C. Setup (forces + corners) must already be done (setup_arena.py).
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_COMPETE = _HERE / "compete.py"
_SETUP = _HERE / "setup_arena.py"

# (item, goal, round_name) — escalating raw-material ladder toward a rocket's material base.
LADDER = [
    ("copper-ore", 20, "copper start"),
    ("coal",       20, "fuel run"),
    ("stone",      20, "stone start"),
    ("iron-ore",   40, "iron ramp"),
    ("copper-ore", 60, "copper ramp"),
    ("coal",       60, "fuel ramp"),
    ("stone",      60, "brick stock"),
    ("iron-ore",  120, "iron surge"),
    ("wood",       40, "lumber run"),
]
ROUND_SECS = 90        # per-round time cap
GAP_SECS = 8           # breather between rounds


def main() -> int:
    ap = argparse.ArgumentParser(description="auto-advancing Road-to-Rocket race campaign")
    ap.add_argument("--once", action="store_true", help="one pass through the ladder then stop")
    ap.add_argument("--secs", type=int, default=ROUND_SECS, help="per-round time cap")
    args = ap.parse_args()

    stage = 0
    try:
        while True:
            for item, goal, name in LADDER:
                stage += 1
                label = f"Road to Rocket #{stage}: {name}"
                print(f"\n=== {label} — first to {goal} {item} ===", flush=True)
                # FAIR STARTING LINE: reposition everyone to their identical corner centers so
                # between-round drift doesn't hand a camper an advantage.
                subprocess.run([sys.executable, str(_SETUP)], cwd=str(_HERE.parent.parent))
                subprocess.run(
                    [sys.executable, str(_COMPETE),
                     "--item", item, "--goal", str(goal), "--round", label,
                     "--secs", str(args.secs)],
                    cwd=str(_HERE.parent.parent),
                )
                subprocess.run([sys.executable, str(_COMPETE), "--standings"],
                               cwd=str(_HERE.parent.parent))
                time.sleep(GAP_SECS)
            if args.once:
                break
    except KeyboardInterrupt:
        print("[campaign] stopped.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
