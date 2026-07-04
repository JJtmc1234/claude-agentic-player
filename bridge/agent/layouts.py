"""Declarative chain layouts using the geometry helpers.

Each plan_*() returns a `LineSpec` describing where every entity should go.
The Agent can then execute the spec with .place_layout(). No alignment math
in calling code — that's all encapsulated here.
"""
from __future__ import annotations
from dataclasses import dataclass, field
from typing import List, Tuple, Optional

from agent.geometry import (
    DIR_NORTH, DIR_SOUTH, DIR_EAST, DIR_WEST, DIR_VECTORS,
    snap_2x2_center, snap_1x1_center, snap_3x3_center,
    drill_drop_position, electric_drill_output_tile, direction_toward,
    inserter_pickup_for_drill, inserter_pickup_for_furnace,
    SMALL_POLE_SUPPLY_AREA, SMALL_POLE_WIRE_DISTANCE,
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
    The drill's drop goes directly into the furnace input (touching adjacency).

    IMPORTANT placement order: drill is placed LAST. If drill is placed first
    and fueled, it spam-drops mined ore onto the future furnace tile, which then
    blocks furnace placement (item-on-ground entity in the way). Verified live
    2026-06-20."""
    dx, dy = snap_2x2_center(drill_ore_x, drill_ore_y)
    fx, fy = snap_2x2_center(dx, dy + 2)
    ix, iy = inserter_pickup_for_furnace(fx, fy, inserter_side=DIR_SOUTH)
    cx, cy = snap_1x1_center(ix, iy + 1)
    return LineSpec(
        name=f"iron smelt line @ drill ({dx},{dy})",
        # ORDER MATTERS: chest → inserter → furnace → drill (downstream first).
        placements=[
            Placement('wooden-chest', cx, cy, 0, 'collects plates'),
            Placement('burner-inserter', ix, iy, DIR_NORTH,
                      'picks N from furnace, drops S to chest'),
            Placement('stone-furnace', fx, fy, 0, 'receives ore from drill'),
            Placement('burner-mining-drill', dx, dy, DIR_SOUTH,
                      'on ore, drops S — placed LAST so it doesnt spam-drop on furnace spot'),
        ],
        fuel=[
            ('burner-mining-drill', dx, dy, 'wood', 5),
            ('stone-furnace', fx, fy, 'wood', 5),
            ('burner-inserter', ix, iy, 'wood', 3),
        ],
    )


def plan_multi_drill_line(drill_ore_x: float, drill_ore_y: float,
                          n_drills: int = 2,
                          spacing_x: int = 3) -> LineSpec:
    """N drills side-by-side, each with its own furnace+inserter, sharing chest column.

    For n_drills=2, spacing_x=3:
      Drill 0 at (dx, dy), furnace (dx, dy+2), inserter (dx+0.5, dy+3.5), chest (dx+0.5, dy+4.5)
      Drill 1 at (dx+3, dy), furnace (dx+3, dy+2), inserter (dx+3.5, dy+3.5), chest (dx+3.5, dy+4.5)
    Doubles iron-plate throughput. Per JJ's multi-machine target."""
    dx0, dy0 = snap_2x2_center(drill_ore_x, drill_ore_y)
    placements = []
    fuel = []
    for i in range(n_drills):
        dx, dy = dx0 + i * spacing_x, dy0
        fx, fy = snap_2x2_center(dx, dy + 2)
        ix, iy = inserter_pickup_for_furnace(fx, fy, inserter_side=DIR_SOUTH)
        cx, cy = snap_1x1_center(ix, iy + 1)
        # Downstream-first order PER CHAIN (chest, inserter, furnace, drill)
        placements.append(Placement('wooden-chest', cx, cy, 0, f'chain {i} chest'))
        placements.append(Placement('burner-inserter', ix, iy, DIR_NORTH, f'chain {i} inserter'))
        placements.append(Placement('stone-furnace', fx, fy, 0, f'chain {i} furnace'))
        placements.append(Placement('burner-mining-drill', dx, dy, DIR_SOUTH, f'chain {i} drill'))
        fuel.extend([
            ('burner-mining-drill', dx, dy, 'wood', 5),
            ('stone-furnace', fx, fy, 'wood', 5),
            ('burner-inserter', ix, iy, 'wood', 3),
        ])
    return LineSpec(
        name=f"multi-drill x{n_drills} @ ore ({dx0},{dy0})",
        placements=placements,
        fuel=fuel,
        notes=f"{n_drills} parallel chains. Per chain output goes to its own chest. "
              "Could be unified later via belt + splitter."
    )


def plan_steel_smelt(chest_in_x: float, chest_in_y: float,
                     iron_per_steel: int = 5) -> LineSpec:
    """Steel line: chest of iron-plate → inserter → stone-furnace (steel-plate recipe)
    → inserter → chest of steel-plate.

    Stone furnace can smelt steel-plate (5 iron → 1 steel) without needing
    a smelting tech in 2.0 if the recipe is set. Set via furnace.set_recipe('steel-plate')
    or use a steel-furnace which has steel as default. We use stone-furnace + set_recipe."""
    icx, icy = snap_1x1_center(chest_in_x, chest_in_y)
    # input inserter east of chest, dir=W (picks west from chest)
    iicx, iicy = snap_1x1_center(icx + 1, icy)
    # furnace east of input inserter, dir=0
    ffx, ffy = snap_2x2_center(iicx + 1.5, iicy)
    # output inserter east of furnace, dir=W (picks west from furnace)
    oicx, oicy = snap_1x1_center(ffx + 1.5, ffy)
    # output chest east of output inserter
    ocx, ocy = snap_1x1_center(oicx + 1, oicy)
    return LineSpec(
        name=f"steel smelt @ ({ffx},{ffy})",
        placements=[
            Placement('wooden-chest', ocx, ocy, 0, 'steel-plate output'),
            Placement('burner-inserter', oicx, oicy, DIR_WEST, 'picks W from furnace, drops E to out chest'),
            Placement('stone-furnace', ffx, ffy, 0, 'steel recipe (set via API)'),
            Placement('burner-inserter', iicx, iicy, DIR_WEST, 'picks W from input chest, drops E to furnace'),
            Placement('wooden-chest', icx, icy, 0, 'iron-plate input'),
        ],
        fuel=[
            ('stone-furnace', ffx, ffy, 'coal', 5),
            ('burner-inserter', iicx, iicy, 'coal', 2),
            ('burner-inserter', oicx, oicy, 'coal', 2),
        ],
        notes=(
            f"Each steel-plate costs {iron_per_steel} iron-plate and ~16 sec to smelt.\n"
            "After placing, call: surface.find_entities_filtered{position=furnace_pos, name='stone-furnace'}[1].set_recipe('steel-plate')\n"
            "Top up input chest with iron-plate periodically (or pipe in from iron line)."
        ),
    )


def plan_wall_turret_segment(start_x: float, start_y: float, length: int = 8,
                             direction: str = 'east') -> LineSpec:
    """Defensive segment: alternating wall+turret along a line.

    Pattern (east-going, length 8):
      W T W W T W W T W W T W W T W W   (W=stone-wall, T=gun-turret)
    Spacing: every 3rd tile is a turret to give them overlapping fire arcs.

    REQUIRES: stone-wall recipe (Automation 1) + gun-turret recipe (Military 1) +
    firearm-magazine ammo. JJ has 200 magazines from the spaceship loot, but the
    turret recipe is gated on research. Plan is ready for once Military is unlocked.
    """
    sx, sy = snap_1x1_center(start_x, start_y)
    placements = []
    for i in range(length):
        if direction == 'east':
            x, y = sx + i, sy
        elif direction == 'south':
            x, y = sx, sy + i
        else:
            raise ValueError(f"direction must be 'east' or 'south', got {direction}")
        x, y = snap_1x1_center(x, y)
        # Every 3rd position is a turret
        if i % 3 == 1:
            placements.append(Placement('gun-turret', x, y, 0, f'turret {i//3}'))
        else:
            placements.append(Placement('stone-wall', x, y, 0, f'wall'))
    return LineSpec(
        name=f"wall+turret segment {direction} from ({sx},{sy}) length={length}",
        placements=placements,
        fuel=[],
        notes=(
            "Load each turret with firearm-magazines via insert_into_entity "
            "(slot = defines.inventory.turret_ammo). "
            "Pattern is wall-turret-wall-wall-turret-wall (turret every 3rd tile)."
        ),
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


def plan_belt_run(start: Tuple[float, float], end: Tuple[float, float],
                  belt_item: str = 'transport-belt',
                  first: str = 'h') -> LineSpec:
    """A straight or L-shaped transport-belt path from `start` to `end` tile.

    Belt `direction` = the direction items MOVE (the belt's output side). Each belt
    in the path faces toward the NEXT tile; at an L-corner the corner belt faces the
    turn (vertical) direction so items flow around it. The final belt keeps the
    heading of the segment that fed it (items run off the end).

    `first`: for an L-shape, 'h' goes horizontal-then-vertical (corner at end_x,start_y),
    'v' goes vertical-then-horizontal (corner at start_x,end_y). Ignored when the run
    is already straight (shared x or y).

    Coords are snapped to 1x1 (*.5) tile centers, so the path steps by whole tiles.
    """
    sx, sy = snap_1x1_center(*start)
    ex, ey = snap_1x1_center(*end)

    # Build the ordered list of tile centers along the path.
    tiles: List[Tuple[float, float]] = []

    def _line(ax, ay, bx, by):
        """Inclusive tile walk from (ax,ay) to (bx,by) along one axis."""
        pts = []
        if ax == bx:
            step = 1 if by >= ay else -1
            n = int(round(abs(by - ay)))
            for k in range(n + 1):
                pts.append((ax, ay + step * k))
        else:
            step = 1 if bx >= ax else -1
            n = int(round(abs(bx - ax)))
            for k in range(n + 1):
                pts.append((ax + step * k, ay))
        return pts

    if sx == ex or sy == ey:
        tiles = _line(sx, sy, ex, ey)
    elif first == 'h':
        corner = (ex, sy)
        tiles = _line(sx, sy, *corner)          # horizontal leg incl. corner
        tiles += _line(*corner, ex, ey)[1:]      # vertical leg, skip dup corner
    elif first == 'v':
        corner = (sx, ey)
        tiles = _line(sx, sy, *corner)          # vertical leg incl. corner
        tiles += _line(*corner, ex, ey)[1:]      # horizontal leg, skip dup corner
    else:
        raise ValueError(f"first must be 'h' or 'v', got {first!r}")

    placements = []
    for i, (tx, ty) in enumerate(tiles):
        if i + 1 < len(tiles):
            d = direction_toward((tx, ty), tiles[i + 1])
        else:
            d = placements[-1].direction if placements else DIR_EAST
        placements.append(Placement(belt_item, tx, ty, d, f'belt {i}'))

    return LineSpec(
        name=f"belt run ({sx},{sy})->({ex},{ey}) {first if sx!=ex and sy!=ey else 'straight'}",
        placements=placements,
        fuel=[],
        notes=f"{len(placements)} belts. direction = item-flow (output side).",
    )


def plan_electric_drill_array(patch_center: Tuple[float, float],
                              rows: int = 2, cols: int = 4,
                              drill_dir: int = DIR_SOUTH,
                              belt_flow: int = DIR_EAST) -> LineSpec:
    """Scalable electric-mining-drill array over an ore patch, centred on `patch_center`.

    Geometry (all from base prototypes — see geometry.py):
      * electric-mining-drill is 3x3, snaps to *.5 centres.
      * Column pitch = 3 (footprints edge-to-edge, no gap).
      * Row pitch = 5: drill row (3 tiles) + belt lane (1 tile, catches the drops at
        centre+2 south) + pole strip (1 tile, holds small-electric-poles). This keeps
        belts, poles and drill footprints on mutually-disjoint tiles.
      * Each drill drops on its own centre column (vector_to_place_result X offset = 0),
        so the belt lane tile under a drill is exactly (drill_x, drill_y+2) for south.

    Power: small-electric-pole supply_area_distance=2.5, wire<=7.5. Poles sit in the
    strip 3 tiles south of each drill row (within reach of that row AND the next row's
    drills), one pole per 2 columns (x offset +1.5 covers the adjacent column pair).
    Pole strips are 5 apart in Y (<=7.5 wire) so the network stays connected.

    Electric entities need NO burner fuel, so `fuel` is empty. Placement order is
    poles -> belts -> drills (downstream/support first, drills last).

    Currently supports drill_dir=DIR_SOUTH + belt_flow horizontal (the common case);
    raises for other orientations rather than emitting an unverified layout.
    """
    if drill_dir != DIR_SOUTH:
        raise NotImplementedError("plan_electric_drill_array currently supports drill_dir=DIR_SOUTH")
    if belt_flow not in (DIR_EAST, DIR_WEST):
        raise ValueError("belt_flow must be DIR_EAST or DIR_WEST")

    pcx, pcy = patch_center
    col_pitch, row_pitch = 3, 5
    # Anchor: top-left drill centre so the drill grid is centred on patch_center.
    cx0, cy0 = snap_3x3_center(pcx - (cols - 1) * col_pitch / 2.0,
                               pcy - (rows - 1) * row_pitch / 2.0)

    poles: List[Placement] = []
    belts: List[Placement] = []
    drills: List[Placement] = []

    for r in range(rows):
        row_y = cy0 + r * row_pitch
        # --- drills in this row ---
        for c in range(cols):
            dx = cx0 + c * col_pitch
            drills.append(Placement('electric-mining-drill', dx, row_y, drill_dir,
                                    f'r{r}c{c} drill'))
        # --- belt lane: continuous run catching every drop, flowing belt_flow ---
        bx0, by = electric_drill_output_tile(cx0, row_y, drill_dir)
        bx_last, _ = electric_drill_output_tile(cx0 + (cols - 1) * col_pitch, row_y, drill_dir)
        lane = plan_belt_run((bx0, by), (bx_last, by),
                             belt_item='transport-belt', first='h')
        # Force flow direction (a 1-row run defaults to EAST; honor belt_flow=WEST too)
        if belt_flow == DIR_WEST:
            lane = plan_belt_run((bx_last, by), (bx0, by), first='h')
        for p in lane.placements:
            belts.append(Placement(p.item, p.x, p.y, p.direction, f'r{r} {p.note}'))
        # --- pole strip: 1 tile south of the belt lane, one pole per 2 columns ---
        pole_y = row_y + 3
        for c in range(0, cols, 2):
            px = cx0 + c * col_pitch + 1.5   # between column c and c+1
            px, py = snap_1x1_center(px, pole_y)
            poles.append(Placement('small-electric-pole', px, py, 0, f'r{r} pole'))

    placements = poles + belts + drills
    return LineSpec(
        name=f"electric drill array {rows}x{cols} @ {patch_center}",
        placements=placements,
        fuel=[],   # electric drills + belts + poles: no burner fuel
        notes=(
            f"{rows*cols} electric-mining-drills, {len(belts)} belts, {len(poles)} poles. "
            "Each row's belt lane is independent (merge lanes with plan_belt_run + a "
            "splitter on the output side). Drills face south, drop into the lane at "
            "centre+2; poles sit 3 tiles south of each row (supply<=2.5 reaches drill "
            "edges, wire<=7.5 keeps strips connected). No fuel — all electric."
        ),
    )


def execute_layout(agent, spec: LineSpec, clear_blockers: bool = True,
                   mine_resources: bool = True) -> list:
    """Execute a LineSpec via the agent. Returns list of placement results.

    `mine_resources=True` (default) lets the furnace/inserter/chest placements
    consume any ore tiles in their footprint — important on dense ore patches
    where the iron-smelt-line's furnace would otherwise fail placement.
    Drills are intentionally NOT mine_resources (they need to be on ore).
    """
    results = []
    for p in spec.placements:
        # Drills want resources under them; everything else can consume them
        mine = mine_resources and not p.item.endswith('-mining-drill')
        res = agent.placement.place(p.item, p.x, p.y, p.direction,
                                    clear_blockers=clear_blockers,
                                    mine_resources=mine)
        results.append(res)
        if not res.get('ok'):
            break
    for entry in spec.fuel:
        agent.fuel.fuel(*entry[:3], fuel_item=entry[3], want_amount=entry[4])
    return results
