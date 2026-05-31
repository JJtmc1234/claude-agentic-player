"""
Stage 2 training: cables. Warm-start from a gear-trained checkpoint.

Requires mod 0.9.0 with arena_set_task remote function (see
mod/claude-companion/circuit_changes.lua).

Run (after mod 0.9.0):
    python bridge/rl/train_cables.py \
        --gear-checkpoint checkpoints/gears_final.zip \
        --steps 10000 --save checkpoints/cables_final.zip
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


def configure_arena_for_cables():
    spec = {
        "recipe_name": "copper-cable",
        "output_item": "copper-cable",
        "target_output": 100,  # recipe yields 2 per craft, so 100 is ~50 crafts
        "input_items": [{"name": "copper-plate", "count": 100}],
    }
    with RconClient() as r:
        try:
            res = _call(r, "arena_set_task", spec, interface="claude_rl")
            if res.get("ok"):
                print(f"[train_cables] arena set: {res}")
                return True
            print(f"[train_cables] arena_set_task: {res}")
        except Exception as exc:
            print(f"[train_cables] WARNING: arena_set_task not available: {exc}")
            print("[train_cables]   need mod 0.9.0 (see circuit_changes.lua)")
    return False


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--gear-checkpoint", required=True)
    p.add_argument("--steps", type=int, default=10000)
    p.add_argument("--save", default="checkpoints/cables_final.zip")
    p.add_argument("--save-every", type=int, default=256)
    p.add_argument("--learning-rate", type=float, default=2e-4)
    p.add_argument("--ent-coef", type=float, default=0.05)
    args = p.parse_args()

    gear_ckpt = Path(args.gear_checkpoint)
    if not gear_ckpt.exists():
        print(f"[train_cables] gear checkpoint not found: {gear_ckpt}", file=sys.stderr)
        return 1

    if not configure_arena_for_cables():
        return 2

    save_path = Path(args.save)
    save_path.parent.mkdir(parents=True, exist_ok=True)
    raw_env = MaskableFactorioArenaEnv()
    env = Monitor(ActionMasker(raw_env, mask_fn))

    print(f"[train_cables] loading gear checkpoint {gear_ckpt} ...")
    model = MaskablePPO.load(str(gear_ckpt), env=env)
    model.learning_rate = args.learning_rate
    model.ent_coef = args.ent_coef

    ckpt_cb = CheckpointCallback(
        save_freq=args.save_every,
        save_path=str(save_path.parent),
        name_prefix=save_path.stem,
    )
    print(f"[train_cables] training for {args.steps} timesteps")
    model.learn(total_timesteps=args.steps, callback=ckpt_cb, progress_bar=False)
    model.save(str(save_path))
    env.close()
    print(f"[train_cables] saved -> {save_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
