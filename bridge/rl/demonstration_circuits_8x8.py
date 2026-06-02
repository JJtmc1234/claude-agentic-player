"""
8x8 demo for the CIRCUIT task with 2 input belts.

Arena setup (mod >= 0.9.3):
  - Input loader 1 at (-21, 77.5) feeds row 4 belt with iron-plate
  - Input loader 2 at (-21, 78.5) feeds row 5 belt with copper-cable
  - Output loader at (-11, 77.5) receives circuits via row 4 belt
  - Assembler set to electronic-circuit (3x3, cols 2-4, rows 3-5)

Chain:
  - col 0 row 4: belt EAST  -> carries iron east
  - col 1 row 4: inserter W -> picks iron from belt, drops on asm west edge
  - col 0 row 5: belt EAST  -> carries cable east
  - col 1 row 5: inserter W -> picks cable from belt, drops on asm SW corner
  - col 3 row 4: assembler  -> crafts electronic-circuit (1 iron + 3 cable)
  - col 5 row 4: inserter W -> picks circuit from asm east, drops on belt
  - col 6 row 4: belt EAST  -> carries circuit east
  - col 7 row 4: belt EAST  -> feeds output loader at col 8 (x=-12)

Action order: assembler FIRST (otherwise inserter drops on empty tile
leaving an item-on-ground that blocks asm placement), then both input
inserters, then output inserter, then belts.
"""

W = 8

LAYOUT = [
    # 1. Assembler at col=3, row=4 (cols 2-4, rows 3-5)
    (3, 4, 2, 0),
    # 2. Iron-side inserter at col=1, row=4, dir=W
    (1, 4, 1, 3),
    # 3. Cable-side inserter at col=1, row=5, dir=W
    (1, 5, 1, 3),
    # 4. Output inserter at col=5, row=4, dir=W
    (5, 4, 1, 3),
    # 5. Iron input belt at col=0, row=4, dir=E
    (0, 4, 0, 1),
    # 6. Cable input belt at col=0, row=5, dir=E
    (0, 5, 0, 1),
    # 7. Output belt at col=6, row=4, dir=E
    (6, 4, 0, 1),
    # 8. Output belt at col=7, row=4, dir=E
    (7, 4, 0, 1),
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"8x8 circuit demo (2 input belts): {len(LAYOUT)} actions")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col} row={row} -> place {ent_name:<10s} facing {dir_name}")
