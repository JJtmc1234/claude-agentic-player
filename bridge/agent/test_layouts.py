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
                            plan_wall_turret_segment)


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


if __name__ == '__main__':
    main()
