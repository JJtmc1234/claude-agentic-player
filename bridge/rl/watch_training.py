"""
Live-poll a training run's info.jsonl and print summary stats every
few seconds. No RCON — read-only on the file, safe to run alongside
training.

Run:
    python bridge/rl/watch_training.py --jsonl checkpoints/maskppo_cable16_v3_info.jsonl --window 30
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
import time
from pathlib import Path


def load_infos(path: Path) -> list[dict]:
    out = []
    try:
        with path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    out.append(json.loads(line))
    except (FileNotFoundError, json.JSONDecodeError):
        pass
    return out


def summarize(infos: list[dict], window: int = 30) -> dict:
    if not infos:
        return {}
    rewards = [i.get("r") or 0 for i in infos]
    reached = sum(1 for i in infos if i.get("reached"))
    with_out = sum(1 for i in infos if (i.get("output_count") or 0) > 0)
    alive = sum(1 for i in infos
                if (i.get("components") or {}).get("chain_alive") is True)
    out_counts = [i.get("output_count") or 0 for i in infos]
    last = rewards[-window:] if len(rewards) >= window else rewards
    first = rewards[:window] if len(rewards) >= window else rewards
    return {
        "n": len(infos),
        "best_r": max(rewards),
        "mean_r": statistics.mean(rewards),
        "first_window_mean": statistics.mean(first) if first else 0,
        "last_window_mean": statistics.mean(last) if last else 0,
        "reached_pct": 100 * reached / len(infos),
        "with_out_pct": 100 * with_out / len(infos),
        "alive_pct": 100 * alive / len(infos),
        "max_out": max(out_counts) if out_counts else 0,
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--jsonl", required=True, type=Path)
    p.add_argument("--interval", type=float, default=20.0,
                   help="seconds between summary prints")
    p.add_argument("--window", type=int, default=30)
    p.add_argument("--once", action="store_true",
                   help="print one summary and exit")
    args = p.parse_args()

    print(f"[watch] tailing {args.jsonl} every {args.interval}s ...")
    last_n = -1
    while True:
        infos = load_infos(args.jsonl)
        s = summarize(infos, window=args.window)
        if not s:
            print("[watch] no episodes yet ...")
        elif s["n"] != last_n:
            delta = s["last_window_mean"] - s["first_window_mean"]
            print(f"[watch] eps={s['n']:4d}  "
                  f"alive={s['alive_pct']:5.1f}%  out>0={s['with_out_pct']:5.1f}%  "
                  f"reached={s['reached_pct']:5.1f}%  "
                  f"best={s['best_r']:+8.1f}  "
                  f"mean={s['mean_r']:+7.1f}  "
                  f"first->last={s['first_window_mean']:+6.1f}->{s['last_window_mean']:+6.1f} (d={delta:+5.1f})  "
                  f"max_out={s['max_out']}")
            last_n = s["n"]
        if args.once:
            return 0
        try:
            time.sleep(args.interval)
        except KeyboardInterrupt:
            return 0


if __name__ == "__main__":
    sys.exit(main())
