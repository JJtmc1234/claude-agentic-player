"""
Variant B of the partial mastery demo: SHIFTED layout, SWAPPED rows.

Variety per JJ's `feedback_demo_variety`: BC trained on multiple demos
generalizes much better than a single-demo BC that memorizes one layout.

Same topology as variant A (cable_asm -> bridging inserter -> circuit_asm
-> output) but:
  - cable asm shifted east (col 4 -> col 5)
  - circuit asm shifted east (col 10 -> col 11)
  - bridging inserter direction differs (asm on col 5 instead of col 3)
"""

W = 16

LAYOUT = [
    # Assemblers (direction = recipe-index)
    (11, 7, 2, 1),   # circuit asm dir=E -> recipe_options[2] = circuit (cols 10-12)
    (5, 9, 2, 0),    # cable asm   dir=N -> recipe_options[1] = cable   (cols 4-6)

    # Bridging inserters
    (9, 7, 1, 3),    # iron pickup -> circuit asm (was col 8 in variant A)
    (13, 7, 1, 3),   # circuit output (was col 12)
    (3, 8, 1, 3),    # copper -> cable asm (was col 1)
    (7, 8, 1, 3),    # cable output (was col 5)
    (9, 8, 1, 3),    # cable -> circuit asm bottom (was col 8)

    # Minimal anchor belts
    (0, 7, 0, 1),    # first iron belt
    (0, 8, 0, 1),    # first copper belt
    (14, 7, 0, 1),   # first output belt (was col 13)
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"16x16 circuit MASTERY PARTIAL B demo: {len(LAYOUT)} actions")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        if e == 2:
            recipe = ["cable", "circuit", "?", "?"][d]
            print(f"  col={col:>2} row={row} -> place {ent_name:<10s} dir={d} ({recipe})")
        else:
            dir_name = ["N", "E", "S", "W"][d]
            print(f"  col={col:>2} row={row} -> place {ent_name:<10s} facing {dir_name}")
