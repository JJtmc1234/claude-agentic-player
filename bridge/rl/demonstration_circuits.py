"""
Hand-built demo for the circuit task on the same 8x8 arena.

Structurally identical to demonstration_8x8.py (assembler in the middle,
inserter on each side, belts to/from loaders). Only the assembler RECIPE
differs — set in the mod, not in the action sequence.

NOT YET WIRED UP. Used by train_circuits.py / replay_demo_circuits.py
once mod 0.9.0 supports arena_set_task('electronic-circuit', ...).
"""

W = 8

LAYOUT = [
    # Assembler anchor at col=3, row=4 (3x3 occupies cols 2-4, rows 3-5).
    # Mod 0.9.0 will set this assembler's recipe to electronic-circuit at
    # placement time (controlled by storage.arena.recipe_name).
    (3, 4, 2, 0),
    # Input-side inserter: picks west (col 0 belt), drops east (col 2 = asm)
    (1, 4, 1, 3),
    # Output-side inserter: picks west (col 4 = asm), drops east (col 6 belt)
    (5, 4, 1, 3),
    # Belts east-facing
    (0, 4, 0, 1),
    (6, 4, 0, 1),
    (7, 4, 0, 1),
]


def as_actions():
    """(entity_choice, tile_index, direction) tuples for env.step()."""
    return [(e, row * W + col, d) for (col, row, e, d) in LAYOUT]


if __name__ == "__main__":
    print(f"8x8 circuit demo: {len(LAYOUT)} actions (same shape as gears, "
          f"different recipe set mod-side)")
    for col, row, e, d in LAYOUT:
        ent_name = {0: "belt", 1: "inserter", 2: "assembler", 3: "no-op"}[e]
        dir_name = ["N", "E", "S", "W"][d]
        print(f"  col={col} row={row} -> place {ent_name:<10s} facing {dir_name}")
