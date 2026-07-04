"""Tile-snap geometry — the math we keep getting wrong in ad-hoc scripts.

Factorio 2.0 snap rules (verified):
- 1x1 entities (chest, inserter, pipe, pole) snap to half-integer centers (x.5, y.5)
- 2x2 entities (burner-drill, stone-furnace) snap to integer centers (x, y)
- 3x2 entities (boiler) snap to (x, y.5) for the 2-wide axis
- 2x3 entities (steam-engine in some orientations) snap to (x.5, y)

Burner-mining-drill drop offset (Factorio 2.0): center + (0.5, 1.296875) for south-facing.
That means the drop point is INSIDE tile (cx, cy+1) — first row south of drill, NOT second.

Inserter dir = side it PICKS FROM (not where it drops to). dir=0 (north) means
pickup at center+(0,-1), drop at center+(0,+1).
"""
from __future__ import annotations
import math
from typing import Tuple


def _round_half_up(x: float) -> int:
    """Round half AWAY from negative infinity (matches Factorio's snap behavior).
    Python's built-in round() uses banker's rounding (half-to-even), which
    disagrees with the game on integer-and-half target positions."""
    return int(math.floor(x + 0.5))


# Cardinal direction → unit vector (dx, dy). Matches Factorio defines.direction.
DIR_NORTH = 0
DIR_EAST  = 4
DIR_SOUTH = 8
DIR_WEST  = 12
DIR_VECTORS = {
    DIR_NORTH: (0, -1),
    DIR_EAST:  (1,  0),
    DIR_SOUTH: (0,  1),
    DIR_WEST:  (-1, 0),
}


def snap_2x2_center(target_x: float, target_y: float) -> Tuple[float, float]:
    """2x2 entities (drill, furnace) snap to integer centers. Round half UP."""
    return (float(_round_half_up(target_x)), float(_round_half_up(target_y)))


def snap_1x1_center(target_x: float, target_y: float) -> Tuple[float, float]:
    """1x1 entities (chest, inserter, pipe, pole) snap to *.5 centers. Round half UP."""
    return (_round_half_up(target_x - 0.5) + 0.5, _round_half_up(target_y - 0.5) + 0.5)


def drill_drop_position(drill_cx: float, drill_cy: float, direction: int = DIR_SOUTH) -> Tuple[float, float]:
    """Where a 2x2 burner-mining-drill drops items, given its center + facing direction.
    Verified for burner-mining-drill in 2.0 — offset is 1.296875 along facing axis.
    """
    dx, dy = DIR_VECTORS[direction]
    OFFSET = 1.296875
    # drop is 0.5 perpendicular for x-axis on south-facing... actually the
    # actual observed drop is (cx+0.5, cy+1.296875) for south-facing. The +0.5
    # on x is consistent with the drill being a 2-tile entity that drops
    # centered on its perpendicular axis. For simplicity match the empirical:
    if direction == DIR_SOUTH:
        return (drill_cx + 0.5, drill_cy + OFFSET)
    if direction == DIR_NORTH:
        return (drill_cx + 0.5, drill_cy - OFFSET)
    if direction == DIR_EAST:
        return (drill_cx + OFFSET, drill_cy + 0.5)
    if direction == DIR_WEST:
        return (drill_cx - OFFSET, drill_cy + 0.5)
    raise ValueError(f"unsupported direction {direction}")


def inserter_pickup_for_drill(drill_cx: float, drill_cy: float,
                              direction: int = DIR_SOUTH) -> Tuple[float, float]:
    """1x1 inserter position to pick up from drill drop tile."""
    dx, dy = drill_drop_position(drill_cx, drill_cy, direction)
    perp_x, perp_y = DIR_VECTORS[direction]
    # Inserter is one tile further along facing direction than drop point.
    # Snap to 1x1 grid.
    if direction == DIR_SOUTH:
        return snap_1x1_center(drill_cx + 0.5, drill_cy + 2.5)
    if direction == DIR_NORTH:
        return snap_1x1_center(drill_cx + 0.5, drill_cy - 2.5)
    if direction == DIR_EAST:
        return snap_1x1_center(drill_cx + 2.5, drill_cy + 0.5)
    if direction == DIR_WEST:
        return snap_1x1_center(drill_cx - 2.5, drill_cy + 0.5)
    raise ValueError(f"unsupported direction {direction}")


