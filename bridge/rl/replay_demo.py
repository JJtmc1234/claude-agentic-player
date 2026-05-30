"""
Replay JJ's demonstration layout into the arena via env.step().

This is the "behavioral cloning sanity check": if the demo encoding in
demonstration.LAYOUT is correct, env.reset() + each demo action + a final
no-op should produce a layout that scores like JJ's hand-built design.

If the replayed score is close to a fresh hand-built run, the demo is
faithful and can be used as expert trajectories for actual BC training.

Run:
    python bridge/rl/replay_demo.py
"""

from __future__ import annotations

import sys
from pathlib import Path

# allow imports regardless of cwd
_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from rl.demonstration import as_actions  # noqa: E402
from rl.env import FactorioArenaEnv  # noqa: E402


def main() -> int:
    print(f"[replay] instantiating env ...")
    env = FactorioArenaEnv()
    print(f"[replay] obs_space={env.observation_space.shape}, "
          f"action_space={env.action_space}")

    obs, info = env.reset()
    print(f"[replay] reset done, obs sum={obs.sum():.1f}")

    actions = as_actions()
    print(f"[replay] applying {len(actions)} demo actions ...")
    last_reward = 0.0
    last_info = {}
    for i, a in enumerate(actions, 1):
        obs, reward, terminated, truncated, info = env.step(list(a))
        place = info.get("place", {})
        ok = place.get("ok")
        err = place.get("error") if not ok else None
        tag = "ok" if ok else f"FAIL: {err}"
        print(f"[replay] action {i:2d} ent={a[0]} tile={a[1]:3d} dir={a[2]} -> {tag}")
        if terminated:
            print(f"[replay] env terminated early at action {i}; reward={reward}")
            break
        last_reward = reward
        last_info = info

    # Fire a no-op to trigger simulate + scoring.
    print(f"[replay] firing no-op to start simulate phase ...")
    obs, reward, terminated, truncated, info = env.step([3, 0, 0])
    print(f"[replay] final reward: {reward}")
    if "components" in info:
        for k, v in info["components"].items():
            print(f"           {k}: {v}")
    if info.get("reached") is not None:
        print(f"           reached: {info['reached']}, ticks_taken: {info.get('ticks_taken')}, "
              f"output_count: {info.get('output_count')}")

    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
