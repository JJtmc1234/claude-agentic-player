"""
Snapshot what entities are in the arena RIGHT NOW. Pure text/ASCII output —
no PIL, no in-game rendering. Useful for diffing what different checkpoints
build.

Reads arena_debug_state + the observation grid to build a (height, width)
grid of entity-type letters with direction arrows.

Run:
    python bridge/rl/snapshot_layout.py
    python bridge/rl/snapshot_layout.py --before-reset  # snapshot existing state
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from _claude import call_mod
from rcon_client import RconClient


DIR_NAME = {0: 'N', 4: 'E', 8: 'S', 12: 'W'}
DIR_ARROW = {0: '^', 4: '>', 8: 'v', 12: '<', None: '?'}


def grid_text(s, width=80):
    return f'{s:<{width}}'


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument('--cell-width', type=int, default=4,
                   help='characters per arena tile')
    args = p.parse_args()

    r = RconClient(); r.connect()

    consts = call_mod(r, 'arena_get_constants', interface='claude_rl')
    if not consts.get('ok'):
        print(f'arena_get_constants failed: {consts}')
        return 1
    w = consts['width']
    h = consts['height']
    bounds = consts['bounds']
    print(f'Arena: {w}x{h} bounds={bounds}')

    dbg = call_mod(r, 'arena_debug_state', interface='claude_rl')
    print(f'\nChests:')
    print(f'  in : {dbg.get("input_chest", {}).get("position")} '
          f'contents={dbg.get("input_chest", {}).get("contents")}')
    print(f'  out: {dbg.get("output_chest", {}).get("position")} '
          f'contents={dbg.get("output_chest", {}).get("contents")}')
    print(f'Loaders: in={dbg.get("input_loader")} out={dbg.get("output_loader")}')
    print(f'Assemblers: {dbg.get("n_assemblers")}')
    for asm in dbg.get('assemblers') or []:
        print(f'  {asm}')

    # Build a grid using the observation channels.
    obs = call_mod(r, 'arena_get_observation', interface='claude_rl')
    if not obs.get('ok'):
        print(f'arena_get_observation failed: {obs}')
        return 1
    grid = obs['grid']
    if isinstance(grid, dict):
        # 1-indexed string keys
        flat = [0.0] * (w * h * 12)
        for k, v in grid.items():
            flat[int(k) - 1] = float(v)
        grid = flat

    # Channel layout: 0=empty, 1=belt, 2=inserter, 3=asm, 4..7=belt dir, 8..11=ins dir
    # (See mod's arena_get_observation for exact mapping.)
    def cell_at(col, row):
        base = ((row * w) + col) * 12
        ch = grid[base:base+12]
        if ch[0] > 0.5:
            return '.'  # empty
        if ch[1] > 0.5:
            for di, dirv in enumerate([0, 4, 8, 12]):
                if ch[4+di] > 0.5:
                    return f'B{DIR_ARROW[dirv]}'
            return 'B?'
        if ch[2] > 0.5:
            for di, dirv in enumerate([0, 4, 8, 12]):
                if ch[8+di] > 0.5:
                    return f'I{DIR_ARROW[dirv]}'
            return 'I?'
        if ch[3] > 0.5:
            return 'AA'
        return '?'

    cw = max(args.cell_width, 3)
    print('\nLayout (rows top-to-bottom, cols 0..W-1 left-to-right):')
    print('     ' + ''.join(f'{c:>{cw}}' for c in range(w)))
    for row in range(h):
        cells = [cell_at(col, row) for col in range(w)]
        print(f' {row:>2}  ' + ''.join(f'{c:>{cw}}' for c in cells))

    r.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
