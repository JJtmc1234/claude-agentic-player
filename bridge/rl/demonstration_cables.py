"""
Hand-built demo for the cable task on the 8x8 arena.

Structurally identical to the gear demo (assembler + 2 inserters + belts).
Only the recipe (mod-side, set to 'copper-cable') differs.
"""

W = 8

LAYOUT = [
    # Assembler anchor at col=3, row=4 (recipe='copper-cable' from mod config)
    (3, 4, 2, 0),
    # Input inserter: picks belt at col 0, drops on assembler west edge (col 2)
    (1, 4, 1, 3),
    # Output inserter: picks assembler east (col 4), drops on belt col 6
    (5, 4, 1, 3),
    # Belts
    (0, 4, 0, 1),
    (6, 4, 0, 1),
    (7, 4, 0, 1),
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"8x8 cable demo: {len(LAYOUT)} actions (identical layout to gears, "
          f"recipe is the only difference)")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col} row={row} -> place {ent_name:<10s} facing {dir_name}")
