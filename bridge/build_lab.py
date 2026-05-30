"""
First Phase 2 action: place a lab near the nearest iron-ore patch.

Steps inside the Lua:
1. Find every iron-ore entity within 500 tiles of the first connected player.
2. Compute the centroid of those tiles (rough "middle of the patch").
3. Scan outward from the centroid in expanding rings, looking for a 3x3 spot
   the game considers placeable (no overlap with ore, water, trees, etc.).
4. Place a 'lab' entity on the player force at the first such spot.
5. Report what happened.

Run:
    set FACTORIO_RCON_PASSWORD=<password>
    python bridge/build_lab.py
"""

import sys

from rcon_client import RconClient

LUA = r"""
local s = game.surfaces[1]
local jj = game.connected_players[1]
if not jj then rcon.print('no player connected'); return end

local ents = s.find_entities_filtered{
  name = 'iron-ore',
  position = jj.position,
  radius = 500
}
if #ents == 0 then
  rcon.print('no iron ore within 500 tiles of player at ' .. jj.position.x .. ',' .. jj.position.y)
  return
end

local sumx, sumy = 0, 0
for _, e in pairs(ents) do
  sumx = sumx + e.position.x
  sumy = sumy + e.position.y
end
local cx, cy = sumx / #ents, sumy / #ents

local placed = nil
for r = 1, 40 do
  for dx = -r, r do
    for dy = -r, r do
      if math.abs(dx) == r or math.abs(dy) == r then
        local x, y = cx + dx, cy + dy
        if s.can_place_entity{name='lab', position={x,y}, force='player'} then
          local e = s.create_entity{name='lab', position={x,y}, force='player'}
          if e then
            placed = {x = x, y = y}
            goto done
          end
        end
      end
    end
  end
end
::done::

if placed then
  rcon.print(string.format(
    'placed lab at (%.1f, %.1f) | iron centroid (%.1f, %.1f) | %d ore tiles found | player at (%.1f, %.1f)',
    placed.x, placed.y, cx, cy, #ents, jj.position.x, jj.position.y
  ))
else
  rcon.print(string.format(
    'no placeable 3x3 spot within 40 tiles of centroid (%.1f, %.1f)', cx, cy
  ))
end
"""


def main() -> int:
    with RconClient() as r:
        out = r.command("/silent-command " + LUA)
    print(out.strip() or "(no output)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
