"""
Render the current arena state to a PNG using PIL.

Queries the mod for the observation grid, draws each tile color-coded by
entity type with direction arrows where relevant. Saves to ./images/.
Does NOT require a connected Factorio client (no in-game rendering).

Run:
    python bridge/rl/render_arena.py
    python bridge/rl/render_arena.py --out images/best.png --tile 96
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from _claude import call_mod as _call  # noqa: E402
from rcon_client import RconClient  # noqa: E402

# Color palette by entity kind.
PALETTE = {
    "empty": (40, 40, 50),
    "belt": (60, 180, 110),
    "inserter": (240, 200, 60),
    "assembler": (130, 110, 230),
    "input_chest": (60, 200, 60),
    "output_chest": (220, 60, 60),
}
DIR_ARROW = {"N": "^", "E": ">", "S": "v", "W": "<"}


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--out", default=None,
                   help="output PNG path (default: images/arena_<timestamp>.png)")
    p.add_argument("--tile", type=int, default=64, help="pixels per tile")
    args = p.parse_args()

    print("[render] querying arena ...")
    with RconClient() as r:
        constants = _call(r, "arena_get_constants", interface="claude_rl")
        obs = _call(r, "arena_get_observation", interface="claude_rl")
    if not constants.get("ok"):
        print(f"[render] arena_get_constants: {constants.get('error')}", file=sys.stderr)
        return 1
    if not obs.get("ok"):
        print(f"[render] arena_get_observation: {obs.get('error')}", file=sys.stderr)
        return 1

    W = constants["width"]
    H = constants["height"]
    grid = obs["grid"]
    g_globals = obs["globals"]
    tile = args.tile

    margin_top = 50
    margin_bot = 60
    side_pad = tile  # room on each side for input/output loader markers
    img_w = side_pad * 2 + W * tile
    img_h = margin_top + H * tile + margin_bot
    img = Image.new("RGB", (img_w, img_h), (18, 18, 24))
    draw = ImageDraw.Draw(img)

    try:
        title_font = ImageFont.truetype("arialbd.ttf", 20)
        cell_font = ImageFont.truetype("arialbd.ttf", max(14, tile // 3))
        small_font = ImageFont.truetype("arial.ttf", 12)
    except (OSError, IOError):
        title_font = ImageFont.load_default()
        cell_font = ImageFont.load_default()
        small_font = ImageFont.load_default()

    # Title bar
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    draw.text((10, 8), f"Arena snapshot — {timestamp}", fill="white", font=title_font)
    draw.text(
        (10, 30),
        f"{W}x{H} grid  |  input chest plates: {g_globals.get('input_count', 0):.0f}  "
        f"|  output chest gears: {g_globals.get('output_count', 0):.0f}",
        fill=(200, 200, 220), font=small_font,
    )

    # Input loader marker (left of grid)
    in_x0 = side_pad - tile + 4
    in_y0 = margin_top + (H // 2) * tile
    draw.rectangle([in_x0, in_y0, in_x0 + tile - 8, in_y0 + tile],
                   fill=PALETTE["input_chest"], outline="white", width=2)
    draw.text((in_x0 + 8, in_y0 + tile // 2 - 10), "IN", fill="black", font=cell_font)

    # Output loader marker (right of grid)
    out_x0 = side_pad + W * tile + 4
    out_y0 = margin_top + (H // 2) * tile
    draw.rectangle([out_x0, out_y0, out_x0 + tile - 8, out_y0 + tile],
                   fill=PALETTE["output_chest"], outline="white", width=2)
    draw.text((out_x0 + 4, out_y0 + tile // 2 - 10), "OUT", fill="black", font=cell_font)

    # Iterate grid cells
    for row in range(H):
        for col in range(W):
            tx = side_pad + col * tile
            ty = margin_top + row * tile
            offset = (row * W + col) * 12
            channels = grid[offset:offset + 12]
            on_idx = next((i for i, v in enumerate(channels) if v > 0.5), 0)

            if on_idx == 0:
                color = PALETTE["empty"]
                label = ""
            elif 1 <= on_idx <= 4:
                color = PALETTE["belt"]
                label = DIR_ARROW["NESW"[on_idx - 1]]
            elif 5 <= on_idx <= 8:
                color = PALETTE["inserter"]
                # Inserter direction in our channels = pickup direction.
                label = DIR_ARROW["NESW"[on_idx - 5]]
            elif on_idx == 9:
                color = PALETTE["assembler"]
                label = "A"
            elif on_idx == 10:
                color = PALETTE["input_chest"]
                label = "I"
            elif on_idx == 11:
                color = PALETTE["output_chest"]
                label = "O"
            else:
                color = PALETTE["empty"]
                label = "?"

            draw.rectangle([tx, ty, tx + tile, ty + tile], fill=color, outline=(70, 70, 80))
            if label:
                bbox = draw.textbbox((0, 0), label, font=cell_font)
                tw = bbox[2] - bbox[0]
                th = bbox[3] - bbox[1]
                draw.text((tx + (tile - tw) // 2, ty + (tile - th) // 2),
                          label, fill="black", font=cell_font)

    # Legend at the bottom
    legend_y = margin_top + H * tile + 12
    legend_items = [
        ("Empty", PALETTE["empty"]),
        ("Belt", PALETTE["belt"]),
        ("Inserter", PALETTE["inserter"]),
        ("Assembler", PALETTE["assembler"]),
        ("Input chest", PALETTE["input_chest"]),
        ("Output chest", PALETTE["output_chest"]),
    ]
    lx = 10
    for name, color in legend_items:
        draw.rectangle([lx, legend_y, lx + 18, legend_y + 18], fill=color, outline="white")
        draw.text((lx + 22, legend_y + 2), name, fill="white", font=small_font)
        lx += 110

    # Save
    if args.out:
        out = Path(args.out)
    else:
        repo_root = _BRIDGE.parent
        out = repo_root / "images" / f"arena_{int(time.time())}.png"
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    print(f"[render] saved -> {out}  ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
