"""
Keep the 4 named team characters continuously hand-mining on JJ's hosted
Factorio (2.0 SE) world.

Each start_mining job yields exactly ONE ore then clears (control.lua
process_mining_jobs), so a char goes idle after every ore. This loop re-arms
any idle char: for each char, if it has no active mining job, find the nearest
resource of its assigned type and start_mining it (walk toward it if the
nearest tile is out of reach). Never overwrites an ACTIVE job (that would reset
ticks_left and the ore would never finish).

Roster (unums on the current world; update if chars die/respawn):
    186 miner  -> iron-ore     188 courier -> copper-ore
    187 builder-> coal         189 scout   -> stone

Run in background; Ctrl-C / TaskStop to end.
"""

import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _exec import _ensure_password  # noqa: E402
from rcon_client import RconClient  # noqa: E402

_ensure_password()

# One server-side pass: re-arm every idle roster char. Kept entirely in Lua so
# the Python side just re-sends it each tick.
LUA = r"""
local s=game.surfaces['nauvis']
local roster={[186]='iron-ore',[187]='coal',[188]='copper-ore',[189]='stone'}
for u,t in pairs(roster) do
  local c=game.get_entity_by_unit_number(u)
  if c and c.valid and c.type=='character' then
    local ms=remote.call('claude','get_mining_status',u)
    if not ms.mining then
      local near=s.find_entities_filtered{name=t,position=c.position,radius=40}
      local best,bd=nil,1e18
      for _,e in ipairs(near) do
        local dx=e.position.x-c.position.x; local dy=e.position.y-c.position.y
        local d=dx*dx+dy*dy
        if d<bd then bd=d; best=e end
      end
      if best then
        local r=remote.call('claude','start_mining',u,best.position.x,best.position.y)
        if not (r and r.ok) then
          remote.call('claude','walk_to',u,best.position.x,best.position.y)
        end
      end
    end
  end
end
rcon.print('tick '..game.tick)
"""

CMD = "/silent-command " + LUA


def main() -> int:
    period = 0.8
    while True:
        try:
            with RconClient() as r:
                while True:
                    r.command(CMD)
                    time.sleep(period)
        except KeyboardInterrupt:
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"[automine] rcon error: {e}; reconnecting in 2s", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
