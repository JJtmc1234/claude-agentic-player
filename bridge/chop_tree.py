"""
The Embodiment of Claude (character #454) finds the nearest tree, walks to
it via the mod's pathfinder, then mines it via the mod's on_tick mining
action loop. No teleport.

Flow:
  1. Find nearest tree on the character's surface (raw Lua query).
  2. Call mod's walk_to(unit, tree_x, tree_y, radius=mining_reach).
  3. Poll get_walk_status until status is 'completed' or 'error' or 'idle'.
  4. Call mod's start_mining(unit, tree_x, tree_y).
  5. Poll get_mining_status until mining=false.
  6. Compare inventory wood count before/after.

If the path can't be found (e.g. trapped by chests with no exit), walk_to
returns an error and we abort without mining.

Run:
    python bridge/chop_tree.py
"""

import json
import sys
import time

from _claude import NAME, UNIT
from rcon_client import RconClient

SEARCH_RADIUS = 300
MINING_REACH_RADIUS = 2.0    # walk to within this; mod's MINING_REACH is 2.7 (buffer for collision box edge cases)
WALK_POLL_INTERVAL = 0.5
WALK_TIMEOUT_S = 60
MINE_POLL_INTERVAL = 0.25
MINE_TIMEOUT_S = 10


FIND_TREE_LUA = f"""
local c = game.get_entity_by_unit_number({UNIT})
if not c or not c.valid then
  rcon.print(helpers.table_to_json({{error='no character'}})); return
end
local trees = c.surface.find_entities_filtered{{
  type='tree', position=c.position, radius={SEARCH_RADIUS}
}}
if #trees == 0 then
  rcon.print(helpers.table_to_json({{error='no tree within {SEARCH_RADIUS} tiles'}})); return
end
local best, bd = nil, math.huge
for _, t in pairs(trees) do
  local dx, dy = t.position.x - c.position.x, t.position.y - c.position.y
  local d = dx*dx + dy*dy
  if d < bd then bd = d; best = t end
end
rcon.print(helpers.table_to_json({{
  ok = true, tree = best.name,
  target_x = best.position.x, target_y = best.position.y,
  distance = math.sqrt(bd),
}}))
"""

WOOD_COUNT_LUA = f"""
local c = game.get_entity_by_unit_number({UNIT})
local inv = c and c.valid and c.get_main_inventory()
local w = 0
if inv then
  for _, s in ipairs(inv.get_contents()) do
    if s.name == 'wood' then w = s.count end
  end
end
rcon.print(w)
"""


def _call_mod(r: RconClient, fn: str, *args) -> dict:
    """Helper: call remote.call('claude', fn, args...) and return the parsed JSON."""
    arg_str = ",".join(str(a) for a in args)
    cmd = (
        f"/silent-command rcon.print(helpers.table_to_json("
        f"remote.call('claude','{fn}'"
        f"{',' + arg_str if arg_str else ''}"
        f")))"
    )
    out = r.command(cmd).strip()
    if not out or out.startswith("Cannot execute"):
        raise RuntimeError(f"mod call {fn} failed: {out}")
    return json.loads(out)


def main() -> int:
    with RconClient() as r:
        # 1) Find the nearest tree.
        out = r.command("/silent-command " + FIND_TREE_LUA).strip()
        data = json.loads(out)
        if data.get("error"):
            print(f"[chop] {data['error']}", file=sys.stderr)
            return 1
        tx, ty, tree, dist = data["target_x"], data["target_y"], data["tree"], data["distance"]
        print(f"[chop] {NAME} found {tree} at ({tx:.1f}, {ty:.1f}); {dist:.1f} tiles away")

        # 2) Ask the mod to walk there.
        walk_res = _call_mod(r, "walk_to", UNIT, tx, ty, MINING_REACH_RADIUS)
        if not walk_res.get("ok"):
            print(f"[chop] walk_to failed: {walk_res.get('error')}", file=sys.stderr)
            return 2
        if walk_res.get("status") == "already_at_goal":
            print("[chop] already in mining range, no walk needed")
        else:
            print(f"[chop] pathfinding ...")
            deadline = time.monotonic() + WALK_TIMEOUT_S
            last_status = None
            while time.monotonic() < deadline:
                time.sleep(WALK_POLL_INTERVAL)
                status = _call_mod(r, "get_walk_status", UNIT)
                s = status.get("status")
                if s != last_status:
                    print(f"[chop] walk status: {s}"
                          f"{' (' + str(status.get('current_index')) + '/' + str(status.get('total_waypoints')) + ' waypoints)' if s == 'walking' else ''}"
                          f"{' (' + status.get('error', '') + ')' if status.get('error') else ''}")
                    last_status = s
                if s in ("completed", "error", "idle"):
                    if s == "error":
                        print(f"[chop] walk failed: {status.get('error')}", file=sys.stderr)
                        return 3
                    break
            else:
                print(f"[chop] walk timed out after {WALK_TIMEOUT_S}s", file=sys.stderr)
                _call_mod(r, "cancel_walk", UNIT)
                return 4

        # 3) Mine the tree.
        wood_before = int(r.command("/silent-command " + WOOD_COUNT_LUA).strip())
        mine_res = _call_mod(r, "start_mining", UNIT, tx, ty)
        if not mine_res.get("ok"):
            print(f"[chop] start_mining failed: {mine_res.get('error')}", file=sys.stderr)
            return 5
        print(f"[chop] mining {mine_res['target']}, eta {mine_res['eta_ticks']} ticks "
              f"(~{mine_res['eta_ticks']/60:.2f}s)")

        deadline = time.monotonic() + MINE_TIMEOUT_S
        while time.monotonic() < deadline:
            time.sleep(MINE_POLL_INTERVAL)
            ms = _call_mod(r, "get_mining_status", UNIT)
            if not ms.get("mining"):
                break
        else:
            print(f"[chop] mining timed out after {MINE_TIMEOUT_S}s", file=sys.stderr)
            _call_mod(r, "stop_mining", UNIT)
            return 6

        wood_after = int(r.command("/silent-command " + WOOD_COUNT_LUA).strip())
        gained = wood_after - wood_before
        print(f"[chop] {NAME} now has {wood_after} wood (gained {gained:+d})")
        return 0 if gained > 0 else 7


if __name__ == "__main__":
    sys.exit(main())
