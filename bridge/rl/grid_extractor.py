"""
Custom features extractor: reshape the flat (H*W*12 + 3) obs into a
12-channel HxW grid + 3 globals, run a small CNN on the grid, concat
with globals, output features.

Why: an 8x8 grid has spatial structure (adjacency, flow direction) that
an MLP has to relearn from scratch — burning sample efficiency. A 2-layer
CNN with 3x3 kernels gives the policy "neighborhood awareness" for free.

Plug into MaskablePPO via:
    policy_kwargs = dict(
        features_extractor_class=GridExtractor,
        features_extractor_kwargs=dict(width=8, height=8, n_channels=12,
                                       n_globals=3, features_dim=128),
        net_arch=[128],
    )
"""

from __future__ import annotations

import torch as th
from torch import nn
from stable_baselines3.common.torch_layers import BaseFeaturesExtractor


class GridExtractor(BaseFeaturesExtractor):
    def __init__(self, observation_space, width: int = 8, height: int = 8,
                 n_channels: int = 12, n_globals: int = 3,
                 features_dim: int = 128):
        super().__init__(observation_space, features_dim)
        self.width = width
        self.height = height
        self.n_channels = n_channels
        self.n_globals = n_globals
        self.n_grid = width * height * n_channels

        # Small CNN: 12 -> 32 -> 32, 3x3 same-padding, then flatten.
        self.cnn = nn.Sequential(
            nn.Conv2d(n_channels, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 32, kernel_size=3, padding=1),
            nn.ReLU(),
            nn.Flatten(),
        )
        cnn_out = 32 * width * height

        self.head = nn.Sequential(
            nn.Linear(cnn_out + n_globals, features_dim),
            nn.ReLU(),
        )

    def forward(self, obs: th.Tensor) -> th.Tensor:
        # obs shape: (B, H*W*12 + 3)
        batch = obs.shape[0]
        grid = obs[:, : self.n_grid]
        globs = obs[:, self.n_grid:]
        # Env writes row-major H,W with 12 channels last (one-hot per tile).
        grid = grid.reshape(batch, self.height, self.width, self.n_channels)
        # Conv2d wants (B, C, H, W)
        grid = grid.permute(0, 3, 1, 2).contiguous()
        feats = self.cnn(grid)
        combined = th.cat([feats, globs], dim=-1)
        return self.head(combined)
