"""
Plot reward-component breakdown over episodes from the info JSONL.

Stacked area chart of how each reward component (per_gear, reached_bonus,
chain_pts, activity, useless_belt_penalty, etc.) contributes to total
reward across training. Tells us at a glance whether the agent is
producing gears, farming chain bonuses, or just losing penalties.

Run:
    python bridge/rl/plot_components.py --jsonl checkpoints/maskppo_chain_v9_info.jsonl
    python bridge/rl/plot_components.py --jsonl ... --save reports/chain_v9_components.png
"""

from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path


# Components we care about, grouped into "positive contributors" and
# "penalties" for color-coding.
POS_KEYS = [
    'reached_bonus', 'per_gear_reward', 'speed_bonus',
    'chain_points', 'activity_reward', 'functional_inserter_bonus',
]
NEG_KEYS = ['base', 'useless_belt_penalty', 'invalid_action_penalty']


def load_infos(path: Path) -> list[dict]:
    out = []
    with path.open('r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            out.append(json.loads(line))
    return out


def text_summary(infos: list[dict]):
    n = len(infos)
    if n == 0:
        print('[plot] no data')
        return
    reached = sum(1 for i in infos if i.get('reached'))
    with_gear = sum(1 for i in infos if (i.get('output_count') or 0) > 0)
    chain_alive = sum(1 for i in infos
                      if (i.get('components') or {}).get('chain_alive') is True)
    rewards = [i.get('r') or 0 for i in infos]
    print(f'[plot] episodes: {n}')
    print(f'[plot] reached target: {reached}/{n} ({100*reached/n:.0f}%)')
    print(f'[plot] produced any gear: {with_gear}/{n}')
    print(f'[plot] chain alive: {chain_alive}/{n}')
    print(f'[plot] reward mean/max: {sum(rewards)/n:+.1f} / {max(rewards):+.1f}')
    # Component means over last 20% of episodes
    tail_start = max(0, n - max(1, n // 5))
    tail = infos[tail_start:]
    comp_sums = defaultdict(float)
    for ep in tail:
        c = ep.get('components') or {}
        for k, v in c.items():
            if isinstance(v, (int, float)):
                comp_sums[k] += v
    print(f'[plot] mean component values over last {len(tail)} eps:')
    for k in sorted(comp_sums):
        avg = comp_sums[k] / len(tail)
        marker = ''
        if k in POS_KEYS:
            marker = '+'
        elif k in NEG_KEYS:
            marker = '-'
        print(f'    {marker} {k}: {avg:+.2f}')


def plot_to_png(infos: list[dict], out_path: Path, window: int = 30):
    try:
        import matplotlib
        matplotlib.use('Agg')
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError:
        print('[plot] matplotlib not installed; skipping PNG')
        return
    n = len(infos)
    if n < 2:
        print('[plot] not enough data')
        return
    eps = np.arange(n)
    # Build per-component arrays
    series = {k: np.zeros(n) for k in POS_KEYS + NEG_KEYS}
    for i, ep in enumerate(infos):
        c = ep.get('components') or {}
        for k in series:
            v = c.get(k)
            if isinstance(v, (int, float)):
                series[k][i] = v
    # Rolling mean
    def rolling(arr):
        out = np.zeros_like(arr, dtype=float)
        for i in range(len(arr)):
            lo = max(0, i - window + 1)
            out[i] = arr[lo:i+1].mean()
        return out
    fig, (ax_pos, ax_neg) = plt.subplots(2, 1, figsize=(11, 7), sharex=True)
    # Positive components (stacked)
    bottom = np.zeros(n)
    for k in POS_KEYS:
        smooth = rolling(series[k])
        ax_pos.fill_between(eps, bottom, bottom + smooth, alpha=0.55, label=k)
        bottom = bottom + smooth
    ax_pos.set_ylabel('reward (rolling mean)')
    ax_pos.set_title(f'positive contributors (window={window}) — {n} episodes')
    ax_pos.legend(loc='upper left', fontsize=8)
    ax_pos.grid(alpha=0.3)
    # Negative
    bottom = np.zeros(n)
    for k in NEG_KEYS:
        smooth = rolling(series[k])
        ax_neg.fill_between(eps, bottom, bottom + smooth, alpha=0.55, label=k)
        bottom = bottom + smooth
    ax_neg.set_ylabel('penalty (rolling mean)')
    ax_neg.set_title('penalties (lower bar = more penalty)')
    ax_neg.set_xlabel('episode')
    ax_neg.legend(loc='lower left', fontsize=8)
    ax_neg.grid(alpha=0.3)
    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path)
    print(f'[plot] saved {out_path}')


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--jsonl', required=True, type=Path)
    p.add_argument('--save', type=Path, default=None)
    p.add_argument('--window', type=int, default=30)
    args = p.parse_args()
    if not args.jsonl.exists():
        print(f'[plot] not found: {args.jsonl}')
        return 1
    infos = load_infos(args.jsonl)
    text_summary(infos)
    if args.save:
        plot_to_png(infos, args.save, window=args.window)
    return 0


if __name__ == '__main__':
    sys.exit(main())
