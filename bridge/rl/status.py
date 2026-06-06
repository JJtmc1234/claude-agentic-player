"""
One-shot training-status summary for the most recently modified
info.jsonl in checkpoints/. No args needed.

Run:
    python bridge/rl/status.py
"""

from __future__ import annotations

import json
import statistics
import sys
from pathlib import Path


def find_latest(ckpt_dir: Path) -> Path | None:
    candidates = list(ckpt_dir.glob("*_info.jsonl"))
    if not candidates:
        return None
    return max(candidates, key=lambda p: p.stat().st_mtime)


def main() -> int:
    ckpt_dir = Path("checkpoints")
    p = find_latest(ckpt_dir)
    if p is None:
        print("[status] no info.jsonl found in checkpoints/")
        return 1
    print(f"[status] {p.name}")
    infos = []
    with p.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                infos.append(json.loads(line))
    if not infos:
        print("[status] no episodes yet")
        return 0
    n = len(infos)
    rewards = [i.get("r") or 0 for i in infos]
    out_counts = [i.get("output_count") or 0 for i in infos]
    reached = sum(1 for i in infos if i.get("reached"))
    with_out = sum(1 for i in infos if (i.get("output_count") or 0) > 0)
    alive = sum(1 for i in infos
                if (i.get("components") or {}).get("chain_alive") is True)
    # Best ep components
    best_idx = max(range(n), key=lambda i: rewards[i])
    best = infos[best_idx]
    bc = best.get("components") or {}
    print(f"[status] episodes: {n}")
    print(f"[status] reached: {reached}/{n} ({100*reached/n:.1f}%)")
    print(f"[status] any output: {with_out}/{n} ({100*with_out/n:.1f}%)")
    print(f"[status] chain alive: {alive}/{n} ({100*alive/n:.1f}%)")
    print(f"[status] reward: mean={statistics.mean(rewards):+.1f} "
          f"stdev={statistics.pstdev(rewards):.1f} "
          f"min={min(rewards):+.1f} max={max(rewards):+.1f}")
    print(f"[status] max output_count: {max(out_counts)}")
    if n >= 20:
        first20 = statistics.mean(rewards[:20])
        last20 = statistics.mean(rewards[-20:])
        print(f"[status] first 20 mean: {first20:+.1f}  last 20 mean: {last20:+.1f}  "
              f"delta: {last20-first20:+.1f}")
    print()
    print(f"[status] best ep #{best_idx+1}: reward={rewards[best_idx]:+.1f}")
    keys_to_show = ["gears_in_chest", "gears_in_asm", "gears_in_inserters",
                    "gears_on_belts", "gears_total", "chain_alive",
                    "chain_points", "per_gear_reward", "useless_belts",
                    "invalid_actions"]
    for k in keys_to_show:
        v = bc.get(k)
        if v is not None:
            print(f"           {k}: {v}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
