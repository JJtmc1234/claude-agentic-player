"""
Behavioral cloning for the circuit task using the 2-input demo.
Same structure as bc_masked.py but pulls the circuit demo and
ensures arena is configured for circuits before collecting pairs.

Run:
    python bridge/rl/bc_circuits.py --epochs 500 --reps 25 \
        --save checkpoints/maskppo_bc_circ_v1.zip
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

from _claude import call_mod
from rcon_client import RconClient
from rl.demonstration_circuits_8x8 import as_actions
from rl.grid_extractor import GridExtractor
from rl.masked_env import MaskableFactorioArenaEnv


def mask_fn(env):
    return env.action_masks()


def configure_arena_for_circuits():
    with RconClient() as r:
        spec = {
            'recipe_name': 'electronic-circuit',
            'output_item': 'electronic-circuit',
            'target_output': 10,
            'input_items': [
                {'name': 'iron-plate', 'count': 20},
                {'name': 'copper-cable', 'count': 60},
            ],
            'sim_max_ticks': 3600,  # 60 game-sec, enough for 10 circuits
        }
        res = call_mod(r, 'arena_set_task', spec, interface='claude_rl')
        print(f"[bc-circ] arena_set_task: {res}")
        return res.get('ok', False)


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
    # Final no-op to end the episode after the demo finishes building.
    obss.append(obs.copy())
    acts.append([3, 0, 0])
    env.step([3, 0, 0])
    return np.asarray(obss, dtype=np.float32), np.asarray(acts, dtype=np.int64)


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--epochs', type=int, default=500)
    p.add_argument('--reps', type=int, default=25)
    p.add_argument('--lr', type=float, default=3e-4)
    p.add_argument('--save', default='checkpoints/maskppo_bc_circ_v1.zip')
    args = p.parse_args()

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    if not configure_arena_for_circuits():
        print('[bc-circ] failed to set circuit task; aborting')
        return 1

    print('[bc-circ] instantiating env ...')
    raw_env = MaskableFactorioArenaEnv()
    env = ActionMasker(raw_env, mask_fn)
    demo = list(as_actions())
    print(f'[bc-circ] demo has {len(demo)} actions')

    print(f'[bc-circ] collecting {args.reps} reps ...')
    all_obs, all_acts = [], []
    for rep in range(args.reps):
        obs, acts = collect_demo_pairs(env, demo)
        all_obs.append(obs); all_acts.append(acts)
        if rep == 0:
            print(f'  rep 1: {len(obs)} pairs')
    demo_obs = np.concatenate(all_obs, axis=0)
    demo_acts = np.concatenate(all_acts, axis=0)
    print(f'[bc-circ] total: {len(demo_obs)} pairs, obs {demo_obs.shape}, acts {demo_acts.shape}')

    policy_kwargs = dict(
        features_extractor_class=GridExtractor,
        features_extractor_kwargs=dict(
            width=raw_env.width, height=raw_env.height,
            n_channels=12, n_globals=3, features_dim=128,
        ),
        net_arch=[128],
    )
    model = MaskablePPO(
        'MlpPolicy', env, verbose=0, n_steps=128, batch_size=64,
        learning_rate=args.lr, seed=42, policy_kwargs=policy_kwargs,
    )

    policy = model.policy
    optimizer = th.optim.Adam(policy.parameters(), lr=args.lr)
    obs_t = th.as_tensor(demo_obs, device=policy.device)
    acts_t = th.as_tensor(demo_acts, device=policy.device)

    print(f'[bc-circ] training {args.epochs} epochs ...')
    for epoch in range(args.epochs):
        dist = policy.get_distribution(obs_t)
        log_probs = dist.log_prob(acts_t)
        loss = -log_probs.mean()
        optimizer.zero_grad(); loss.backward(); optimizer.step()
        if epoch == 0 or (epoch + 1) % 50 == 0:
            print(f'[bc-circ] epoch {epoch+1}/{args.epochs}  loss = {loss.item():.4f}')

    print(f'[bc-circ] saving {save_path}')
    model.save(str(save_path))
    env.close()
    print('[bc-circ] done')
    return 0


if __name__ == '__main__':
    sys.exit(main())
