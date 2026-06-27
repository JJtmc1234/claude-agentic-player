"""Autonomous power-chain builder — implements POWER_CHAIN.md's
discovery-driven procedure with can_place + fluidbox checks at every step.

Untested against live server (written 2026-06-20 while JJ playing).
Should work end-to-end IF the documented 2.0 constraints hold.

Usage:
    from agent import Agent
    from agent.power import build_power_chain
    with Agent.connect() as a:
        result = build_power_chain(a, water_hint_x=-41, water_hint_y=21)
        if result['ok']:
            print(f"Power live, engine producing {result['production']} W")
"""
from __future__ import annotations
import time
from typing import Optional, Dict, Any

from agent.geometry import DIR_EAST, snap_1x1_center


def _find_pump_friendly_water(agent, hint_x: float, hint_y: float,
                              radius: int = 30, max_tries: int = 20) -> Optional[Dict[str, float]]:
    """Find a water tile where placing a pump produces a connection target on LAND.
    Returns {water_x, water_y, target_x, target_y} or None.

    Iterative try-and-undo: place pump, query target, if target is water,
    take_back and try the next tile.
    """
    # Prefer water tiles whose SOUTH neighbor is land — those are where the
    # pump's auto-southward output target will land on a placeable tile.
    body = (
        "local c = game.get_entity_by_unit_number(" + str(agent.unit) + "); "
        "local s = c.surface; "
        f"local water = s.find_tiles_filtered{{position={{{hint_x},{hint_y}}}, radius={radius}, name={{'water','deepwater'}}}}; "
        "local edges = {}; local others = {}; "
        "for _, wt in ipairs(water) do "
        "  local wx, wy = wt.position.x, wt.position.y; "
        "  local cx, cy = wx + 0.5, wy + 0.5; "
        "  if s.can_place_entity{name='offshore-pump', position={cx,cy}, force='player', direction=0} then "
        "    local south = s.get_tile(wx, wy + 1); "
        "    local east = s.get_tile(wx + 1, wy); "
        "    local north = s.get_tile(wx, wy - 1); "
        "    local west = s.get_tile(wx - 1, wy); "
        "    local function isLand(t) return t and not (t.name == 'water' or t.name == 'deepwater') end; "
        "    if isLand(south) or isLand(north) or isLand(east) or isLand(west) then "
        "      table.insert(edges, string.format('%.1f,%.1f', cx, cy)) "
        "    else "
        "      table.insert(others, string.format('%.1f,%.1f', cx, cy)) "
        "    end "
        "  end "
        "end; "
        f"for i = 1, math.min({max_tries}, #edges) do rcon.print(edges[i]) end; "
        "if #edges == 0 then "
        f"  for i = 1, math.min({max_tries}, #others) do rcon.print(others[i]) end "
        "end"
    )
    out = agent.rcon.command('/silent-command ' + body).strip()
    if not out:
        return None
    candidates = [tuple(float(s) for s in line.split(',')) for line in out.split('\n') if ',' in line]

    # Place + query + take_back for each candidate until one has a land target
    for wx, wy in candidates:
        # Place
        place_body = (
            f"local s = game.surfaces['nauvis']; "
            f"local e = s.create_entity{{name='offshore-pump', position={{{wx},{wy}}}, force='player', direction=0}}; "
            "if not e then rcon.print('NO'); return end; "
            "local conn = e.fluidbox.get_pipe_connections(1)[1]; "
            "local tx, ty = conn.target_position.x, conn.target_position.y; "
            "local can = s.can_place_entity{name='pipe', position={tx,ty}, force='player'}; "
            "if can then "
            "  rcon.print(string.format('OK,%.1f,%.1f', tx, ty)) "
            "else "
            "  e.destroy(); "
            "  rcon.print(string.format('BAD,%.1f,%.1f', tx, ty)) "
            "end"
        )
        res = agent.rcon.command('/silent-command ' + place_body).strip()
        if res.startswith('OK,'):
            _, sx, sy = res.split(',')
            return {'water_x': wx, 'water_y': wy, 'target_x': float(sx), 'target_y': float(sy)}
    return None


def _read_pump_connection(agent, pump_x: float, pump_y: float) -> Dict[str, float]:
    """Read the pump's pipe connection target_position after placement."""
    body = (
        f"local s = game.surfaces['nauvis']; "
        f"local p = s.find_entities_filtered{{position={{{pump_x},{pump_y}}}, "
        "radius=0.6, name='offshore-pump'}[1]; "
        "if not p then rcon.print('MISS'); return end; "
        "local conn = p.fluidbox.get_pipe_connections(1)[1]; "
        "rcon.print(string.format('%.1f,%.1f,%.1f,%.1f', "
        "  conn.position.x, conn.position.y, conn.target_position.x, conn.target_position.y))"
    )
    out = agent.rcon.command('/silent-command ' + body).strip()
    if out == 'MISS':
        return {}
    cx, cy, tx, ty = (float(p) for p in out.split(','))
    return {'conn_x': cx, 'conn_y': cy, 'target_x': tx, 'target_y': ty}


def _can_place(agent, name: str, x: float, y: float, direction: int = 0) -> bool:
    body = (
        f"local s = game.surfaces['nauvis']; "
        f"rcon.print(tostring(s.can_place_entity{{name='{name}', "
        f"position={{{x},{y}}}, force='player', direction={direction}}}))"
    )
    return agent.rcon.command('/silent-command ' + body).strip() == 'true'


