"""BC pretrain on imperfect 16x16 transport-belt demo (initial stage)."""

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

from _claude import call_mod
from rcon_client import RconClient
from rl.demonstration_belts_16x16_partial import as_actions
from rl.grid_extractor import GridExtractor
from rl.masked_env import MaskableFactorioArenaEnv


def mask_fn(env):
    return env.action_masks()


def configure_belts_initial():
    """Initial-stage: gears pre-made in input chest (cable task gives copper-
    plate; this gives iron-gear-wheel). Mastery comes later when the agent
    can compose a gear-making chain on its own."""
    with RconClient() as r:
        spec = {
            'recipe_name': 'transport-belt',
            'output_item': 'transport-belt',
            'target_output': 40,  # 2 belts per craft * ~20 crafts; pressures parallelism
            'input_items': [
                {'name': 'iron-plate', 'count': 40},
                {'name': 'iron-gear-wheel', 'count': 40},
            ],
            'sim_max_ticks': 3600,
        }
        return call_mod(r, 'arena_set_task', spec, interface='claude_rl').get('ok', False)


def collect_demo_pairs(env, demo_actions):
    obs, _ = env.reset()
    obss, acts = [], []
    for action in demo_actions:
        obss.append(obs.copy())
        acts.append(list(action))
        next_obs, _r, term, _trunc, _info = env.step(list(action))
        if term:
            break
        obs = next_obs
    return np.asarray(obss, dtype=np.float32), np.asarray(acts, dtype=np.int64)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=2000)
    p.add_argument('--reps', type=int, default=50)
    p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--save', default='checkpoints/maskppo_bc_belt16_v1.zip')
    args = p.parse_args()

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    if not configure_belts_initial():
        print('[bc-belt] failed to set transport-belt task')
        return 1

    raw_env = MaskableFactorioArenaEnv()
    env = ActionMasker(raw_env, mask_fn)
    demo = list(as_actions())
    print(f'[bc-belt] partial demo: {len(demo)} actions')

    print(f'[bc-belt] collecting {args.reps} reps ...')
    all_obs, all_acts = [], []
    for _ in range(args.reps):
        obs, acts = collect_demo_pairs(env, demo)
        all_obs.append(obs); all_acts.append(acts)
    demo_obs = np.concatenate(all_obs, axis=0)
    demo_acts = np.concatenate(all_acts, axis=0)
    print(f'[bc-belt] total: {len(demo_obs)} pairs')

    policy_kwargs = dict(
        features_extractor_class=GridExtractor,
        features_extractor_kwargs=dict(
            width=raw_env.width, height=raw_env.height,
            n_channels=raw_env.n_channels, n_globals=3, features_dim=128,
        ),
        net_arch=[128],
    )
    model = MaskablePPO('MlpPolicy', env, verbose=0, n_steps=128, batch_size=64,
                       learning_rate=args.lr, seed=42, policy_kwargs=policy_kwargs)

    policy = model.policy
    optimizer = th.optim.Adam(policy.parameters(), lr=args.lr)
    obs_t = th.as_tensor(demo_obs, device=policy.device)
    acts_t = th.as_tensor(demo_acts, device=policy.device)

    print(f'[bc-belt] training {args.epochs} epochs (target loss < 1.0 for demo reproduction) ...')
    for epoch in range(args.epochs):
        dist = policy.get_distribution(obs_t)
        log_probs = dist.log_prob(acts_t)
        loss = -log_probs.mean()
        optimizer.zero_grad(); loss.backward(); optimizer.step()
        if epoch == 0 or (epoch + 1) % 100 == 0:
            print(f'[bc-belt] epoch {epoch+1}/{args.epochs}  loss = {loss.item():.4f}')

    print(f'[bc-belt] saving {save_path}')
    model.save(str(save_path))
    env.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
