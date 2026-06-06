"""
IMPERFECT 16x16 circuit demo. Initial-stage: inputs are iron-plate +
copper-cable (cables provided, agent doesn't make them yet).

Places the assembler + the iron-input half of the chain ONLY. The agent
must add: cable-input chain on row 8 + output chain on row 7+ to the
output loader.

Arena (mod 0.9.5, 16x16, bounds (-20,70) to (-5,85)):
  - Input loader 1 at (-21, 77.5) feeds row 7 (iron-plate)
  - Input loader 2 at (-21, 78.5) feeds row 8 (copper-cable)
  - Output loader at (-4, 77.5) receives circuit via row 7

Demo places at row 7 (iron input):
  - col 0 row 7: belt EAST  (iron-plate belt)
  - col 1 row 7: inserter W (picks iron, drops on asm west edge)
  - col 3 row 7: asm anchor (cols 2-4, rows 6-8; recipe=electronic-circuit)

Agent must add:
  - Cable input inserter (somewhere on row 8 picking from cable belt)
  - Cable input belt (col 0 row 8 east)
  - Output inserter on asm east edge
  - Output belts col 5-15 row 7 east -> output loader at col 16/x=-4
  - Optional: 2nd parallel asm row 11+

3 actions placed; agent has 57 more to extend.
"""

W = 16

LAYOUT = [
    # Assembler at col=3, row=7 (cols 2-4, rows 6-8)
    (3, 7, 2, 0),
    # Iron input inserter at col=1, row=7, dir=W
    (1, 7, 1, 3),
    # Iron input belt at col=0, row=7, dir=E
    (0, 7, 0, 1),
]


def as_actions():
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"16x16 circuit IMPERFECT demo: {len(LAYOUT)} actions (initial stage)")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col} row={row} -> place {ent_name:<10s} facing {dir_name}")
    print("Agent must add cable-input chain + output chain + (optional) 2nd asm.")
