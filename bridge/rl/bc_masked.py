"""
Behavioral cloning for MaskablePPO with CNN policy. Replays the 8x8
demonstration, collects (obs, action) pairs, then runs supervised
cross-entropy training to bias the policy toward "place this layout".

Run:
    python bridge/rl/bc_masked.py --epochs 100 --save checkpoints/maskppo_bc_v2.zip

The output checkpoint is shape-compatible with train_masked.py --policy cnn,
so PPO fine-tuning resumes cleanly:

    python bridge/rl/train_masked.py --checkpoint checkpoints/maskppo_bc_v2.zip \
        --steps 20000 --save checkpoints/maskppo_chain_v3.zip --policy cnn
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
import torch as th

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from rl.demonstration_8x8 import as_actions
from rl.grid_extractor import GridExtractor
from rl.masked_env import MaskableFactorioArenaEnv


def mask_fn(env):
    return env.action_masks()


def collect_demo_pairs(env) -> tuple[np.ndarray, np.ndarray]:
    """Replay demo actions and capture (obs_before_action, action). Append
    a final no-op so BC learns "after the demo is built, end the episode."
    Critical: env's MIN_ACTIONS_BEFORE_NOOP must be <= len(demo) or the
    no-op gets penalized and the trajectory keeps going."""
    obs, _ = env.reset()
    obss, acts = [], []
    demo = as_actions()
    for action in demo:
        obss.append(obs.copy())
        acts.append(list(action))
        next_obs, _r, term, _trunc, _info = env.step(list(action))
        if term:
            break
        obs = next_obs
    # Append final no-op action so the policy learns to STOP after demo.
    obss.append(obs.copy())
    acts.append([3, 0, 0])
    # Actually fire the no-op so env returns to a clean state.
    env.step([3, 0, 0])
    return np.asarray(obss, dtype=np.float32), np.asarray(acts, dtype=np.int64)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=100)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--save", default="checkpoints/maskppo_bc_v2.zip")
    p.add_argument("--reps", type=int, default=10,
                   help="repeat the demo this many times (more reps = stronger imprint)")
    args = p.parse_args()

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    print("[bc] instantiating env ...")
    raw_env = MaskableFactorioArenaEnv()
    env = ActionMasker(raw_env, mask_fn)

    print(f"[bc] collecting demo trajectory x{args.reps} ...")
    all_obs, all_acts = [], []
    for i in range(args.reps):
        obs, acts = collect_demo_pairs(env)
        if len(obs) == 0:
            print(f"[bc] rep {i+1}: 0 actions (env terminated early?)")
            continue
        all_obs.append(obs)
        all_acts.append(acts)
        print(f"[bc] rep {i+1}/{args.reps}: {len(obs)} pairs")
    if not all_obs:
        print("[bc] no data collected; aborting")
        return 1

    demo_obs = np.concatenate(all_obs, axis=0)
    demo_acts = np.concatenate(all_acts, axis=0)
    print(f"[bc] total: {len(demo_obs)} pairs, obs {demo_obs.shape}, acts {demo_acts.shape}")

    print("[bc] creating MaskablePPO (CNN policy) ...")
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

    print(f"[bc] training for {args.epochs} epochs ...")
    for epoch in range(args.epochs):
        dist = policy.get_distribution(obs_t)
        log_probs = dist.log_prob(acts_t)
        loss = -log_probs.mean()
        optimizer.zero_grad()
        loss.backward()
        optimizer.step()
        if epoch == 0 or (epoch + 1) % 10 == 0:
            print(f"[bc] epoch {epoch+1:3d}/{args.epochs}  loss = {loss.item():.4f}")

    print(f"[bc] saving {save_path}")
    model.save(str(save_path))
    env.close()
    print("[bc] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
