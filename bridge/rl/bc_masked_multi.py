"""
Behavioral cloning on MULTIPLE demos. Collects (obs, action) pairs from
each demo variant, mixes them, trains supervised CE loss.

Why: BC on a single trajectory produces a rigid policy that builds the
exact same layout every time. Training on multiple equivalent solutions
teaches the policy "the chain PATTERN" rather than "this exact tile
sequence" — so PPO downstream has freedom to find variants without
catastrophically forgetting how chains work.

Adding a new demo: write a `demonstration_<name>.py` exposing
`as_actions()` and add it to DEMO_MODULES below.

Run:
    python bridge/rl/bc_masked_multi.py --epochs 500 --reps 20 \
        --save checkpoints/maskppo_bc_v5.zip
"""

from __future__ import annotations

import argparse
import importlib
import sys
from pathlib import Path

import numpy as np
import torch as th

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from rl.grid_extractor import GridExtractor
from rl.masked_env import MaskableFactorioArenaEnv

DEMO_MODULES = [
    "rl.demonstration_8x8",
    "rl.demonstration_8x8_v2",
]


def mask_fn(env):
    return env.action_masks()


def collect_demo_pairs(env, demo_actions) -> tuple[np.ndarray, np.ndarray]:
    """Reset env, replay demo, return (obs_before_each_action, action_taken).
    Appends a final no-op so BC learns to STOP after the demo (env's
    MIN_ACTIONS_BEFORE_NOOP must be <= len(demo))."""
    obs, _ = env.reset()
    obss, acts = [], []
    for action in demo_actions:
        obss.append(obs.copy())
        acts.append(list(action))
        next_obs, _r, term, _trunc, _info = env.step(list(action))
        if term:
            break
        obs = next_obs
    obss.append(obs.copy())
    acts.append([3, 0, 0])
    env.step([3, 0, 0])
    return np.asarray(obss, dtype=np.float32), np.asarray(acts, dtype=np.int64)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=500)
    p.add_argument("--reps", type=int, default=20,
                   help="reps PER demo (total trajectories = reps * #demos)")
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--save", default="checkpoints/maskppo_bc_v5.zip")
    args = p.parse_args()

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    print("[bc-multi] instantiating env ...")
    raw_env = MaskableFactorioArenaEnv()
    env = ActionMasker(raw_env, mask_fn)

    print(f"[bc-multi] loading {len(DEMO_MODULES)} demo modules:")
    demos = []
    for modname in DEMO_MODULES:
        mod = importlib.import_module(modname)
        actions = list(mod.as_actions())
        print(f"  - {modname}: {len(actions)} actions")
        demos.append(actions)

    print(f"[bc-multi] collecting {args.reps} reps per demo "
          f"({args.reps * len(demos)} total) ...")
    all_obs, all_acts = [], []
    for rep in range(args.reps):
        for demo_idx, demo_actions in enumerate(demos):
            obs, acts = collect_demo_pairs(env, demo_actions)
            if len(obs):
                all_obs.append(obs)
                all_acts.append(acts)
                if rep == 0:
                    print(f"  demo {demo_idx}: {len(obs)} pairs")

    if not all_obs:
        print("[bc-multi] no data collected; aborting")
        return 1
    demo_obs = np.concatenate(all_obs, axis=0)
    demo_acts = np.concatenate(all_acts, axis=0)
    print(f"[bc-multi] total: {len(demo_obs)} pairs, "
          f"obs {demo_obs.shape}, acts {demo_acts.shape}")

    print("[bc-multi] creating MaskablePPO (CNN policy) ...")
    policy_kwargs = dict(
        features_extractor_class=GridExtractor,
        features_extractor_kwargs=dict(
            width=raw_env.width, height=raw_env.height,
            n_channels=12, n_globals=3, features_dim=128,
        ),
        net_arch=[128],
    )
    model = MaskablePPO(
        "MlpPolicy",
        env,
        verbose=0,
        n_steps=128,
        batch_size=64,
        learning_rate=args.lr,
        seed=42,
        policy_kwargs=policy_kwargs,
    )

    policy = model.policy
    optimizer = th.optim.Adam(policy.parameters(), lr=args.lr)
    obs_t = th.as_tensor(demo_obs, device=policy.device)
    acts_t = th.as_tensor(demo_acts, device=policy.device)

    print(f"[bc-multi] training {args.epochs} epochs ...")
    for epoch in range(args.epochs):
        dist = policy.get_distribution(obs_t)
        log_probs = dist.log_prob(acts_t)
        loss = -log_probs.mean()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        if epoch == 0 or (epoch + 1) % 50 == 0:
            print(f"[bc-multi] epoch {epoch+1:3d}/{args.epochs}  loss = {loss.item():.4f}")

    print(f"[bc-multi] saving {save_path}")
    model.save(str(save_path))
    env.close()
    print("[bc-multi] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
