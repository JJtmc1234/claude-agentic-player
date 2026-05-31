"""
Stage 4 training: two-step production chain (cables + circuits).

Requires mod 0.10.0 with support for INTERMEDIATE outputs in the reward
(credit copper-cable production along the way, not just final circuit).

Two assemblers in the arena:
  - One crafting copper-cable from copper-plate
  - One crafting electronic-circuit from iron-plate + copper-cable
The agent must route intermediates from one to the other.

Warm-start from circuits-trained checkpoint.

Run (after mod 0.10.0 + bigger arena maybe):
    python bridge/rl/train_chain.py \
        --circuits-checkpoint checkpoints/circuits_final.zip \
        --steps 20000 --save checkpoints/chain_final.zip
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


def configure_arena_for_chain():
    # The mod will need to support multi-recipe arenas in 0.10.0 — meaning
    # multiple assemblers can have their recipe controlled. For now we
    # send a spec assuming the mod accepts it.
    spec = {
        "task": "chain",
        "recipes": ["copper-cable", "electronic-circuit"],  # cables -> circuits
        "output_item": "electronic-circuit",
        "intermediate_items": ["copper-cable"],  # reward partial production
        "target_output": 5,
        "input_items": [
            {"name": "copper-plate", "count": 100},
            {"name": "iron-plate", "count": 100},
        ],
    }
    with RconClient() as r:
        try:
            res = _call(r, "arena_set_task", spec, interface="claude_rl")
            if res.get("ok"):
                print(f"[train_chain] arena set: {res}")
                return True
            print(f"[train_chain] arena_set_task: {res}")
        except Exception as exc:
            print(f"[train_chain] WARNING: arena_set_task / chain support not available: {exc}")
            print("[train_chain]   need mod 0.10.0")
    return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--circuits-checkpoint", required=True)
    p.add_argument("--steps", type=int, default=20000)
    p.add_argument("--save", default="checkpoints/chain_final.zip")
    p.add_argument("--save-every", type=int, default=512)
    p.add_argument("--learning-rate", type=float, default=1e-4,
                   help="even lower LR — chain is fragile, preserve transferred policy")
    p.add_argument("--ent-coef", type=float, default=0.05)
    args = p.parse_args()

    ckpt = Path(args.circuits_checkpoint)
    if not ckpt.exists():
        print(f"[train_chain] circuit checkpoint not found: {ckpt}", file=sys.stderr)
        return 1

    if not configure_arena_for_chain():
        return 2

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    raw_env = MaskableFactorioArenaEnv()
    env = Monitor(ActionMasker(raw_env, mask_fn))

    print(f"[train_chain] loading circuit checkpoint {ckpt} ...")
    model = MaskablePPO.load(str(ckpt), env=env)
    model.learning_rate = args.learning_rate
    model.ent_coef = args.ent_coef

    ckpt_cb = CheckpointCallback(
        save_freq=args.save_every,
        save_path=str(save_path.parent),
        name_prefix=save_path.stem,
    )
    print(f"[train_chain] training for {args.steps} timesteps")
    model.learn(total_timesteps=args.steps, callback=ckpt_cb, progress_bar=False)
    model.save(str(save_path))
    env.close()
    print(f"[train_chain] saved -> {save_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
