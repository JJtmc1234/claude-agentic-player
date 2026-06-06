"""
IMPERFECT mastery demo: just the asms + key bridging inserters, no belts.

Agent gets ~10 actions placed and must add the input/output belts + cable
conveyor itself. JJ asked for "less chain demo initially" — this is the
minimum scaffolding to make the multi-product structure visible.

Layout (16x16, mod 0.10.1, recipe_options = [cable, circuit]):

  Row 7 (iron / output): circuit asm at cols 9-11 + key inserters
  Row 8 (copper / cable conveyor): cable asm at cols 2-4 (rows 8-10) + key inserters
"""

W = 16

LAYOUT = [
    # Assemblers (with direction = recipe index)
    (10, 7, 2, 1),   # circuit asm dir=E -> recipe_options[2] = circuit
    (3, 9, 2, 0),    # cable asm   dir=N -> recipe_options[1] = cable

    # Key inserters that physically MAKE the multi-product topology happen
    (8, 7, 1, 3),    # iron inserter (will pick from belt to be placed, drops on circuit asm)
    (12, 7, 1, 3),   # circuit output inserter
    (1, 8, 1, 3),    # copper inserter (-> cable asm)
    (5, 8, 1, 3),    # cable output inserter (cable asm -> conveyor)
    (8, 8, 1, 3),    # cable input inserter (conveyor -> circuit asm bottom)

    # Minimal belts the agent can use as "anchors" for the input/output chains
    (0, 7, 0, 1),    # first iron belt (agent extends east)
    (0, 8, 0, 1),    # first copper belt
    (13, 7, 0, 1),   # first output belt (agent extends east)
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"16x16 circuit MASTERY PARTIAL demo: {len(LAYOUT)} actions")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        if e == 2:
            recipe = ["cable", "circuit", "?", "?"][d]
            print(f"  col={col:>2} row={row} -> place {ent_name:<10s} dir={d} ({recipe})")
        else:
            dir_name = ["N", "E", "S", "W"][d]
            print(f"  col={col:>2} row={row} -> place {ent_name:<10s} facing {dir_name}")
    print()
    print("Agent must add: iron belts col 1-7 row 7, copper belt(s) row 8, "
          "cable conveyor belts col 6-7 row 8, output belts col 14 row 7.")
