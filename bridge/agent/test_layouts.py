"""Layout-plan tests — verify each plan produces the day-2 verified coords."""
from __future__ import annotations
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BRIDGE = _HERE.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from agent.layouts import (plan_iron_smelt_line, plan_drill_to_chest,
                            plan_multi_drill_line, plan_steel_smelt,
                            plan_wall_turret_segment,
                            plan_belt_run, plan_electric_drill_array)
from agent.geometry import DIR_NORTH, DIR_SOUTH, DIR_EAST, DIR_WEST


def _occupied_tiles(placements):
    """Return list of integer tile-index sets each entity occupies (drill=3x3, else 1x1)."""
    import math
    sets = []
    for p in placements:
        size = 3 if p.item == 'electric-mining-drill' else 1
        half = size / 2.0
        x0 = int(math.floor(p.x - half))
        y0 = int(math.floor(p.y - half))
        tiles = {(x0 + i, y0 + j) for i in range(size) for j in range(size)}
        sets.append(tiles)
    return sets


def check(name, want, got):
    if want == got:
        print(f"  PASS  {name}")
        return True
    print(f"  FAIL  {name}: want {want}, got {got}")
    return False


def main():
    print("plan_iron_smelt_line at ore (-14.5, 50.5):")
    spec = plan_iron_smelt_line(-14.5, 50.5)
    # Day 2 verified: drill (-14, 51), furnace (-14, 53), inserter (-13.5, 54.5), chest (-13.5, 55.5)
    # Order is now chest first, drill LAST (downstream-first to avoid drill spam-drop)
    p = spec.placements
    check("chest pos (first)", (-13.5, 55.5), (p[0].x, p[0].y))
    check("chest is wooden-chest", 'wooden-chest', p[0].item)
    check("inserter pos", (-13.5, 54.5), (p[1].x, p[1].y))
    check("inserter dir=NORTH(0)", 0, p[1].direction)
    check("furnace pos", (-14.0, 53.0), (p[2].x, p[2].y))
    check("furnace is stone-furnace", 'stone-furnace', p[2].item)
    check("drill pos (last)", (-14.0, 51.0), (p[3].x, p[3].y))
    check("drill is burner-mining-drill", 'burner-mining-drill', p[3].item)
    check("fuel entries", 3, len(spec.fuel))

    print("plan_drill_to_chest at copper (87.5, 41.5):")
    # Asking for (87.5, 41.5) -> snap_2x2_center round-half-up -> (88, 42).
    # Chest 1x1 at drill drop tile = (drill_cx+0.5, drill_cy+1.5) = (88.5, 43.5).
    # Day 2's actual copper drill landed at (87, 42) because we asked for
    # INTEGER (87, 42) directly via _auto_copper.py — no snap involved.
    # The earlier (86.5, 40.5) attempt did snap (-> 87, 41) consistently with round-half-up.
    spec = plan_drill_to_chest(87.5, 41.5)
    p = spec.placements
    check("drill pos", (88.0, 42.0), (p[0].x, p[0].y))
    check("chest pos (drop tile)", (88.5, 43.5), (p[1].x, p[1].y))

    print("plan_drill_to_chest at (-14.5, 89.5):")
    # Negative coords: -14.5 should snap to -14 (round-half-up = round toward +inf)
    spec = plan_drill_to_chest(-14.5, 89.5)
    p = spec.placements
    check("drill pos", (-14.0, 90.0), (p[0].x, p[0].y))
    check("chest pos", (-13.5, 91.5), (p[1].x, p[1].y))

    print("plan_multi_drill_line at (-14.5, 50.5) x2:")
    spec = plan_multi_drill_line(-14.5, 50.5, n_drills=2, spacing_x=3)
    check("4 entities per chain x 2 chains", 8, len(spec.placements))
    check("3 fuel entries per chain x 2 chains", 6, len(spec.fuel))
    # Chain 0 ends with drill at (-14, 51), chain 1's drill at (-11, 51)
    drills = [p for p in spec.placements if p.item == 'burner-mining-drill']
    check("drill 0 x", -14.0, drills[0].x)
    check("drill 1 x (shifted by spacing)", -11.0, drills[1].x)

    print("plan_steel_smelt at chest (10, 10):")
    spec = plan_steel_smelt(10, 10)
    check("5 entities (chest+ins+furnace+ins+chest)", 5, len(spec.placements))
    items = [p.item for p in spec.placements]
    check("first is output chest", 'wooden-chest', items[0])
    check("last is input chest", 'wooden-chest', items[-1])
    check("middle is furnace", 'stone-furnace', items[2])

    print("plan_wall_turret_segment east length=8:")
    spec = plan_wall_turret_segment(0, 0, length=8, direction='east')
    check("8 placements", 8, len(spec.placements))
    types = [p.item for p in spec.placements]
    # Pattern: W T W W T W W T   (turret every 3rd starting index 1)
    expected = ['stone-wall' if i % 3 != 1 else 'gun-turret' for i in range(8)]
    check("pattern matches W-T-W-W-T-W-W-T", expected, types)

    print("plan_belt_run straight east (0.5,0.5)->(4.5,0.5):")
    spec = plan_belt_run((0.5, 0.5), (4.5, 0.5))
    p = spec.placements
    check("5 belts (inclusive)", 5, len(p))
    check("all transport-belt", True, all(b.item == 'transport-belt' for b in p))
    check("all flow EAST", True, all(b.direction == DIR_EAST for b in p))
    check("start tile", (0.5, 0.5), (p[0].x, p[0].y))
    check("end tile", (4.5, 0.5), (p[-1].x, p[-1].y))

    print("plan_belt_run straight north (0.5,4.5)->(0.5,0.5):")
    spec = plan_belt_run((0.5, 4.5), (0.5, 0.5))
    p = spec.placements
    check("5 belts", 5, len(p))
    check("all flow NORTH", True, all(b.direction == DIR_NORTH for b in p))

    print("plan_belt_run L-shape first=h (0.5,0.5)->(3.5,2.5):")
    # horizontal leg y=0.5 x:0.5..3.5 (corner 3.5,0.5), then vertical x=3.5 y:0.5..2.5
    spec = plan_belt_run((0.5, 0.5), (3.5, 2.5), first='h')
    p = spec.placements
    check("6 belts (4 horiz + 2 new vert; corner shared)", 6, len(p))
    # corner belt is at (3.5, 0.5); it must face SOUTH (toward next vertical tile)
    corner = [b for b in p if (b.x, b.y) == (3.5, 0.5)][0]
    check("corner faces SOUTH (turn)", DIR_SOUTH, corner.direction)
    check("pre-corner faces EAST", DIR_EAST, p[2].direction)
    check("last belt faces SOUTH", DIR_SOUTH, p[-1].direction)
    # no two belts on same tile
    tiles = [(b.x, b.y) for b in p]
    check("belt tiles unique", len(tiles), len(set(tiles)))

    print("plan_belt_run L-shape first=v (0.5,0.5)->(3.5,2.5):")
    spec = plan_belt_run((0.5, 0.5), (3.5, 2.5), first='v')
    p = spec.placements
    check("6 belts", 6, len(p))
    corner = [b for b in p if (b.x, b.y) == (0.5, 2.5)][0]
    check("corner (0.5,2.5) faces EAST", DIR_EAST, corner.direction)

    print("plan_electric_drill_array 2x4 @ (0,0):")
    spec = plan_electric_drill_array((0, 0), rows=2, cols=4)
    drills = [p for p in spec.placements if p.item == 'electric-mining-drill']
    belts = [p for p in spec.placements if p.item == 'transport-belt']
    poles = [p for p in spec.placements if p.item == 'small-electric-pole']
    check("8 drills (2x4)", 8, len(drills))
    check("20 belts (2 rows x 10)", 20, len(belts))
    check("4 poles (2 rows x ceil(4/2))", 4, len(poles))
    check("no burner fuel (electric)", 0, len(spec.fuel))
    check("drills face SOUTH", True, all(d.direction == DIR_SOUTH for d in drills))
    # Belt lane sits exactly 2 tiles south of its drill row (catches the drop).
    row0_drill_y = min(d.y for d in drills)
    lane_ys = sorted({b.y for b in belts})
    check("belt lane row0 = drill_y+2", row0_drill_y + 2, lane_ys[0])
    # NO OVERLAP: total occupied tiles == sum of per-entity tile counts.
    sets = _occupied_tiles(spec.placements)
    union = set().union(*sets)
    total = sum(len(s) for s in sets)
    check("no overlapping footprints (2x4)", total, len(union))

    print("plan_electric_drill_array 3x5 @ (10,-6) scales:")
    spec = plan_electric_drill_array((10, -6), rows=3, cols=5)
    drills = [p for p in spec.placements if p.item == 'electric-mining-drill']
    belts = [p for p in spec.placements if p.item == 'transport-belt']
    poles = [p for p in spec.placements if p.item == 'small-electric-pole']
    check("15 drills (3x5)", 15, len(drills))
    check("39 belts (3 rows x 13)", 39, len(belts))
    check("9 poles (3 rows x ceil(5/2))", 9, len(poles))
    sets = _occupied_tiles(spec.placements)
    union = set().union(*sets)
    total = sum(len(s) for s in sets)
    check("no overlapping footprints (3x5)", total, len(union))
    # Adjacent drills in a row are exactly 3 apart (edge-to-edge 3x3).
    row_drills = sorted([d for d in drills if d.y == min(x.y for x in drills)],
                        key=lambda d: d.x)
    check("column pitch = 3", 3.0, row_drills[1].x - row_drills[0].x)


if __name__ == '__main__':
    main()