def build_power_chain(agent, water_hint_x: float, water_hint_y: float,
                      max_search_radius: int = 30) -> Dict[str, Any]:
    """End-to-end power chain build. Returns {ok, ...details}.

    Steps:
    1. Find a pump-friendly water tile near the hint
    2. Place pump, query its connection target
    3. Place pipe at target (or extend pipes if target is on water)
    4. Place boiler so a water-input port lines up with a pipe
    5. Place engine east of boiler (steam-out → steam-in)
    6. Place pole within 7 tiles of engine
    7. Fuel boiler, wait, verify production
    """
    # Stage 1: find good water tile (already places + queries pump). On success,
    # the pump is LIVE at (wx, wy) and connection target is known.
    agent.movement.walk_chunked(water_hint_x, water_hint_y, chunk_size=30, radius_final=3)
    spot = _find_pump_friendly_water(agent, water_hint_x, water_hint_y, max_search_radius)
    if not spot:
        return {'ok': False, 'stage': 'find_water',
                'reason': 'no water tile produced a land-placeable output target'}
    wx, wy = spot['water_x'], spot['water_y']
    tx, ty = spot['target_x'], spot['target_y']

    # Stage 3: place pipe at target — we've already verified it's placeable
    pipe = agent.placement.place('pipe', tx, ty, 0, clear_blockers=True, step_aside=False)

    # Stage 4: place boiler. We want its WEST water-input (one of N/S of west tile)
    # to coincide with our pipe or with another pipe we'll add. For east-flow boiler:
    #   bx, by = boiler center
    #   water input N: target at (bx-0.5, by-1.5)
    #   water input S: target at (bx-0.5, by+1.5)
    # Pick boiler center such that water_input_S target = (tx, ty), so
    # bx = tx + 0.5, by = ty - 1.5. Boiler 3x2 dir=4 snaps to (x, y+0.5) — bx integer, by integer.
    bx, by = tx + 0.5, ty - 1.5
    # Snap: boiler dir=4 is 3 wide × 2 tall → x snaps to integer, y snaps to *.5
    bx = round(bx)
    by = round(by - 0.5) + 0.5
    if not _can_place(agent, 'boiler', bx, by, DIR_EAST):
        return {'ok': False, 'stage': 'place_boiler',
                'reason': f"can't place boiler at ({bx},{by})"}
    boiler = agent.placement.place('boiler', bx, by, DIR_EAST,
                                   clear_blockers=True, step_aside=False)

    # Stage 5: place steam-engine east of boiler. Boiler steam-out target = (bx+2.5, by+0.5)
    # Engine 2x3 dir=4 → 3 wide × 2 tall. Engine center at (bx+3.5, by+0.5) places its west
    # tile at (bx+2.5, by+0.5) — perfect.
    ex, ey = bx + 3.5, by + 0.5
    # snap: 2x3 dir=4 -> 3w x 2t. x snaps to *.5, y snaps to integer. Hmm by+0.5 = ey wants .5 → fine for x but y needs integer? Actually steam-engine in 2.0 might snap to (x.5, y.5). Just round to nearest .5.
    ex = round(ex - 0.5) + 0.5
    ey = round(ey - 0.5) + 0.5
    if not _can_place(agent, 'steam-engine', ex, ey, DIR_EAST):
        return {'ok': False, 'stage': 'place_engine',
                'reason': f"can't place engine at ({ex},{ey})"}
    engine = agent.placement.place('steam-engine', ex, ey, DIR_EAST,
                                   clear_blockers=True, step_aside=False)

    # Stage 6: place a small-electric-pole within 7 tiles of engine center
    px, py = snap_1x1_center(ex + 2, ey + 2)
    if not _can_place(agent, 'small-electric-pole', px, py):
        # Try a few nearby spots
        for dx, dy in [(0, 2), (2, 0), (-2, 0), (0, -2), (3, 0), (0, 3)]:
            candidate = snap_1x1_center(ex + dx, ey + dy)
            if _can_place(agent, 'small-electric-pole', candidate[0], candidate[1]):
                px, py = candidate
                break
    pole = agent.placement.place('small-electric-pole', px, py)

    # Stage 7: fuel boiler
    inv = agent.inventory.list()
    fuel_item = 'coal' if inv.get('coal', 0) >= 1 else 'wood'
    agent.fuel.fuel('boiler', bx, by, fuel_item=fuel_item, want_amount=20)

    # Verify
    time.sleep(15)
    body = (
        f"local s = game.surfaces['nauvis']; "
        f"local e = s.find_entities_filtered{{position={{{ex},{ey}}}, "
        f"radius=2, name='steam-engine'}}[1]; "
        f"local b = s.find_entities_filtered{{position={{{bx},{by}}}, "
        f"radius=2, name='boiler'}}[1]; "
        "rcon.print(string.format('engine_status=%d engine_W=%d boiler_status=%d', "
        "  e and e.status or -1, e and e.energy_generated_last_tick or 0, b and b.status or -1))"
    )
    status_out = agent.rcon.command('/silent-command ' + body).strip()
    return {
        'ok': True,
        'pump': (wx, wy),
        'pipe': (tx, ty),
        'boiler': (bx, by),
        'engine': (ex, ey),
        'pole': (px, py),
        'fuel_used': fuel_item,
        'status': status_out,
    }
