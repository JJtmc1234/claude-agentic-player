"""
Plot episode rewards over training time from the JSONL log written by
EpisodeJsonlLogger.

Run:
    python bridge/rl/plot_episodes.py --jsonl checkpoints/maskppo_chain_v2_episodes.jsonl
    python bridge/rl/plot_episodes.py --jsonl checkpoints/maskppo_chain_v2_episodes.jsonl --save plot.png

Without --save, prints text summary only (no matplotlib required).
"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path


def load_episodes(jsonl_path: Path) -> list[dict]:
    eps = []
    with jsonl_path.open("r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            eps.append(json.loads(line))
    return eps


def text_summary(eps: list[dict], window: int = 50):
    if not eps:
        print("[plot] no episodes yet")
        return
    rewards = [e["r"] for e in eps]
    lengths = [e["l"] for e in eps]
    print(f"[plot] {len(eps)} episodes")
    print(f"[plot] reward: mean={statistics.mean(rewards):+.2f}  "
          f"min={min(rewards):+.1f}  max={max(rewards):+.1f}  "
          f"stdev={statistics.pstdev(rewards):.1f}")
    print(f"[plot] length: mean={statistics.mean(lengths):.1f}  "
          f"min={min(lengths)}  max={max(lengths)}")
    # Rolling window stats
    if len(rewards) >= window:
        recent = rewards[-window:]
        early = rewards[:window]
        print(f"[plot] first {window} eps mean reward: {statistics.mean(early):+.2f}")
        print(f"[plot] last  {window} eps mean reward: {statistics.mean(recent):+.2f}")
        delta = statistics.mean(recent) - statistics.mean(early)
        print(f"[plot] delta (last - first {window}): {delta:+.2f}")
    # Best episode
    best_idx, best_r = max(enumerate(rewards), key=lambda x: x[1])
    print(f"[plot] best episode: #{best_idx+1}/{len(eps)} reward={best_r:+.1f} "
          f"len={lengths[best_idx]}")


def plot_to_file(eps: list[dict], out_path: Path, window: int = 50):
    try:
        import matplotlib
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("[plot] matplotlib not installed; skipping plot. "
              "pip install matplotlib")
        return
    rewards = [e["r"] for e in eps]
    steps = [e.get("step", i) for i, e in enumerate(eps)]
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.plot(steps, rewards, alpha=0.3, label="per-episode reward")
    # Rolling mean
    if len(rewards) >= window:
        rolling = []
        for i in range(len(rewards)):
            lo = max(0, i - window + 1)
            rolling.append(sum(rewards[lo:i+1]) / (i - lo + 1))
        ax.plot(steps, rolling, label=f"rolling mean (w={window})", linewidth=2)
    ax.set_xlabel("timesteps")
    ax.set_ylabel("episode reward")
    ax.set_title(f"Training rewards ({len(eps)} episodes)")
    ax.axhline(0, color="black", linewidth=0.5, alpha=0.5)
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path)
    print(f"[plot] saved {out_path}")


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--jsonl", required=True, type=Path)
    p.add_argument("--save", type=Path, default=None,
                   help="write a PNG plot here (requires matplotlib)")
    p.add_argument("--window", type=int, default=50,
                   help="rolling-mean window size")
    args = p.parse_args()

    if not args.jsonl.exists():
        print(f"[plot] jsonl not found: {args.jsonl}")
        return 1
    eps = load_episodes(args.jsonl)
    text_summary(eps, window=args.window)
    if args.save:
        plot_to_file(eps, args.save, window=args.window)
    return 0


if __name__ == "__main__":
    sys.exit(main())
