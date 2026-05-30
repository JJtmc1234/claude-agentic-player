"""
Spawn a 'character' entity on the player force at a given position.

The character has no driver — it's just a body in the world. Later we'll
hook up movement (walking_state) and inventory transfer; for now this is
the seed for "Claude has a presence on the map."

Run:
    python bridge/char_spawn.py             # spawn near (0,0)
    python bridge/char_spawn.py 50 -20      # spawn near (50,-20)
"""

import sys

from rcon_client import RconClient

LUA_TPL = r"""
local s = game.surfaces[1]
local cx, cy = %f, %f
local target = nil
for r = 0, 20 do
  for dx = -r, r do
    for dy = -r, r do
      if r == 0 or math.abs(dx) == r or math.abs(dy) == r then
        local x, y = cx + dx, cy + dy
        if s.can_place_entity{name='character', position={x,y}, force='player'} then
          target = {x = x, y = y}
          goto done
        end
      end
    end
  end
end
::done::
if not target then
  rcon.print('no placeable spot for character near (' .. cx .. ',' .. cy .. ')')
  return
end
local c = s.create_entity{name='character', position=target, force='player'}
if c then
  rcon.print(string.format('character placed at (%%.1f, %%.1f), health=%%d, unit_number=%%d',
    c.position.x, c.position.y, c.health, c.unit_number))
else
  rcon.print('create_entity returned nil')
end
"""


def main() -> int:
    if len(sys.argv) >= 3:
        cx, cy = float(sys.argv[1]), float(sys.argv[2])
    else:
        cx, cy = 0.0, 0.0
    lua = LUA_TPL % (cx, cy)
    with RconClient() as r:
        out = r.command("/silent-command " + lua)
    print(out.strip() or "(no output)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
