"""
JJ's hand-built reference layout — a minimal working gear factory.

Captured from the arena on 2026-05-30 after JJ placed it for demonstration.
Used as:
  - A scoring sanity check (apply this layout to a fresh reset; the score
    should be HIGH because it actually produces gears).
  - Seed material for behavioral cloning / pre-training the PPO policy.

Encoding matches the env's MultiDiscrete([4, n_tiles, 4]) action space:
  - entity_choice: 0=transport-belt, 1=inserter, 2=assembling-machine-1, 3=no-op
  - tile_index: 0..(W*H-1), row-major (col = idx % W, row = idx // W)
  - direction: 0=N, 1=E, 2=S, 3=W (mapped to defines.direction 0/4/8/12)

Arena bounds (for reference): x_min=-24, y_min=70, W=16, H=16
  -> col = (x - x_min), row = (y - y_min)
"""

W = 16

# (col, row, entity_choice, dir_choice)
# IMPORTANT: assembler FIRST. If we placed an inserter first, it would
# immediately try to drop its picked-up plate on the empty target tile,
# creating an item-on-ground that blocks the assembler placement.
LAYOUT = [
    # Assembler anchor (3x3) — entity occupies cols 6-8 around anchor at col 7
    (7, 8, 2, 0),
    # Input-side inserter (picks from belt at col 4, drops on assembler at col 6)
    (5, 8, 1, 3),
    # Output-side inserter (picks from assembler col 8, drops on belt at col 10)
    (9, 8, 1, 3),
    # Belts feeding in (5 belts, east-facing, row 8 = y=78)
    (0, 8, 0, 1),  (1, 8, 0, 1),  (2, 8, 0, 1),  (3, 8, 0, 1),  (4, 8, 0, 1),
    # Belts feeding out (6 belts, east-facing)
    (10, 8, 0, 1), (11, 8, 0, 1), (12, 8, 0, 1), (13, 8, 0, 1), (14, 8, 0, 1), (15, 8, 0, 1),
]


def as_actions():
    """Convert LAYOUT to a list of (entity_choice, tile_index, direction)
    tuples ready to feed into env.step()."""
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"JJ demo layout: {len(LAYOUT)} actions")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col:2d} row={row:2d} -> place {ent_name:<10s} facing {dir_name}")
