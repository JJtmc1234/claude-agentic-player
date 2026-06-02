"""
Env wrapper that writes one JSONL line per finished episode containing
the rich `info` dict from `_finish_episode` (reward components, chain stats,
output count, reached flag, ticks_taken). Pairs with EpisodeJsonlLogger
(which only captures r/l/t from Monitor).

Why a separate wrapper instead of extending EpisodeJsonlLogger: the sb3
callback only sees Monitor's compacted dict, not the raw info from the env.
Hook at the env layer to capture everything.

Wrap order in train_masked.py:
    raw_env = MaskableFactorioArenaEnv()
    env = ActionMasker(InfoJsonlWrapper(Monitor(raw_env), path), mask_fn)
"""

from __future__ import annotations

import json
from pathlib import Path

import gymnasium as gym


class InfoJsonlWrapper(gym.Wrapper):
    def __init__(self, env, path: str):
        super().__init__(env)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._episode_idx = 0
        self._episode_reward = 0.0
        self._episode_len = 0

    def reset(self, *, seed=None, options=None):
        obs, info = self.env.reset(seed=seed, options=options)
        self._episode_reward = 0.0
        self._episode_len = 0
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = self.env.step(action)
        self._episode_reward += float(reward)
        self._episode_len += 1
        if terminated or truncated:
            self._episode_idx += 1
            line = {
                "ep": self._episode_idx,
                "r": self._episode_reward,
                "l": self._episode_len,
                "reached": info.get("reached"),
                "output_count": info.get("output_count"),
                "ticks_taken": info.get("ticks_taken"),
                "actions_used": info.get("actions_used"),
                "components": info.get("components"),
            }
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(line) + "\n")
        return obs, reward, terminated, truncated, info

    # ActionMasker calls env.action_masks() through this wrapper; forward
    # explicitly so the gym.Wrapper attribute-passthrough doesn't get in
    # the way.
    def action_masks(self):
        return self.env.action_masks()
