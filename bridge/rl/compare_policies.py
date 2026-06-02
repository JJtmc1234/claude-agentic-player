"""
Run two checkpoints side-by-side and report whether they build the same
layout or different ones. Both episodes use stochastic sampling (so the
same checkpoint can produce different outputs across runs).

Output: action diffs per step + final reward / output count for each
checkpoint, repeated N times to detect within-checkpoint variance.

Run:
    python bridge/rl/compare_policies.py \
        --a checkpoints/maskppo_bc_v4.zip \
        --b checkpoints/maskppo_bc_v5b.zip \
        --repeats 5
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

from rl.masked_env import MaskableFactorioArenaEnv


def mask_fn(env):
    return env.action_masks()


ENT = {0: "belt", 1: "ins", 2: "asm", 3: "noop"}
DIR = ["N", "E", "S", "W"]


def run_episode(env, model, deterministic):
    obs, _ = env.reset()
    actions = []
    ep_reward = 0.0
    done = False
    while not done:
        masks = env.action_masks()
        action, _ = model.predict(obs, action_masks=masks,
                                  deterministic=deterministic)
        actions.append(tuple(int(x) for x in action))
        obs, r, term, trunc, info = env.step(action)
        ep_reward += float(r)
        done = term or trunc
    return actions, ep_reward, info


def action_str(a, width):
    ec, ti, d = a
    col = ti % width
    row = ti // width
    return f"{ENT.get(ec):<4s}({col},{row}){DIR[d]}"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--a", required=True)
    p.add_argument("--b", required=True)
    p.add_argument("--repeats", type=int, default=3)
    p.add_argument("--deterministic", action="store_true", default=False,
                   help="default uses stochastic to surface within-policy variance")
    args = p.parse_args()

    raw_env = MaskableFactorioArenaEnv()
    env = ActionMasker(raw_env, mask_fn)
    model_a = MaskablePPO.load(args.a, env=env)
    model_b = MaskablePPO.load(args.b, env=env)
    w = raw_env.width

    print(f"=== A: {args.a}")
    print(f"=== B: {args.b}")
    print(f"=== mode: {'deterministic' if args.deterministic else 'stochastic'}, repeats={args.repeats}\n")

    for rep in range(args.repeats):
        print(f"--- Repeat {rep+1}/{args.repeats} ---")
        a_actions, a_r, a_info = run_episode(env, model_a, args.deterministic)
        b_actions, b_r, b_info = run_episode(env, model_b, args.deterministic)
        n = max(len(a_actions), len(b_actions))
        print(f"  {'step':<5} {'A':<22} {'B':<22} {'match':<5}")
        match_count = 0
        for i in range(n):
            a_act = a_actions[i] if i < len(a_actions) else None
            b_act = b_actions[i] if i < len(b_actions) else None
            a_s = action_str(a_act, w) if a_act else "-"
            b_s = action_str(b_act, w) if b_act else "-"
            ok = "yes" if a_act == b_act else "NO"
            if a_act == b_act and a_act is not None:
                match_count += 1
            print(f"  {i+1:<5} {a_s:<22} {b_s:<22} {ok:<5}")
        gear_a = a_info.get("output_count") or 0
        gear_b = b_info.get("output_count") or 0
        print(f"  A reward={a_r:+.1f} gears={gear_a}  |  B reward={b_r:+.1f} gears={gear_b}  "
              f"|  {match_count}/{n} step matches\n")

    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
