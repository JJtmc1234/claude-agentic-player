"""
Circuit MASTERY 16x16 demo — MULTI-PRODUCT CHAIN.

Inputs: iron-plate (row 7) + copper-plate (row 8).
Agent must assemble copper-plate -> cable asm -> cable -> mixed with iron
in circuit asm -> circuit -> output loader.

Two assemblers, different recipes, via direction-as-recipe-index in mod
0.10.0:
  - direction 0 (N) -> recipe_options[1] = 'copper-cable'
  - direction 1 (E) -> recipe_options[2] = 'electronic-circuit'

Layout (16x16, bounds (-20,70) to (-5,85)):

  Row 7 (iron-plate / circuits output):
    col 0..7  belt E         (iron flows east)
    col 8     inserter W     (picks iron belt, drops on circuit asm west)
    col 9..11 CIRCUIT ASM    (3x3 anchor (10,7) dir=E for circuit recipe)
    col 12    inserter W     (picks asm east, drops on output belt)
    col 13..15 belt E        (output to loader at col 16)

  Row 8 (copper-plate / cable conveyor):
    col 0     belt E         (copper feed)
    col 1     inserter W     (picks copper belt, drops on cable asm)
    col 2..4  CABLE ASM      (3x3 anchor (3,9) dir=N for cable recipe; occupies rows 8-10)
    col 5     inserter W     (picks asm east, drops on conveyor belt)
    col 6..7  belt E         (cable conveyor east)
    col 8     inserter W     (picks cable belt, drops on circuit asm bottom)

The cable assembler's anchor at (3, 9) means it occupies rows 8-10 — keeping
row 7 free for iron through-traffic. The circuit assembler's anchor at
(10, 7) means it occupies rows 6-8 — overlapping the cable conveyor at row 8
on its SW corner, which is where the cable inserter drops.

Action count: 22 (2 asm + 5 inserters + 15 belts).
This is the FULL demo; for imperfect-demo training, truncate the last
few output belts so PPO has to discover the bridging.
"""

W = 16

LAYOUT = [
    # ---- assemblers first ----
    (10, 7, 2, 1),   # circuit asm — anchor (10,7), dir=E -> recipe_options[2] = circuit
    (3, 9, 2, 0),    # cable asm   — anchor (3,9),  dir=N -> recipe_options[1] = cable

    # ---- iron / circuit row 7 ----
    (8, 7, 1, 3),    # inserter W: picks col 7 belt, drops col 9 (circuit asm)
    (12, 7, 1, 3),   # inserter W: picks col 11 (circuit asm), drops col 13 (output)

    # iron input belts cols 0..7 row 7
    (0, 7, 0, 1),
    (1, 7, 0, 1),
    (2, 7, 0, 1),
    (3, 7, 0, 1),
    (4, 7, 0, 1),
    (5, 7, 0, 1),
    (6, 7, 0, 1),
    (7, 7, 0, 1),

    # output belts cols 13, 14 row 7 (col 15 collides with the 1x2 loader)
    (13, 7, 0, 1),
    (14, 7, 0, 1),

    # ---- copper / cable row 8 ----
    (1, 8, 1, 3),    # copper inserter W: picks col 0 belt, drops col 2 (cable asm)
    (5, 8, 1, 3),    # cable output inserter W: picks col 4 (cable asm), drops col 6
    (8, 8, 1, 3),    # cable input inserter W: picks col 7 belt, drops col 9 (circuit asm)

    (0, 8, 0, 1),    # copper feed belt
    (6, 8, 0, 1),    # cable conveyor belts
    (7, 8, 0, 1),
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"16x16 circuit MASTERY demo (multi-product): {len(LAYOUT)} actions")
    print("  inputs: iron-plate (row 7) + copper-plate (row 8)")
    print("  output: electronic-circuit via output loader at col 16")
    print("  recipe_options must be ['copper-cable', 'electronic-circuit']")
    print()
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        if e == 2:
            recipe = ["cable", "circuit", "?", "?"][d]
            print(f"  col={col:>2} row={row} -> place {ent_name:<10s} dir={d} ({recipe})")
        else:
            dir_name = ["N", "E", "S", "W"][d]
            print(f"  col={col:>2} row={row} -> place {ent_name:<10s} facing {dir_name}")
