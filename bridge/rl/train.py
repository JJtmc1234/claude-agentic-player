"""
Train a PPO policy on the Factorio arena.

Uses stable-baselines3's PPO with the default MlpPolicy. Observation is the
flattened grid + globals; action is MultiDiscrete([4, n_tiles, 4]).

This is the v0 training script. Goals:
  - Verify the loop runs without crashing
  - Save a checkpoint
  - Print a reward curve via SB3's verbose logging

Caveats:
  - Episodes are slow when no player is connected (auto_pause clamps speed
    even with our overrides). Connect in-game during training for ~30-60x
    speedup per episode.
  - The default reward is very sparse (most random episodes score -100).
    Don't expect interesting learning in the first 1000 steps; this is
    just plumbing validation.

Run:
    python bridge/rl/train.py --steps 1000
    python bridge/rl/train.py --steps 50000 --save checkpoints/ppo_arena_v0.zip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Make `from rl.env import ...` work whether run from project root or bridge/
_BRIDGE_DIR = Path(__file__).resolve().parent.parent
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

try:
    from stable_baselines3 import PPO
    from stable_baselines3.common.monitor import Monitor
except ImportError as exc:
    raise ImportError(
        "stable-baselines3 not installed. Run: pip install stable-baselines3 gymnasium"
    ) from exc

from rl.env import FactorioArenaEnv  # noqa: E402


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--steps", type=int, default=1000,
                   help="total PPO training timesteps")
    p.add_argument("--save", default="checkpoints/ppo_arena_v0.zip",
                   help="path to save the trained model")
    p.add_argument("--checkpoint", default=None,
                   help="optional starting checkpoint (e.g. bc_warm.zip)")
    p.add_argument("--n-steps", type=int, default=128,
                   help="PPO rollout length per update (default 128 — small "
                        "since episodes here are expensive)")
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--save-every", type=int, default=500,
                   help="save a checkpoint every N timesteps (default 500)")
    args = p.parse_args()

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    print(f"[train] instantiating FactorioArenaEnv ...")
    env = Monitor(FactorioArenaEnv())
    print(f"[train] obs_space={env.observation_space.shape}, "
          f"action_space={env.action_space}")

    if args.checkpoint:
        ckpt = Path(args.checkpoint)
        if not ckpt.exists():
            print(f"[train] checkpoint not found: {ckpt}")
            return 1
        print(f"[train] loading checkpoint {ckpt} ...")
        model = PPO.load(str(ckpt), env=env)
        # Only safe to swap learning_rate after load — n_steps/batch_size would
        # require rebuilding the rollout buffer.
        model.learning_rate = args.learning_rate
    else:
        print(f"[train] creating fresh PPO model ...")
        model = PPO(
            "MlpPolicy",
            env,
            verbose=1,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            seed=args.seed,
            ent_coef=0.1,  # high entropy to encourage exploration past no-op local min
            policy_kwargs=dict(net_arch=[128, 128]),
        )

    print(f"[train] learning for {args.steps} timesteps "
          f"(saving every {args.save_every}) ...")

    # Periodic save callback
    from stable_baselines3.common.callbacks import CheckpointCallback
    ckpt_cb = CheckpointCallback(
        save_freq=args.save_every,
        save_path=str(save_path.parent),
        name_prefix=save_path.stem,
    )

    model.learn(total_timesteps=args.steps, progress_bar=False,
                callback=ckpt_cb)

    print(f"[train] saving final to {save_path}")
    model.save(str(save_path))

    env.close()
    print("[train] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
