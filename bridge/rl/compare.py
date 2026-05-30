"""
Evaluate a trained policy checkpoint by running N episodes and reporting
mean reward + summary of placements.

Use this to compare different PPO checkpoints, or compare PPO vs BC vs
the hand demo.

Run:
    python bridge/rl/compare.py --checkpoint checkpoints/bc_warm.zip --episodes 3
    python bridge/rl/compare.py --checkpoint checkpoints/ppo_v2_2500_steps.zip --episodes 5 --deterministic
"""

from __future__ import annotations

import argparse
import statistics
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from stable_baselines3 import PPO  # noqa: E402

from rl.env import FactorioArenaEnv  # noqa: E402


def run_one_episode(model, env, deterministic: bool, max_actions: int = 60):
    obs, _ = env.reset()
    placements = {0: 0, 1: 0, 2: 0}  # belt, inserter, assembler
    invalids = 0
    for _ in range(max_actions):
        action, _ = model.predict(obs, deterministic=deterministic)
        entity = int(action[0])
        obs, reward, terminated, truncated, info = env.step(
            [entity, int(action[1]), int(action[2])]
        )
        place = info.get("place", {})
        if place.get("noop") or entity == 3:
            break
        if place.get("ok"):
            placements[entity] = placements.get(entity, 0) + 1
        else:
            invalids += 1
        if terminated:
            break
    if not terminated:
        obs, reward, terminated, truncated, info = env.step([3, 0, 0])
    return {
        "reward": float(reward),
        "belts": placements.get(0, 0),
        "inserters": placements.get(1, 0),
        "assemblers": placements.get(2, 0),
        "invalids": invalids,
        "reached": info.get("reached"),
        "output_count": info.get("output_count"),
        "ticks_taken": info.get("ticks_taken"),
        "chain": info.get("components", {}).get("chain"),
    }


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", required=True)
    p.add_argument("--episodes", type=int, default=3)
    p.add_argument("--deterministic", action="store_true")
    args = p.parse_args()

    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        print(f"[compare] not found: {ckpt}")
        return 1

    env = FactorioArenaEnv()
    print(f"[compare] loading {ckpt} ...")
    model = PPO.load(str(ckpt), env=env)
    print(f"[compare] running {args.episodes} episodes "
          f"(deterministic={args.deterministic}) ...\n")

    rewards = []
    for i in range(1, args.episodes + 1):
        r = run_one_episode(model, env, args.deterministic)
        rewards.append(r["reward"])
        print(f"ep {i}: reward={r['reward']:7.1f}  "
              f"placed={r['belts']}b/{r['inserters']}i/{r['assemblers']}a  "
              f"invalid={r['invalids']}  "
              f"out={r['output_count']}  chain={r['chain']}")

    print()
    print(f"[compare] mean reward over {len(rewards)} eps: {statistics.mean(rewards):.1f}")
    if len(rewards) > 1:
        print(f"[compare] stdev: {statistics.stdev(rewards):.1f}, "
              f"min: {min(rewards):.1f}, max: {max(rewards):.1f}")
    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
