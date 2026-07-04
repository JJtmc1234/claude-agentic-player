"""Pure-Python unit tests for geometry math (no RCON / no server needed).
Run with: python -m bridge.agent.test_geometry  OR  python bridge/agent/test_geometry.py"""
from __future__ import annotations
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BRIDGE = _HERE.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from agent.geometry import (
    snap_2x2_center, snap_1x1_center, snap_3x3_center,
    drill_drop_position,
    electric_drill_drop_position, electric_drill_output_tile, direction_toward,
    inserter_pickup_for_drill, inserter_pickup_for_furnace,
    DIR_NORTH, DIR_SOUTH, DIR_EAST, DIR_WEST, opposite_direction,
)


def near(a, b, eps=1e-3):
    return abs(a - b) < eps


def check(name, expected, actual):
    if expected == actual or (
        isinstance(expected, tuple) and isinstance(actual, tuple)
        and all(near(e, a) for e, a in zip(expected, actual))
    ):
        print(f"  PASS  {name}")
        return True
    print(f"  FAIL  {name}: expected {expected}, got {actual}")
    return False


def main():
    print("snap_2x2_center:")
    check("(-14.5, 50.5) -> (-14, 51)", (-14, 51), snap_2x2_center(-14.5, 50.5))
    check("(87.3, 41.8) -> (87, 42)", (87, 42), snap_2x2_center(87.3, 41.8))

    print("snap_1x1_center:")
    check("(-14, 55) -> (-13.5, 55.5)", (-13.5, 55.5), snap_1x1_center(-14, 55))
    check("(-14, 54.5) -> (-13.5, 54.5)", (-13.5, 54.5), snap_1x1_center(-14, 54.5))
    check("(87, 45.5) -> (87.5, 45.5)", (87.5, 45.5), snap_1x1_center(87, 45.5))

    print("drill_drop_position (south-facing):")
    # Verified empirically against live server day 2: drill at (87, 42) drops at (87.5, 43.296875)
    check("(87, 42) south -> (87.5, 43.296875)",
          (87.5, 43.296875), drill_drop_position(87, 42, DIR_SOUTH))

    print("inserter_pickup_for_drill (south-facing):")
    # For drill at (87, 42), inserter should be at (87.5, 44.5) per the verified layout.
    check("(87, 42) south -> (87.5, 44.5)",
          (87.5, 44.5), inserter_pickup_for_drill(87, 42, DIR_SOUTH))

    print("inserter_pickup_for_furnace (south side):")
    # Iron-line: furnace (-14, 53), inserter (-13.5, 54.5) verified
    check("(-14, 53) south -> (-13.5, 54.5)",
          (-13.5, 54.5), inserter_pickup_for_furnace(-14, 53, DIR_SOUTH))
    # Copper-line: furnace (-11, 52), inserter (-10.5, 53.5) verified
    check("(-11, 52) south -> (-10.5, 53.5)",
          (-10.5, 53.5), inserter_pickup_for_furnace(-11, 52, DIR_SOUTH))

    print("opposite_direction:")
    check("N <-> S", DIR_NORTH, opposite_direction(DIR_SOUTH))
    check("E <-> W", DIR_WEST, opposite_direction(DIR_EAST))

    print("snap_3x3_center (odd dim -> *.5, like 1x1):")
    check("(0, 0) -> (0.5, 0.5)", (0.5, 0.5), snap_3x3_center(0, 0))
    check("(-4.5, -2.5) stays", (-4.5, -2.5), snap_3x3_center(-4.5, -2.5))

    print("electric_drill_drop_position (offset 1.85, X-centered):")
    # south-facing 3x3 drill at (0.5, 0.5) drops at (0.5, 2.35)
    check("(0.5,0.5) south -> (0.5, 2.35)",
          (0.5, 2.35), electric_drill_drop_position(0.5, 0.5, DIR_SOUTH))
    check("(0.5,0.5) north -> (0.5, -1.35)",
          (0.5, -1.35), electric_drill_drop_position(0.5, 0.5, DIR_NORTH))

    print("electric_drill_output_tile (belt tile beyond footprint):")
    check("(0.5,0.5) south -> (0.5, 2.5)",
          (0.5, 2.5), electric_drill_output_tile(0.5, 0.5, DIR_SOUTH))
    check("(0.5,0.5) east -> (2.5, 0.5)",
          (2.5, 0.5), electric_drill_output_tile(0.5, 0.5, DIR_EAST))

    print("direction_toward:")
    check("east", DIR_EAST, direction_toward((0.5, 0.5), (1.5, 0.5)))
    check("north", DIR_NORTH, direction_toward((0.5, 0.5), (0.5, -1.5)))


if __name__ == '__main__':
    main()
