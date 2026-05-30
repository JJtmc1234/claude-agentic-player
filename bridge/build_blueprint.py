"""
Have The Embodiment of Claude walk to a cluster of ghosts and build them.

Strategy:
  1. Find all entity-ghosts on the player force, anywhere on TEoC's surface.
  2. Pick the cluster nearest to TEoC (using a simple "centroid of all ghosts
     within 500 tiles of nearest ghost" heuristic — good enough for one
     blueprint at a time).
  3. Walk TEoC to the centroid (radius 5: doesn't need to be exact).
  4. Call mod's build_ghosts_in_range(radius=10), which revives reachable
     ghosts and deducts items from TEoC's inventory.
  5. If ghosts remain (cluster larger than build radius), walk to a new
     centroid of the remaining ghosts and build again. Loop until done or
     missing items / errors stop progress.

Run:
    python bridge/build_blueprint.py
"""

import json
import sys
import time

from _claude import NAME, UNIT
from rcon_client import RconClient

WALK_POLL_INTERVAL = 0.5
WALK_TIMEOUT_S = 60
WALK_RADIUS = 5.0          # how close TEoC needs to be to "the cluster"
BUILD_RADIUS = 10          # mod-side: ghosts within this get built per call
MAX_ITERATIONS = 30  # 357-ghost blueprints can take ~10 build stops


FIND_GHOSTS_LUA = f"""
local c = game.get_entity_by_unit_number({UNIT})
if not c or not c.valid then
  rcon.print(helpers.table_to_json({{error='no character'}})); return
end
local ghosts = c.surface.find_entities_filtered{{
  type = 'entity-ghost', force = c.force,
}}
if #ghosts == 0 then
  rcon.print(helpers.table_to_json({{ok=true, count=0}})); return
end
-- Pick the ghost nearest to the character.
local nearest, nd = nil, math.huge
for _, g in pairs(ghosts) do
  local dx, dy = g.position.x - c.position.x, g.position.y - c.position.y
  local d = dx*dx + dy*dy
  if d < nd then nd = d; nearest = g end
end
-- Centroid of all ghosts within 500 tiles of the nearest one.
local cx, cy, n = 0, 0, 0
for _, g in pairs(ghosts) do
  local dx, dy = g.position.x - nearest.position.x, g.position.y - nearest.position.y
  if dx*dx + dy*dy <= 500*500 then
    cx = cx + g.position.x; cy = cy + g.position.y; n = n + 1
  end
end
rcon.print(helpers.table_to_json({{
  ok = true,
  count = #ghosts,
  cluster_count = n,
  centroid = {{ x = cx/n, y = cy/n }},
  nearest = {{ x = nearest.position.x, y = nearest.position.y }},
  char = {{ x = c.position.x, y = c.position.y }},
}}))
"""


def _call_mod(r: RconClient, fn: str, *args) -> dict:
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


def find_ghosts(r: RconClient) -> dict:
    out = r.command("/silent-command " + FIND_GHOSTS_LUA).strip()
    return json.loads(out)


def walk_to_and_wait(r: RconClient, x: float, y: float, radius: float) -> dict:
    res = _call_mod(r, "walk_to", UNIT, x, y, radius)
    if not res.get("ok"):
        return {"status": "error", "error": res.get("error")}
    if res.get("status") == "already_at_goal":
        return {"status": "completed"}
    deadline = time.monotonic() + WALK_TIMEOUT_S
    while time.monotonic() < deadline:
        time.sleep(WALK_POLL_INTERVAL)
        s = _call_mod(r, "get_walk_status", UNIT)
        st = s.get("status")
        if st in ("completed", "error", "idle"):
            return s
    _call_mod(r, "cancel_walk", UNIT)
    return {"status": "timeout"}


def main() -> int:
    with RconClient() as r:
        total_built = 0
        total_missing = []
        for iteration in range(1, MAX_ITERATIONS + 1):
            info = find_ghosts(r)
            if info.get("error"):
                print(f"[build] {info['error']}", file=sys.stderr)
                return 1
            ghosts_remaining = info.get("count", 0)
            if ghosts_remaining == 0:
                print(f"[build] no more ghosts on the surface. {total_built} built total.")
                return 0
            target_x, target_y = info["nearest"]["x"], info["nearest"]["y"]
            print(
                f"[build] iter {iteration}: "
                f"{ghosts_remaining} ghosts remain; nearest at "
                f"({target_x:.1f}, {target_y:.1f}); centroid was "
                f"({info['centroid']['x']:.1f}, {info['centroid']['y']:.1f})"
            )

            walk_res = walk_to_and_wait(r, target_x, target_y, WALK_RADIUS)
            # Don't abort on walk failure. Two reasons it can happen mid-build:
            # (1) entities we JUST built block the path the pathfinder is
            # planning around. (2) TEoC steps onto a newly-placed transport
            # belt and the belt pushes him off the goal tile.
            # Both are recoverable: build_ghosts_in_range works on whatever
            # ghosts are within 10 tiles of TEoC's actual position. If no
            # ghosts are in range, the build returns 0 and we abort below.
            if walk_res.get("status") == "completed":
                print(f"[build] walked to nearest ghost")
            else:
                final_d = walk_res.get("final_distance")
                print(
                    f"[build] walk ended short ({walk_res.get('status')}, "
                    f"final_distance={final_d if final_d is not None else '?'}); "
                    "attempting build from current position anyway"
                )

            build_res = _call_mod(r, "build_ghosts_in_range", UNIT, BUILD_RADIUS)
            if not build_res.get("ok"):
                print(f"[build] build_ghosts_in_range failed: {build_res.get('error')}", file=sys.stderr)
                return 3
            built = build_res.get("built") or []
            missing = build_res.get("missing") or []
            errors = build_res.get("errors") or []
            print(f"[build]   built {len(built)}, missing-items {len(missing)}, errors {len(errors)}")
            for b in built[:6]:
                print(f"           +1 {b['name']} at ({b['position']['x']:.0f}, {b['position']['y']:.0f})")
            if len(built) > 6:
                print(f"           ... and {len(built) - 6} more")
            total_built += len(built)
            for m in missing:
                total_missing.append(f"{m['needs']} (for {m['name']})")
            if errors:
                print(f"[build]   errors: {errors[:3]}")

            if len(built) == 0:
                print("[build] no progress this iteration — stopping.")
                if missing:
                    unique = sorted(set(total_missing))
                    print(f"[build] missing items: {', '.join(unique[:20])}")
                return 4

        print(f"[build] reached MAX_ITERATIONS={MAX_ITERATIONS}, stopping. Built {total_built}.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
