"""
Custom training callbacks.

BestCheckpointCallback: tracks the rolling ep_rew_mean from sb3's Monitor
wrapper and writes a separate `_best.zip` checkpoint whenever it improves.
Pairs cleanly with CheckpointCallback (which saves every-N-steps regardless).

EpisodeJsonlLogger: writes one JSON line per finished episode to
checkpoints/<name>.jsonl with reward/length/info — easier to parse than the
sb3 table output. Useful for plotting / eval over time.
"""

from __future__ import annotations

import json
from pathlib import Path

from stable_baselines3.common.callbacks import BaseCallback


class BestCheckpointCallback(BaseCallback):
    """Save model to `save_path` whenever the rolling ep_rew_mean improves."""

    def __init__(self, save_path: str, min_episodes: int = 5, verbose: int = 1):
        super().__init__(verbose)
        self.save_path = Path(save_path)
        self.save_path.parent.mkdir(parents=True, exist_ok=True)
        self.min_episodes = min_episodes
        self.best_mean = -float("inf")

    def _on_step(self) -> bool:
        # ep_info_buffer is a deque of dicts {r: reward, l: length, t: time}
        buf = getattr(self.model, "ep_info_buffer", None)
        if not buf or len(buf) < self.min_episodes:
            return True
        mean_r = sum(ep["r"] for ep in buf) / len(buf)
        if mean_r > self.best_mean:
            self.best_mean = mean_r
            self.model.save(str(self.save_path))
            if self.verbose:
                print(f"[best-ckpt] new best ep_rew_mean={mean_r:+.2f} "
                      f"-> {self.save_path}")
        return True


class EpisodeJsonlLogger(BaseCallback):
    """Append a JSON line per finished episode to `path`."""

    def __init__(self, path: str, verbose: int = 0):
        super().__init__(verbose)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._seen_indices = 0  # number of episodes we've already logged

    def _on_step(self) -> bool:
        buf = getattr(self.model, "ep_info_buffer", None)
        if not buf:
            return True
        # ep_info_buffer is bounded; we'd lose episodes if rollouts >100 eps.
        # Realistically each rollout has ~1-10 eps so this is fine.
        new_count = len(buf) - self._seen_indices
        if new_count > 0:
            with self.path.open("a", encoding="utf-8") as f:
                # Take the last new_count entries
                for ep in list(buf)[-new_count:]:
                    line = json.dumps({
                        "r": ep.get("r"),
                        "l": ep.get("l"),
                        "t": ep.get("t"),
                        "step": self.num_timesteps,
                    })
                    f.write(line + "\n")
            self._seen_indices = len(buf)
        return True
