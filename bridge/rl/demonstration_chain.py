"""
Hand-built demo for the cables+circuits production chain on 8x8.

Layout sketch (horizontal, both assemblers in the middle band y=3-5):

  cols:  0 1 2 3 4 5 6 7
  row 3:       [A]A A    [B]B B     (assembler tops)
  row 4:  > > [A]A A < > [B]B B > >   (loaders row, assembler middles)
  row 5:       [A]A A    [B]B B     (assembler bottoms)

  Assembler A = cable maker (recipe = copper-cable), anchor (col 2, row 4)
  Assembler B = circuit maker (recipe = electronic-circuit), anchor (col 5, row 4)

  Belts row 4:
    col 0,1 = belts east (input loader at col -1 feeds copper-plate)
    col 4   = inserter picking from A east (col 3) and dropping on belt col 5
             ...wait this conflicts with B at col 5. need vertical routing.

  Reality check: 8x8 is TIGHT for this. Two 3x3 assemblers need 6 cols,
  and we need inserters between them plus belts in/out. Total needed:
  ~ 1 (in belt) + 1 (inserter) + 3 (asm A) + 1 (inserter B-in) + 3 (asm B)
  + 1 (inserter) + 1 (belt out) = 11 cols. Too wide for 8.

  Workaround for chain on 8x8:
    Vertical stacking. Cable assembler in top half, circuit assembler in
    bottom half. Cable output routes down to circuit input. Output goes
    out the bottom right.

This demo is approximate; the actual chain may need a larger arena.
Commit as a placeholder; revisit when arena is larger or mod supports it.
"""

W = 8

# Sketch only — not necessarily complete. This is a notes-shaped layout
# meant to be revisited when we know the chain arena dimensions.
LAYOUT = [
    # Cable assembler (top half), anchor (3, 1) — 3x3 occupies cols 2-4 rows 0-2
    (3, 1, 2, 0),
    # Inserter feeding cable assembler from input belt
    (1, 1, 1, 3),
    # Input belt (top row)
    (0, 1, 0, 1),
    # Cable assembler output -> goes to row 4 via inserter + belt
    (5, 1, 1, 3),
    (6, 1, 0, 2),  # belt south
    (6, 2, 0, 2),
    (6, 3, 0, 2),
    # Circuit assembler (bottom half), anchor (3, 5) — 3x3 occupies cols 2-4 rows 4-6
    (3, 5, 2, 0),
    # Inserter feeding circuit assembler from the cable-output belt
    (5, 5, 1, 3),
    # ALSO needs iron-plate input — but our single-input arena can only
    # mix items in the chest. iron-plate would come via a separate belt OR
    # in the same chest as copper-plate. This is where the arena design
    # gets tight.
    # Output inserter from circuit assembler
    (1, 5, 1, 3),
    # Output belt (bottom row)
    (0, 5, 0, 1),
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"8x8 chain demo (DRAFT, may not fit 8x8 cleanly): {len(LAYOUT)} actions")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col} row={row} -> place {ent_name:<10s} facing {dir_name}")
