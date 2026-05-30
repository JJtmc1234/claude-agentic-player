"""
Run one episode using the BC warm-started policy. No training, no exploration.

Demonstrates whether BC actually learned anything: if the loss decrease
translated into demo-like actions, the policy should place an assembler,
some inserters, and belts in roughly the right places.

Run:
    python bridge/rl/eval_bc.py
    python bridge/rl/eval_bc.py --checkpoint checkpoints/bc_warm.zip --deterministic
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from stable_baselines3 import PPO  # noqa: E402

from rl.env import FactorioArenaEnv  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--checkpoint", default="checkpoints/bc_warm.zip")
    p.add_argument("--deterministic", action="store_true",
                   help="argmax actions (vs sampling). Default=False (sample).")
    p.add_argument("--max-actions", type=int, default=60)
    args = p.parse_args()

    ckpt = Path(args.checkpoint)
    if not ckpt.exists():
        print(f"[eval] checkpoint not found: {ckpt}")
        return 1

    print(f"[eval] loading {ckpt} ...")
    env = FactorioArenaEnv()
    model = PPO.load(str(ckpt), env=env)
    print(f"[eval] deterministic={args.deterministic}")

    obs, _ = env.reset()
    print("[eval] env reset, running episode ...")
    placements = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}
    counts = {n: 0 for n in placements.values()}
    invalids = 0
    for step in range(1, args.max_actions + 1):
        action, _ = model.predict(obs, deterministic=args.deterministic)
        entity, tile, direction = int(action[0]), int(action[1]), int(action[2])
        obs, reward, terminated, truncated, info = env.step([entity, tile, direction])
        name = placements[entity]
        place = info.get("place", {})
        if place.get("noop") or name == "no-op":
            print(f"[eval] step {step:2d}: no-op rolled, ending build phase")
            break
        if place.get("ok"):
            counts[name] += 1
            print(f"[eval] step {step:2d}: place {name:<10s} tile={tile:3d} dir={direction}")
        else:
            invalids += 1
            err = place.get("error", "unknown")
            print(f"[eval] step {step:2d}: INVALID {name:<10s} tile={tile:3d} dir={direction} ({err})")
        if terminated:
            break

    # If we ran out of build budget without no-op, env auto-finishes on next step.
    if not terminated:
        obs, reward, terminated, truncated, info = env.step([3, 0, 0])

    print(f"\n[eval] build phase done — {counts['belt']} belts, "
          f"{counts['inserter']} inserters, {counts['assembler']} assemblers, "
          f"{invalids} invalid attempts")
    print(f"[eval] final reward: {reward}")
    if "components" in info:
        for k, v in info["components"].items():
            print(f"           {k}: {v}")
    if info.get("reached") is not None:
        print(f"           reached: {info['reached']}, ticks: {info.get('ticks_taken')}, "
              f"output: {info.get('output_count')}")
    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
