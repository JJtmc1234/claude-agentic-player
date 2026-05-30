"""
Minimal Behavioral Cloning: train a PPO policy on JJ's demonstration.

Steps:
  1. Instantiate env.
  2. Collect (obs, action) pairs by replaying the demo (one trajectory).
     Each obs is what the policy would see BEFORE taking the demo action.
  3. Build a fresh PPO model.
  4. For N epochs, do supervised CE loss between the policy's action logits
     and the demo's actions. This nudges the policy toward demo behavior.
  5. Save the model. PPO training can resume from this checkpoint.

This is intentionally tiny. With one demo trajectory of ~14 actions, we
won't get a master policy, but the network will be biased toward
"actually placing entities" instead of spamming no-ops. PPO will fine-tune.

Run:
    python bridge/rl/bc.py --epochs 50 --save checkpoints/bc_warm.zip
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

from stable_baselines3 import PPO  # noqa: E402

from rl.demonstration import as_actions  # noqa: E402
from rl.env import FactorioArenaEnv  # noqa: E402


def collect_demo_pairs(env: FactorioArenaEnv) -> tuple[np.ndarray, np.ndarray]:
    """Replay the demo, returning (observations, actions) as numpy arrays."""
    obs, _ = env.reset()
    obss, acts = [], []
    demo_actions = as_actions()
    for action in demo_actions:
        obss.append(obs.copy())
        acts.append(list(action))
        next_obs, _r, terminated, _trunc, _info = env.step(list(action))
        if terminated:
            break
        obs = next_obs
    # Fire one final no-op so the env is in a clean state.
    env.step([3, 0, 0])
    return np.asarray(obss, dtype=np.float32), np.asarray(acts, dtype=np.int64)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--epochs", type=int, default=50)
    p.add_argument("--lr", type=float, default=3e-4)
    p.add_argument("--save", default="checkpoints/bc_warm.zip")
    args = p.parse_args()

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    print("[bc] instantiating env ...")
    env = FactorioArenaEnv()
    print("[bc] collecting demo trajectory ...")
    demo_obs, demo_acts = collect_demo_pairs(env)
    print(f"[bc] collected {len(demo_obs)} (obs, action) pairs")
    print(f"[bc] obs shape: {demo_obs.shape}, acts shape: {demo_acts.shape}")

    print("[bc] creating PPO model ...")
    model = PPO(
        "MlpPolicy",
        env,
        verbose=0,
        n_steps=128,
        batch_size=64,
        learning_rate=args.lr,
        seed=42,
        policy_kwargs=dict(net_arch=[128, 128]),
    )

    policy = model.policy
    optimizer = th.optim.Adam(policy.parameters(), lr=args.lr)

    obs_t = th.as_tensor(demo_obs, device=policy.device)
    acts_t = th.as_tensor(demo_acts, device=policy.device)  # shape (N, 3)

    print(f"[bc] training for {args.epochs} epochs on demo ...")
    for epoch in range(args.epochs):
        # Forward pass: get the distribution over actions for the demo states.
        dist = policy.get_distribution(obs_t)
        # MultiDiscrete: log_prob accepts the joint action.
        log_probs = dist.log_prob(acts_t)
        loss = -log_probs.mean()

        optimizer.zero_grad()
        loss.backward()
        optimizer.step()

        if epoch == 0 or (epoch + 1) % 10 == 0:
            print(f"[bc] epoch {epoch+1:3d}/{args.epochs}  loss = {loss.item():.4f}")

    print(f"[bc] saving warm-started model to {save_path}")
    model.save(str(save_path))
    env.close()
    print("[bc] done")
    return 0


if __name__ == "__main__":
    sys.exit(main())
