"""
Train MaskablePPO on the CIRCUIT task, warm-starting from a gear checkpoint.

NOT RUNNABLE YET. Depends on mod 0.9.0 exposing:
  remote.call('claude_rl', 'arena_set_task', task_spec)
where task_spec is something like:
  {
    recipe_name = 'electronic-circuit',
    output_item = 'electronic-circuit',
    target_output = 10,
    input_items = { {name='iron-plate', count=100}, {name='copper-cable', count=100} },
  }

Once that mod function exists, this script:
  1. Calls arena_set_task to switch the arena into circuit mode (does
     NOT change observation/action shapes — just changes recipe + refill).
  2. Loads a gear-trained checkpoint (so the policy already knows
     "place assembler in middle, inserters either side, belts connect
     loaders"); the agent just has to re-learn the reward magnitudes
     and ingredient timing.
  3. Continues training in the same loop.

Run (after mod 0.9.0 is deployed):
    python bridge/rl/train_circuits.py \
        --gear-checkpoint checkpoints/maskppo_v3_best.zip \
        --steps 10000 --save checkpoints/maskppo_circuits_v1.zip
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker
from stable_baselines3.common.callbacks import CheckpointCallback
from stable_baselines3.common.monitor import Monitor

from _claude import call_mod as _call  # noqa: E402
from rcon_client import RconClient  # noqa: E402
from rl.masked_env import MaskableFactorioArenaEnv  # noqa: E402


def mask_fn(env):
    return env.action_masks()


def configure_arena_for_circuits():
    """Send arena_set_task RPC to switch task config. No-op if mod doesn't
    yet expose it; logs a clear warning."""
    spec = {
        "recipe_name": "electronic-circuit",
        "output_item": "electronic-circuit",
        "target_output": 10,
        "input_items": [
            {"name": "iron-plate", "count": 100},
            {"name": "copper-cable", "count": 100},
        ],
    }
    with RconClient() as r:
        try:
            res = _call(r, "arena_set_task", spec, interface="claude_rl")
            if res.get("ok"):
                print(f"[train_circ] arena set for circuit task: {res}")
                return True
            print(f"[train_circ] arena_set_task returned: {res}")
        except Exception as exc:
            print(f"[train_circ] WARNING: arena_set_task not available yet: {exc}")
            print("[train_circ]   You need mod 0.9.0 (see PLAN_CIRCUITS.txt).")
    return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gear-checkpoint", required=True,
                   help="path to a MaskablePPO gear checkpoint to transfer from")
    p.add_argument("--steps", type=int, default=10000)
    p.add_argument("--save", default="checkpoints/maskppo_circuits_v1.zip")
    p.add_argument("--save-every", type=int, default=256)
    p.add_argument("--n-steps", type=int, default=128)
    p.add_argument("--learning-rate", type=float, default=2e-4,
                   help="slightly lower LR than gear training to preserve "
                        "transferred features")
    p.add_argument("--ent-coef", type=float, default=0.05)
    args = p.parse_args()

    gear_ckpt = Path(args.gear_checkpoint)
    if not gear_ckpt.exists():
        print(f"[train_circ] gear checkpoint not found: {gear_ckpt}", file=sys.stderr)
        return 1

    ok = configure_arena_for_circuits()
    if not ok:
        return 2

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)

    print("[train_circ] instantiating env ...")
    raw_env = MaskableFactorioArenaEnv()
    env = Monitor(ActionMasker(raw_env, mask_fn))
    print(f"[train_circ] obs_space={env.observation_space.shape}, "
          f"action_space={env.action_space}")

    print(f"[train_circ] loading gear checkpoint {gear_ckpt} -> transferring weights")
    model = MaskablePPO.load(str(gear_ckpt), env=env)
    model.learning_rate = args.learning_rate
    model.ent_coef = args.ent_coef

    ckpt_cb = CheckpointCallback(
        save_freq=args.save_every,
        save_path=str(save_path.parent),
        name_prefix=save_path.stem,
    )
    print(f"[train_circ] continuing training for {args.steps} timesteps")
    model.learn(total_timesteps=args.steps, callback=ckpt_cb, progress_bar=False)
    model.save(str(save_path))
    env.close()
    print(f"[train_circ] saved final to {save_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
