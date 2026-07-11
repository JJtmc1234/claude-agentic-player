"""
Fast scripted executor for the 'companion' teammate character (JJ's 2.1+SA world).

The Claude sub-agent driver reasons at ~seconds per action, so the character
looked idle between turns. This is the FAST tier: a tight ~0.8s loop that keeps
companion continuously WORKING -- mining the nearest useful ore and building any
blueprint ghosts it can reach. Self-heals (respawns near JJ) if the char dies.

Resolves the companion unum via list_chars each cycle, so it survives respawns.
Run in background; TaskStop to end. A Claude strategist can sit on top of this.
"""

import os
import re
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from rcon_client import RconClient  # noqa: E402


def _pw() -> str:
    pw = os.environ.get("FACTORIO_RCON_PASSWORD")
    if pw:
        return pw
    bat = Path(r"C:\FactorioServer\start-server.bat")
    if bat.exists():
        m = re.search(r'--rcon-password "([^"]+)"', bat.read_text())
        if m:
            return m.group(1)
    raise RuntimeError("no FACTORIO_RCON_PASSWORD and start-server.bat unreadable")


LUA = r"""
local s=game.surfaces['nauvis']
local ch=remote.call('claude','list_chars')
local u=ch.companion
local c=u and game.get_entity_by_unit_number(u)
if not (c and c.valid) then
  local jj=game.players['Factoriobrine']
  local jp=(jj and ((jj.character and jj.character.position) or jj.position)) or {x=0,y=0}
  remote.call('claude','spawn_named_char','companion',{jp.x+3,jp.y})
  rcon.print('respawned companion')
  return
end
-- LEASH: stay near JJ. If we've drifted far, walk back toward him instead of
-- wandering across the map chasing ore.
local jj=game.players['Factoriobrine']
local jp=jj and ((jj.character and jj.character.position) or jj.position)
if jp then
  local dx=jp.x-c.position.x; local dy=jp.y-c.position.y
  if dx*dx+dy*dy > 45*45 then
    remote.call('claude','walk_to',u,jp.x-3,jp.y)
    rcon.print('returning to JJ')
    return
  end
end
-- build any blueprint ghosts within reach that we have items for
pcall(function() remote.call('claude','build_ghosts_in_range',u,10) end)
-- keep mining the nearest useful ore within the leash radius, non-stop
local ms=remote.call('claude','get_mining_status',u)
if not ms.mining then
  local best,bd=nil,1e18
  for _,rn in ipairs({'iron-ore','coal','copper-ore','stone'}) do
    for _,e in ipairs(s.find_entities_filtered{name=rn,position=c.position,radius=48}) do
      local dx=e.position.x-c.position.x; local dy=e.position.y-c.position.y
      local d=dx*dx+dy*dy
      if d<bd then bd=d; best=e end
    end
  end
  if best then
    local r=remote.call('claude','start_mining',u,best.position.x,best.position.y)
    if not (r and r.ok) then remote.call('claude','walk_to',u,best.position.x,best.position.y) end
  end
end
rcon.print('t'..game.tick)
"""

CMD = "/silent-command " + LUA


def main() -> int:
    os.environ["FACTORIO_RCON_PASSWORD"] = _pw()
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
            print(f"[companion] rcon error: {e}; reconnecting in 2s", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
