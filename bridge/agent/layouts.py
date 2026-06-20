"""Declarative chain layouts using the geometry helpers.

Each plan_*() returns a `LineSpec` describing where every entity should go.
The Agent can then execute the spec with .place_layout(). No alignment math
in calling code — that's all encapsulated here.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from agent.geometry import (
    DIR_NORTH, DIR_SOUTH, DIR_EAST, DIR_WEST,
    snap_2x2_center, snap_1x1_center,
    drill_drop_position,
    inserter_pickup_for_drill, inserter_pickup_for_furnace,
)


@dataclass
class Placement:
    """One entity to place in a chain layout."""
    item: str
    x: float
    y: float
    direction: int = 0
    note: str = ''


@dataclass
class LineSpec:
    """A planned chain of placements."""
    name: str
    placements: List[Placement] = field(default_factory=list)
    fuel: List[Tuple[str, float, float, str, int]] = field(default_factory=list)
    notes: str = ''

    def at(self, i: int) -> Placement:
        return self.placements[i]


def plan_drill_to_chest(ore_x: float, ore_y: float, direction: int = DIR_SOUTH) -> LineSpec:
    """Direct drill → chest (no inserter). Chest is placed at the drill drop tile.
    Verified pattern: drill at (cx, cy), chest at (cx + 0.5, cy + 1.5) for south-facing."""
    dx, dy = snap_2x2_center(ore_x, ore_y)
    chest_x, chest_y = snap_1x1_center(dx + 0.5, dy + 1.5)
    return LineSpec(
        name=f"drill→chest @ ({dx},{dy})",
        placements=[
            Placement('burner-mining-drill', dx, dy, direction, 'drops south'),
            Placement('wooden-chest', chest_x, chest_y, 0, 'catches drop'),
        ],
        fuel=[
            ('burner-mining-drill', dx, dy, 'wood', 5),
        ],
    )


def plan_iron_smelt_line(drill_ore_x: float, drill_ore_y: float) -> LineSpec:
    """Iron line: drill (on ore) → furnace (south) → inserter → chest. All south-facing chain.
    The drill's drop goes directly into the furnace input (touching adjacency)."""
    dx, dy = snap_2x2_center(drill_ore_x, drill_ore_y)
    # Furnace at center (dx, dy+2.5)? Actually 2x2 at integer center,
    # one tile south of drill bottom edge means center at (dx, dy + 2).
    fx, fy = snap_2x2_center(dx, dy + 2)
    # Inserter 1 tile south of furnace south edge — for furnace at (fx, fy),
    # inserter Y target = fy + 1 (snaps to fy + 1.5)
    ix, iy = inserter_pickup_for_furnace(fx, fy, inserter_side=DIR_SOUTH)
    # Chest 1 tile south of inserter
    cx, cy = snap_1x1_center(ix, iy + 1)
    return LineSpec(
        name=f"iron smelt line @ drill ({dx},{dy})",
        placements=[
            Placement('burner-mining-drill', dx, dy, DIR_SOUTH, 'on ore, drops S'),
            Placement('stone-furnace', fx, fy, 0, 'receives ore from drill'),
            Placement('burner-inserter', ix, iy, DIR_NORTH,
                      'picks N from furnace, drops S to chest'),
            Placement('wooden-chest', cx, cy, 0, 'collects plates'),
        ],
        fuel=[
            ('burner-mining-drill', dx, dy, 'wood', 5),
            ('stone-furnace', fx, fy, 'wood', 5),
            ('burner-inserter', ix, iy, 'wood', 3),
        ],
    )


def plan_power_chain(water_x: float, water_y: float,
                     land_direction: str = 'east') -> LineSpec:
    """Plan an offshore-pump + boiler + steam-engine chain on a water/land edge.

    `land_direction` = which side of the water tile is land ('east' supported).
    Returns LineSpec but does NOT solve the boiler N/S water-input topology
    fully — see POWER_CHAIN.md for the precise layout we plan to deploy.

    The known constraints (from agentic-play day 2):
    - offshore-pump in 2.0 has FIXED output direction (auto-detected by terrain),
      NOT controlled by the `direction` argument. Query fluidbox.get_pipe_connections
      to learn where it connects, then place pipe at that target.
    - boiler 3x2 dir=4 (east-flow): water inputs are NORTH and SOUTH sides
      (perpendicular to flow), steam output is east (far end).
    - steam-engine 2x3 dir=4 (east-flow): steam input is west, electricity is automatic.
    - This means a clean linear east-flowing layout has the boiler perpendicular
      to water flow — pipes must elbow around to reach boiler's N or S input.
    """
    px, py = snap_1x1_center(water_x, water_y)
    notes = (
        "Run the connection-discovery sequence at deploy time:\n"
        "  1. Place pump at (px, py) — direction is ignored\n"
        "  2. Read pump.fluidbox.get_pipe_connections(1)[1].target_position\n"
        "  3. Place a pipe at that target, extend pipes toward land\n"
        "  4. Place boiler so its N or S water-input tile aligns with a pipe\n"
        "  5. Place engine east (or west) of boiler so its steam-input touches\n"
        "  6. Place small-electric-pole within 7.5 tiles of engine\n"
        "Don't trust direction args — verify via fluidbox API."
    )
    return LineSpec(
        name=f"power chain near water ({px},{py})",
        placements=[
            Placement('offshore-pump', px, py, 0,
                      'direction ignored; output auto-set by terrain'),
        ],
        notes=notes,
    )


def execute_layout(agent, spec: LineSpec, clear_blockers: bool = True) -> list:
    """Execute a LineSpec via the agent. Returns list of placement results."""
    results = []
    for p in spec.placements:
        res = agent.placement.place(p.item, p.x, p.y, p.direction,
                                    clear_blockers=clear_blockers)
        results.append(res)
        if not res.get('ok'):
            break
    for entry in spec.fuel:
        agent.fuel.fuel(*entry[:3], fuel_item=entry[3], want_amount=entry[4])
    return results
