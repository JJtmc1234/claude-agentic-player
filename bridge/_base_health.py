"""Read-only base health monitor.

Probes every production entity (drills, furnaces, boilers, steam-engines,
assemblers, labs) on nauvis around the base and prints:
  - a working-vs-stopped tally per entity type, and
  - the worst-starved machines (not working) with coords + decoded status.

READ-ONLY: only reads entity.status; never moves/builds/mutates anything.
Safe for anyone to run at any time.

Usage:
    python bridge/_base_health.py            # default box around the base
    python bridge/_base_health.py X1 Y1 X2 Y2   # custom scan box

The RCON password is taken from FACTORIO_RCON_PASSWORD, else read from
C:\\FactorioServer\\start-server.bat (same fallback as _exec.py).
"""
import os
import re
import sys
from pathlib import Path

from rcon_client import RconClient

# Default scan box: base cluster (~0,60) down through the ore fields.
DEFAULT_BOX = (-150, -50, 100, 250)


def _ensure_password() -> None:
    if os.environ.get("FACTORIO_RCON_PASSWORD"):
        return
    bat = Path(r"C:\FactorioServer\start-server.bat")
    if bat.exists():
        m = re.search(r'--rcon-password "([^"]+)"', bat.read_text())
        if m:
            os.environ["FACTORIO_RCON_PASSWORD"] = m.group(1)


LUA_TEMPLATE = r"""
local s = game.surfaces.nauvis
local area = AREABOX
-- reverse map of entity_status codes -> names
local sname = {}
for k,v in pairs(defines.entity_status) do sname[v] = k end
local types = {'mining-drill','furnace','boiler','generator','assembling-machine','lab'}
local out = {}
local worst = {}
for _,t in ipairs(types) do
  local ents = s.find_entities_filtered{type=t, area=area}
  local working, stopped = 0, 0
  local bycode = {}
  for _,e in ipairs(ents) do
    local st = e.status
    -- 'working' + 'normal'/full-but-fine are ok; anything else = stopped
    if st == defines.entity_status.working
       or st == defines.entity_status.normal then
      working = working + 1
    else
      stopped = stopped + 1
      local nm = sname[st] or ('code'..tostring(st))
      bycode[nm] = (bycode[nm] or 0) + 1
      worst[#worst+1] = string.format('    %s %s at (%.0f,%.0f) -> %s',
        t, e.name, e.position.x, e.position.y, nm)
    end
  end
  local detail = ''
  for nm,c in pairs(bycode) do detail = detail..' '..nm..'='..c end
  out[#out+1] = string.format('%-18s total=%-3d working=%-3d stopped=%-3d%s',
    t, #ents, working, stopped, detail)
end
rcon.print('== BASE HEALTH (box '..area[1][1]..','..area[1][2]..' .. '..area[2][1]..','..area[2][2]..') ==')
rcon.print(table.concat(out, '\n'))
if #worst > 0 then
  rcon.print('== STOPPED MACHINES (fix these) ==')
  -- cap the list so a big broken base doesn't flood output
  local cap = math.min(#worst, 40)
  for i=1,cap do rcon.print(worst[i]) end
  if #worst > cap then rcon.print('    ... +'..(#worst-cap)..' more') end
else
  rcon.print('All scanned machines are working. Nothing starved.')
end
"""


def main() -> int:
    _ensure_password()
    if len(sys.argv) == 5:
        box = tuple(int(a) for a in sys.argv[1:5])
    else:
        box = DEFAULT_BOX
    areabox = "{{%d,%d},{%d,%d}}" % box
    lua = LUA_TEMPLATE.replace("AREABOX", areabox)
    with RconClient() as r:
        out = r.command("/silent-command " + lua)
    print(out, end="" if out.endswith("\n") else "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
