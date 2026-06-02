"""
Alternate 8x8 demo — shifts the assembler right by 1 column.

Geometry:
  - Asm anchor at col=4 row=4 → occupies cols 3-5, rows 3-5
  - 2 belts at cols 0,1 east-facing carry plates from input loader to inserter
  - Input inserter at col=2 dir=W picks belt at col 1, drops on asm edge col 3
  - Output inserter at col=6 dir=W picks col 5 (asm east edge), drops col 7
  - 1 belt at col=7 east-facing pushes gears to output loader at col 8 (x=-12)

This is a working variant: same chain principles, different placement.
Pairs with the original demonstration_8x8.py as a 2nd expert trajectory
for BC training, so the policy learns "the chain pattern" rather than
"this exact tile layout".

Pre-tested in the live arena (mod 0.8.20, refill=20, sim_max=1800):
should also produce ~10 gears.
"""

W = 8

LAYOUT = [
    # Assembler first (must precede inserters; else inserter drop on empty tile
    # leaves an item-on-ground that blocks the asm's footprint).
    (4, 4, 2, 0),
    # Input inserter at col=2 dir=W: picks west (col 1 belt), drops east (col 3 asm edge)
    (2, 4, 1, 3),
    # Output inserter at col=6 dir=W: picks west (col 5 asm edge), drops east (col 7 belt)
    (6, 4, 1, 3),
    # Belts east-facing — 2 input belts (cols 0,1) feed the input inserter
    (0, 4, 0, 1),
    (1, 4, 0, 1),
    # 1 output belt (col 7) pushes east to col 8 which feeds output loader
    (7, 4, 0, 1),
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"8x8 demo v2 (asm shifted +1): {len(LAYOUT)} actions")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col} row={row} -> place {ent_name:<10s} facing {dir_name}")
