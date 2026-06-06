"""
IMPERFECT 16x16 cable demo — version with SOME belts but not the whole chain.

Per JJ: give the agent partial scaffolding, not the full layout. This demo
sets up both input and output sides, but stops the output belt chain
~halfway across the arena. The agent must extend the output belts to reach
the output loader at col 16 (x=-4, just east of bounds.x_max=-5/col 15).

Arena (mod 0.9.5, 16x16, bounds (-20,70) to (-5,85)):
  - Input loader 1 at (-21, 77.5) feeds row 7 with iron-plate (distractor)
  - Input loader 2 at (-21, 78.5) feeds row 8 with copper-plate (real input)
  - Output loader at (-4, 77.5) receives copper-cable via row 7

Demo (7 actions):
  - col 0 row 8: belt EAST          (copper-plate feeds inserter)
  - col 1 row 8: inserter W         (picks copper, drops on asm SW tile)
  - col 3 row 8: assembler anchor   (cols 2-4 rows 7-9, recipe=copper-cable)
  - col 5 row 7: inserter W         (picks asm NE tile, drops east to belt)
  - col 6 row 7: belt EAST          (output belt #1)
  - col 7 row 7: belt EAST          (output belt #2)
  - col 8 row 7: belt EAST          (output belt #3)

Agent must add: belts col 9-15 on row 7 (7 belts) to reach the output
loader. Plus optionally a 2nd parallel chain on rows 11+ for throughput.
"""

W = 16

LAYOUT = [
    # Assembler first (cols 2-4, rows 7-9; row 8 = copper input row)
    (3, 8, 2, 0),
    # Copper input inserter at col 1 row 8, dir=W
    (1, 8, 1, 3),
    # Output inserter at col 5 row 7, dir=W (picks asm NE corner, drops east)
    (5, 7, 1, 3),
    # Copper input belt at col 0 row 8, dir=E
    (0, 8, 0, 1),
    # Output belts at cols 6/7/8 row 7, dir=E — chain stops short of col 15
    (6, 7, 0, 1),
    (7, 7, 0, 1),
    (8, 7, 0, 1),
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"16x16 cable PARTIAL demo (some belts, incomplete output): {len(LAYOUT)} actions")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col} row={row} -> place {ent_name:<10s} facing {dir_name}")
    print("Agent must add belts col 9-15 row 7 (7 more) to reach the loader.")
