"""
Gymnasium environment wrapping the claude-companion arena.

Maps RL primitives to remote.call('claude_rl', ...) on the mod:
  reset(): arena_reset -> initial observation
  step(action): arena_place; on no-op or budget, arena_start_simulate
                + poll arena_get_sim_status, then arena_score

Action space: MultiDiscrete([4, W*H, 4])
  - entity_choice (0=belt, 1=inserter, 2=assembler, 3=no-op)
  - tile_index (row-major across the arena)
  - direction (0=N, 1=E, 2=S, 3=W)

Observation: flat float vector of shape (W*H*12 + 3,)
  - 12 channels per tile (one-hot for entity type + direction)
  - 3 globals: tick_in_episode, output_count, input_count
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

import numpy as np

try:
    import gymnasium as gym
    from gymnasium import spaces
except ImportError as exc:
    raise ImportError(
        "gymnasium not installed. Run: pip install gymnasium stable-baselines3"
    ) from exc

# Allow `python bridge/rl/env.py` from anywhere by adjusting sys.path.
_BRIDGE_DIR = Path(__file__).resolve().parent.parent
if str(_BRIDGE_DIR) not in sys.path:
    sys.path.insert(0, str(_BRIDGE_DIR))

from _claude import call_mod as _call_mod  # noqa: E402
from rcon_client import RconClient  # noqa: E402


def call_rl(r, fn, *args):
    return _call_mod(r, fn, *args, interface="claude_rl")


SIM_POLL_INTERVAL = 0.1   # seconds; faster polling for short sims
SIM_POLL_MAX = 600        # ~60 sec wall (sim should usually take ~1s)
MAX_BUILD_ACTIONS = 25         # reduced from 50 so episodes are shorter
MIN_ACTIONS_BEFORE_NOOP = 6    # matches demo length so BC-imprinted policy can end cleanly
SIM_MAX_TICKS_OVERRIDE = 3600  # 60 game-sec; enough for 10 circuits w/ 2-input chain (gears finish in ~1450)


class FactorioArenaEnv(gym.Env):
    """One Factorio dedicated server, one arena, one PPO env."""

    metadata = {"render_modes": []}

    def __init__(self):
        super().__init__()
        self._rcon = RconClient()
        self._rcon.connect()
        # Pull arena constants once at startup.
        c = call_rl(self._rcon, "arena_get_constants")
        if not c.get("ok"):
            raise RuntimeError(f"arena_get_constants failed: {c.get('error')} "
                               "(did you forget to call arena_setup first?)")
        self.width = c["width"]
        self.height = c["height"]
        self.n_entities = c["n_entities"]      # 4 (including no-op)
        self.n_directions = c["n_directions"]  # 4
        self.target_output = c["target_output"]
        self.sim_max_ticks = c["sim_max_ticks"]
        self.refill_amount = c["refill_amount"]

        n_tiles = self.width * self.height
        self.obs_dim = n_tiles * 12 + 3
        self.observation_space = spaces.Box(
            low=0.0, high=1.0, shape=(self.obs_dim,), dtype=np.float32
        )
        self.action_space = spaces.MultiDiscrete(
            [self.n_entities, n_tiles, self.n_directions]
        )
        self._build_action_count = 0
        # Track placements per entity type for diminishing-returns shaping.
        # Curiosity-by-shaping: rewarding novelty over repetition prevents
        # the agent from collapsing to "spam belts" as a degenerate strategy.
        self._placements_by_type = [0, 0, 0, 0]  # [belt, inserter, assembler, no-op]

    def _read_observation(self) -> np.ndarray:
        ob = call_rl(self._rcon, "arena_get_observation")
        if not ob.get("ok"):
            raise RuntimeError(f"arena_get_observation: {ob.get('error')}")
        grid = ob["grid"]
        globals_ = ob["globals"]
        out = np.zeros(self.obs_dim, dtype=np.float32)
        # grid may come back as a list (JSON array) or a dict (JSON object
        # if Lua serialized an empty-or-sparse table that way).
        if isinstance(grid, list):
            for i, v in enumerate(grid):
                out[i] = float(v)
        elif isinstance(grid, dict):
            # 1-indexed string keys from JSON object
            for k, v in grid.items():
                idx = int(k) - 1
                if 0 <= idx < self.obs_dim - 3:
                    out[idx] = float(v)
        # Normalize globals into [0,1] range (or close to it)
        out[-3] = float(globals_.get("tick_in_episode", 0.0))
        out[-2] = float(globals_.get("output_count", 0.0)) / max(1, self.target_output)
        out[-1] = float(globals_.get("input_count", 0.0)) / max(1, self.refill_amount)
        return out

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        res = call_rl(self._rcon, "arena_reset")
        if not res.get("ok"):
            raise RuntimeError(f"arena_reset failed: {res.get('error')}")
        self._build_action_count = 0
        self._placements_by_type = [0, 0, 0, 0]
        obs = self._read_observation()
        return obs, {"reset": res}

    def _finish_episode(self):
        """Start simulate, poll until done, return final reward + info."""
        sim = call_rl(self._rcon, "arena_start_simulate", SIM_MAX_TICKS_OVERRIDE)
        if not sim.get("ok"):
            return 0.0, {"sim_start_error": sim.get("error")}
        status = None
        for _ in range(SIM_POLL_MAX):
            time.sleep(SIM_POLL_INTERVAL)
            status = call_rl(self._rcon, "arena_get_sim_status")
            if not status.get("simulating"):
                break
        score = call_rl(self._rcon, "arena_score")
        info = {
            "reached": score.get("reached"),
            "ticks_taken": score.get("ticks_taken"),
            "output_count": score.get("output_count"),
            "components": score.get("components"),
            "sim_status": status,
        }
        return float(score.get("total", 0.0)), info

    def step(self, action):
        entity_choice = int(action[0])
        tile_index = int(action[1])
        direction = int(action[2])
        self._build_action_count += 1

        # If agent rolls no-op TOO EARLY, treat as an invalid attempt and
        # continue (don't end episode). Forces it to actually build something
        # before quitting.
        if entity_choice == 3 and self._build_action_count <= MIN_ACTIONS_BEFORE_NOOP:
            obs = self._read_observation()
            return obs, -1.0, False, False, {"place": {"early_noop": True}}

        # No-op (allowed after min actions) OR budget exceeded -> simulate.
        if entity_choice == 3 or self._build_action_count >= MAX_BUILD_ACTIONS:
            obs = self._read_observation()
            reward, info = self._finish_episode()
            info["actions_used"] = self._build_action_count
            info["budget_exceeded"] = self._build_action_count >= MAX_BUILD_ACTIONS
            return obs, reward, True, False, info

        # Per-step shaping with HARD CAPS per type. A typical working chain
        # is ~3 assemblers, ~4 inserters, ~10 belts. Beyond those counts,
        # additional placements of the same type are NEGATIVE — preventing
        # the agent from gaming the placement reward by spamming one thing.
        # Base rewards (first of type): belt=+5, inserter=+5, assembler=+12.
        # Curve shape: full reward up to soft start (1st-3rd), diminishing
        # to the cap, then -1 per excess placement.
        TYPE_CAPS = {0: 9, 1: 4, 2: 3}    # belt, inserter, assembler (demo uses 6 belts; +slack for variations)
        BASE_REWARDS = {0: 5.0, 1: 5.0, 2: 12.0}
        res = call_rl(self._rcon, "arena_place", entity_choice, tile_index, direction)
        if res.get("ok") and not res.get("noop"):
            n_already = self._placements_by_type[entity_choice]
            cap = TYPE_CAPS.get(entity_choice, 5)
            base = BASE_REWARDS.get(entity_choice, 5.0)
            if n_already < cap:
                # Diminishing within the useful range: 1.0, 0.7, 0.5, ...
                multiplier = max(0.3, 1.0 / (1 + 0.5 * n_already))
                step_reward = base * multiplier
            else:
                # Over the cap: actively discourage.
                step_reward = -1.0
            self._placements_by_type[entity_choice] += 1
            # NEW (mod 0.8.15): incremental chain bonus — placements that
            # contribute to a working chain RIGHT NOW (not just at episode
            # end) get an immediate kick. Gives much denser gradient.
            step_reward += float(res.get("chain_bonus", 0) or 0)
        else:
            step_reward = -0.2
        obs = self._read_observation()
        return obs, step_reward, False, False, {"place": res}

    def close(self):
        if self._rcon and self._rcon.sock:
            self._rcon.close()
