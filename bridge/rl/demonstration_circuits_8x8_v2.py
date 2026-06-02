"""
Second 8x8 circuit demo — assembler shifted +1 column.

Same 2-input belt principle as demonstration_circuits_8x8.py but
the asm anchor moves from col 3 to col 4 (cols 3-5 instead of 2-4).
This forces the agent to use slightly different belt/inserter placement
and gives BC a second distinct layout to memorize.

Chain (asm at col 4 row 4 → cols 3-5, rows 3-5):
  - col 0,1 row 4: iron belts EAST -> 2 belts feed inserter at col 2
  - col 2 row 4: iron inserter W -> picks col 1, drops col 3 (asm west)
  - col 0,1 row 5: cable belts EAST -> 2 belts feed inserter at col 2 row 5
  - col 2 row 5: cable inserter W -> picks col 1 row 5, drops col 3 row 5 (asm SW)
  - col 4 row 4: assembler
  - col 6 row 4: output inserter W -> picks col 5 (asm east), drops col 7
  - col 7 row 4: output belt EAST -> col 8 (output loader)

Action order: asm first, inserters next, belts last.
"""

W = 8

LAYOUT = [
    # Assembler at col=4, row=4 (cols 3-5, rows 3-5)
    (4, 4, 2, 0),
    # Iron inserter at col=2 row=4 dir=W
    (2, 4, 1, 3),
    # Cable inserter at col=2 row=5 dir=W
    (2, 5, 1, 3),
    # Output inserter at col=6 row=4 dir=W
    (6, 4, 1, 3),
    # Iron belts (2) cols 0,1 row 4
    (0, 4, 0, 1),
    (1, 4, 0, 1),
    # Cable belts (2) cols 0,1 row 5
    (0, 5, 0, 1),
    (1, 5, 0, 1),
    # Output belt col 7 row 4
    (7, 4, 0, 1),
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"8x8 circuit demo v2 (asm shifted +1): {len(LAYOUT)} actions")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col} row={row} -> place {ent_name:<10s} facing {dir_name}")
