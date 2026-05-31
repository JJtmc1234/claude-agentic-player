"""
Hand-built demo layout for the 8x8 arena.

Arena bounds: x_min=-20, y_min=73, x_max=-13, y_max=80 → 8 cols × 8 rows.
The loaders are OUTSIDE the grid at x=-21 (input) and x=-11 (output),
so the agent only places belts/inserters/assembler inside the grid.

Simplest working chain (row 4 / y=77.5 — same row as the loaders):

  col 0: belt east        -> picks up from input loader
  col 1: inserter west    -> picks col 0 belt, drops on col 2 (asm edge)
  col 3: assembler anchor -> occupies cols 2-4, row 3-5; recipe=gear
  col 5: inserter west    -> picks col 4 (asm east), drops on col 6
  col 6: belt east        -> carries gear east
  col 7: belt east        -> feeds output loader at col=8/x=-11

Encoded as (col, row, entity_choice, dir_choice) tuples.
entity_choice: 0=belt 1=inserter 2=assembler 3=no-op
dir_choice:    0=N    1=E       2=S         3=W
"""

W = 8

# Assembler first (must be placed before inserters; else inserter drops on
# empty tile -> item-on-ground blocks assembler placement).
LAYOUT = [
    # Assembler anchor at col=3, row=4 (3x3 occupies cols 2-4, rows 3-5)
    (3, 4, 2, 0),
    # Input-side inserter at col=1, picks west (col 0), drops east (col 2 = asm)
    (1, 4, 1, 3),
    # Output-side inserter at col=5, picks west (col 4 = asm), drops east (col 6)
    (5, 4, 1, 3),
    # Belts east-facing
    (0, 4, 0, 1),
    (6, 4, 0, 1),
    (7, 4, 0, 1),
]


def as_actions():
    """Convert LAYOUT to a list of (entity_choice, tile_index, direction)
    tuples ready to feed into env.step()."""
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"8x8 demo layout: {len(LAYOUT)} actions")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col} row={row} -> place {ent_name:<10s} facing {dir_name}")
