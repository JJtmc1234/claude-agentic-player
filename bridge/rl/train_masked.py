"""
Train MaskablePPO on the arena, using per-step action masks so the agent
never picks tiles that are already occupied. Dramatically more sample-
efficient than vanilla PPO.

Run:
    python bridge/rl/train_masked.py --steps 5000 --save checkpoints/maskppo_v1.zip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from sb3_contrib import MaskablePPO
from sb3_contrib.common.maskable.callbacks import MaskableEvalCallback  # noqa: F401
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.callbacks import CallbackList, CheckpointCallback
from stable_baselines3.common.monitor import Monitor

from rl.callbacks import BestCheckpointCallback, EpisodeJsonlLogger
from rl.info_logger import InfoJsonlWrapper
from rl.masked_env import MaskableFactorioArenaEnv


def mask_fn(env):
    """ActionMasker needs a callable that returns the mask given env."""
    return env.action_masks()


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--steps", type=int, default=3000)
    p.add_argument("--save", default="checkpoints/maskppo_v1.zip")
    p.add_argument("--save-every", type=int, default=128)
    p.add_argument("--n-steps", type=int, default=128)
    p.add_argument("--batch-size", type=int, default=64)
    p.add_argument("--learning-rate", type=float, default=3e-4)
    p.add_argument("--ent-coef", type=float, default=0.15,
                   help="entropy coefficient — kept higher (0.15) for curiosity so "
                        "the policy doesn't collapse to a single strategy")
    p.add_argument("--checkpoint", default=None,
                   help="resume from a saved MaskablePPO checkpoint")
    p.add_argument("--policy", choices=["mlp", "cnn"], default="mlp",
                   help="mlp = flat 128-128 (legacy); cnn = GridExtractor (recommended for fresh runs)")
    p.add_argument("--target-kl", type=float, default=None,
                   help="early-stop each rollout's policy updates if KL exceeds this. "
                        "Useful after BC warm-start (keeps policy close to imprint).")
    args = p.parse_args()

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    print("[train_masked] instantiating env ...")
    raw_env = MaskableFactorioArenaEnv()
    info_path = str(save_path.with_name(save_path.stem + "_info.jsonl"))
    env = Monitor(ActionMasker(InfoJsonlWrapper(raw_env, info_path), mask_fn))
    print(f"[train_masked] obs_space={env.observation_space.shape}, "
          f"action_space={env.action_space}")

    if args.checkpoint and Path(args.checkpoint).exists():
        print(f"[train_masked] loading checkpoint {args.checkpoint}")
        model = MaskablePPO.load(args.checkpoint, env=env)
        model.learning_rate = args.learning_rate
        model.ent_coef = args.ent_coef
        if args.target_kl is not None:
            model.target_kl = args.target_kl
    else:
        print(f"[train_masked] creating fresh MaskablePPO (policy={args.policy}) ...")
        if args.policy == "cnn":
            from rl.grid_extractor import GridExtractor
            policy_kwargs = dict(
                features_extractor_class=GridExtractor,
                features_extractor_kwargs=dict(
                    width=raw_env.width, height=raw_env.height,
                    n_channels=12, n_globals=3, features_dim=128,
                ),
                net_arch=[128],
            )
        else:
            policy_kwargs = dict(net_arch=[128, 128])
        model = MaskablePPO(
            "MlpPolicy",
            env,
            verbose=1,
            n_steps=args.n_steps,
            batch_size=args.batch_size,
            learning_rate=args.learning_rate,
            ent_coef=args.ent_coef,
            seed=42,
            policy_kwargs=policy_kwargs,
        )

    ckpt_cb = CheckpointCallback(
        save_freq=args.save_every,
        save_path=str(save_path.parent),
        name_prefix=save_path.stem,
    )
    best_cb = BestCheckpointCallback(
        save_path=str(save_path.with_name(save_path.stem + "_best.zip")),
    )
    jsonl_cb = EpisodeJsonlLogger(
        path=str(save_path.with_name(save_path.stem + "_episodes.jsonl")),
    )
    callbacks = CallbackList([ckpt_cb, best_cb, jsonl_cb])
    print(f"[train_masked] learning for {args.steps} timesteps "
          f"(saving every {args.save_every}; best-ckpt + jsonl on) ...")
    model.learn(total_timesteps=args.steps, callback=callbacks, progress_bar=False)

    print(f"[train_masked] saving final to {save_path}")
    model.save(str(save_path))
    env.close()
    print("[train_masked] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
