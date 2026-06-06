"""
FactorioArenaEnv variant that exposes per-step action masks for MaskablePPO.

Strategy: compute mask client-side using the observation grid. A tile is
"masked in" only if it's currently empty (channel 0 == 1). This eliminates
the vast majority of invalid placements (placing on top of an existing
entity, a chest, or anything in the way).

What's NOT masked here:
  - Assembler 3x3 footprint going out of bounds at edge — caught by
    arena_place's bounds check (still an invalid action penalty)
  - Direction validity for the specific entity (most accept any of 4)
  - Entity choice validity (no-op always allowed)

For MaskablePPO with MultiDiscrete action, masks are concatenated per
dimension:  mask shape = (4 + W*H + 4,)
"""

from __future__ import annotations

import numpy as np

from rl.env import FactorioArenaEnv


class MaskableFactorioArenaEnv(FactorioArenaEnv):
    def __init__(self):
        super().__init__()
        self._last_obs = None

    def reset(self, *, seed=None, options=None):
        obs, info = super().reset(seed=seed, options=options)
        self._last_obs = obs
        return obs, info

    def step(self, action):
        obs, reward, terminated, truncated, info = super().step(action)
        self._last_obs = obs
        return obs, reward, terminated, truncated, info

    def action_masks(self) -> np.ndarray:
        """Concatenated mask for MultiDiscrete([n_entities, W*H, n_dirs])."""
        n_tiles = self.width * self.height
        entity_mask = np.ones(self.n_entities, dtype=bool)   # all entity choices allowed
        direction_mask = np.ones(self.n_directions, dtype=bool)  # all directions allowed
        # Tile mask: True only if tile is empty (channel 0 == 1).
        if self._last_obs is None:
            tile_mask = np.ones(n_tiles, dtype=bool)
        else:
            ch = self.n_channels  # mod 0.9.4: 10 channels (was 12)
            grid = self._last_obs[: n_tiles * ch].reshape(self.height, self.width, ch)
            tile_empty = (grid[:, :, 0] > 0.5).reshape(-1)  # row-major
            tile_mask = tile_empty
        return np.concatenate([entity_mask, tile_mask, direction_mask])