def inserter_pickup_for_furnace(furnace_cx: float, furnace_cy: float,
                                inserter_side: int = DIR_SOUTH) -> Tuple[float, float]:
    """1x1 inserter position to pick up from a 2x2 furnace, placed on `inserter_side`.
    Returns the inserter's CENTER. Its `direction` should be the OPPOSITE of inserter_side
    (because direction = pickup side, and pickup is the furnace which is OPPOSITE
    of inserter's own side relative to furnace).
    """
    if inserter_side == DIR_SOUTH:
        return snap_1x1_center(furnace_cx, furnace_cy + 1)
    if inserter_side == DIR_NORTH:
        return snap_1x1_center(furnace_cx, furnace_cy - 1)
    if inserter_side == DIR_EAST:
        return snap_1x1_center(furnace_cx + 1, furnace_cy)
    if inserter_side == DIR_WEST:
        return snap_1x1_center(furnace_cx - 1, furnace_cy)
    raise ValueError(f"unsupported side {inserter_side}")


def opposite_direction(d: int) -> int:
    return {DIR_NORTH: DIR_SOUTH, DIR_SOUTH: DIR_NORTH,
            DIR_EAST: DIR_WEST, DIR_WEST: DIR_EAST}[d]


# --- electric-mining-drill (3x3) + small-electric-pole constants ---------------
# Source: base/prototypes/entity/mining-drill.lua (electric-mining-drill, ~line 259)
#   selection_box = {{-1.5,-1.5},{1.5,1.5}}  -> 3x3 footprint (odd dim -> *.5 center)
#   vector_to_place_result = {0, -1.85}      -> drop 1.85 tiles along facing, X-CENTERED
#     (NOTE: unlike the burner-mining-drill whose drop is offset +0.5 in X, the
#      electric drill drops on its own centre column — X offset is 0.)
#   resource_searching_radius = 2.49
# Source: base/prototypes/entity/entities.lua (small-electric-pole, ~line 1631)
#   supply_area_distance = 2.5   (half-side of the square supply area, from pole centre;
#     measured from the collision-box edge in-engine, so real coverage is >= this — 2.5
#     is the safe underestimate we plan against)
#   maximum_wire_distance = 7.5  (max centre-to-centre gap for two poles to auto-wire)
ELECTRIC_DRILL_DROP_OFFSET = 1.85
ELECTRIC_DRILL_SIZE = 3
SMALL_POLE_SUPPLY_AREA = 2.5
SMALL_POLE_WIRE_DISTANCE = 7.5


def snap_3x3_center(target_x: float, target_y: float) -> Tuple[float, float]:
    """3x3 entities (electric-mining-drill) have an ODD tile dimension, so — like 1x1 —
    they snap to *.5 centers (a 3x3 centred at 0.5 occupies tiles -1,0,1)."""
    return snap_1x1_center(target_x, target_y)


def electric_drill_drop_position(cx: float, cy: float,
                                 direction: int = DIR_SOUTH) -> Tuple[float, float]:
    """Continuous drop point of a 3x3 electric-mining-drill at centre (cx,cy).
    vector_to_place_result magnitude 1.85 along the facing axis; X (perp) offset is 0."""
    dx, dy = DIR_VECTORS[direction]
    return (cx + dx * ELECTRIC_DRILL_DROP_OFFSET, cy + dy * ELECTRIC_DRILL_DROP_OFFSET)


def electric_drill_output_tile(cx: float, cy: float,
                               direction: int = DIR_SOUTH) -> Tuple[float, float]:
    """The 1x1 belt tile that catches an electric drill's drop: one tile beyond the
    3x3 footprint along the facing direction. For south-facing: (cx, cy+2)."""
    dx, dy = DIR_VECTORS[direction]
    return snap_1x1_center(cx + dx * 2, cy + dy * 2)


def direction_toward(from_xy: Tuple[float, float],
                     to_xy: Tuple[float, float]) -> int:
    """Cardinal DIR_* pointing from one tile toward another (dominant axis wins).
    Used to orient each belt segment toward the next tile in a path."""
    fx, fy = from_xy
    tx, ty = to_xy
    if abs(tx - fx) >= abs(ty - fy):
        return DIR_EAST if tx > fx else DIR_WEST
    return DIR_SOUTH if ty > fy else DIR_NORTH
