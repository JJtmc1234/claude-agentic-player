"""
IMPERFECT 16x16 circuit demo (INITIAL stage; cables provided).

Recipe: 1 iron-plate + 3 copper-cable -> 1 electronic-circuit.
Initial stage: agent gets iron-plate AND copper-cable pre-made.
Mastery stage later: agent gets iron-plate + copper-plate and must build a
cable sub-asm in the chain.

Arena (mod 0.9.7+, 16x16, bounds (-20,70) to (-5,85)):
  - Input loader 1 at (-21, 77.5) feeds row 7 (iron-plate)
  - Input loader 2 at (-21, 78.5) feeds row 8 (copper-cable)
  - Output loader at (-4, 77.5) receives circuit via row 7

Demo (7 actions, matching the cable demo's "some belts but not the whole
chain" style):
  - col 0 row 7: belt EAST          (iron-plate input belt)
  - col 1 row 7: inserter W         (picks iron, drops on asm NW corner)
  - col 0 row 8: belt EAST          (cable input belt)
  - col 1 row 8: inserter W         (picks cable, drops on asm SW corner)
  - col 3 row 7: assembler anchor   (cols 2-4 rows 6-8, recipe=electronic-circuit)
  - col 5 row 7: inserter W         (picks asm NE, drops east)
  - col 6 row 7: belt EAST          (start of output chain)

Agent must add: belts col 7-15 on row 7 to reach the output loader.
Optionally a 2nd parallel chain on rows 11+ for throughput.
"""

W = 16

LAYOUT = [
    # Assembler first (cols 2-4, rows 6-8; row 7 = iron+output row, row 8 = cable input row)
    (3, 7, 2, 0),
    # Iron-plate input on row 7
    (1, 7, 1, 3),  # inserter W
    (0, 7, 0, 1),  # belt E
    # Copper-cable input on row 8
    (1, 8, 1, 3),  # inserter W
    (0, 8, 0, 1),  # belt E
    # Output side
    (5, 7, 1, 3),  # output inserter W (picks asm NE corner)
    (6, 7, 0, 1),  # output belt #1
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"16x16 circuit INITIAL demo (cables provided): {len(LAYOUT)} actions")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col} row={row} -> place {ent_name:<10s} facing {dir_name}")
    print("Agent must add: belts col 7-15 row 7 (9 belts) + optional 2nd chain.")
