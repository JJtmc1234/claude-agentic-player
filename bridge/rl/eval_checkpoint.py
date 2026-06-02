"""
Evaluate a MaskablePPO checkpoint by running N deterministic episodes
against the live Factorio arena. Reports reward distribution + headline
stats so we can compare checkpoints quantitatively.

Run:
    python bridge/rl/eval_checkpoint.py --checkpoint checkpoints/maskppo_chain_v1.zip --episodes 20
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from rl.masked_env import MaskableFactorioArenaEnv


def mask_fn(env):
    return env.action_masks()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--episodes", type=int, default=10)
    p.add_argument("--deterministic", action="store_true", default=True)
    p.add_argument("--stochastic", action="store_false", dest="deterministic")
    p.add_argument("--trace-actions", action="store_true",
                   help="print each (entity, tile, dir) the policy picks per step")
    args = p.parse_args()

    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        print(f"[eval] checkpoint not found: {ckpt}")
        return 1

    print(f"[eval] loading {ckpt}")
    raw_env = MaskableFactorioArenaEnv()
    env = ActionMasker(raw_env, mask_fn)
    model = MaskablePPO.load(str(ckpt), env=env)

    rewards = []
    reached_count = 0
    output_counts = []
    chain_pts_list = []

    for ep in range(args.episodes):
        obs, info = env.reset()
        ep_reward = 0.0
        done = False
        actions_taken = []
        while not done:
            masks = env.action_masks()
            action, _ = model.predict(obs, action_masks=masks,
                                      deterministic=args.deterministic)
            actions_taken.append(tuple(int(x) for x in action))
            obs, r, terminated, truncated, info = env.step(action)
            ep_reward += float(r)
            done = terminated or truncated
        if args.trace_actions:
            ENT = {0: "belt", 1: "ins", 2: "asm", 3: "noop"}
            DIR = ["N", "E", "S", "W"]
            print(f"[eval]   trace ep {ep+1}:")
            for i, (ec, ti, d) in enumerate(actions_taken, 1):
                col = ti % raw_env.width
                row = ti // raw_env.width
                print(f"           {i:2d}: {ENT.get(ec):<5s} col={col} row={row} dir={DIR[d]}")
        rewards.append(ep_reward)
        reached = info.get("reached", False)
        out_count = info.get("output_count", 0)
        components = info.get("components") or {}
        chain_pts = components.get("chain_points", 0) if isinstance(components, dict) else 0
        if reached:
            reached_count += 1
        output_counts.append(out_count or 0)
        chain_pts_list.append(chain_pts)
        print(f"[eval] ep {ep+1}/{args.episodes}: reward={ep_reward:+.1f}  "
              f"gears={out_count}  reached={reached}  chain_pts={chain_pts}  "
              f"ticks={info.get('ticks_taken')}")

    env.close()
    print()
    print(f"[eval] === summary over {args.episodes} episodes ===")
    print(f"[eval] reward: mean={statistics.mean(rewards):+.1f}  "
          f"stdev={statistics.pstdev(rewards):.1f}  "
          f"min={min(rewards):+.1f}  max={max(rewards):+.1f}")
    print(f"[eval] gears produced: mean={statistics.mean(output_counts):.1f}  "
          f"max={max(output_counts)}")
    print(f"[eval] reached target: {reached_count}/{args.episodes} "
          f"({100 * reached_count / args.episodes:.0f}%)")
    print(f"[eval] chain_pts: mean={statistics.mean(chain_pts_list):.1f}  "
          f"max={max(chain_pts_list)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
