"""
Scout charting expedition on JJ's hosted world -- self-healing.

Scout physically journeys NE to the big iron field (~113,-249) in ~35-tile hops
and reveals fog ONLY around its own real position each cycle (legit exploration,
no charting places it never visited). If scout dies (biters on the trek), the
loop respawns it at base, re-tags it, and restarts the journey.

Rich iron/copper patches it passes are announced in chat. Runs in background;
TaskStop to end.
"""

import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _exec import _ensure_password  # noqa: E402
from rcon_client import RconClient  # noqa: E402

_ensure_password()

BASE = (-25, -45)
WAYPOINTS = [
    (0, -80), (25, -115), (50, -150), (70, -185), (90, -215),
    (108, -238), (113, -249),          # arrive at the field
    (130, -256), (120, -270), (98, -262), (100, -240), (113, -249),  # circle it
]
CIRCLE_START = 7  # after the full trek, loop indices 7.. to keep circling


def cycle_lua(wx, wy):
    return (
        "local s=game.surfaces['nauvis']; "
        "local chars=remote.call('claude','list_chars'); local u=chars.scout; "
        "local c=u and game.get_entity_by_unit_number(u); "
        "if not (c and c.valid) then "
        "  local r=remote.call('claude','spawn_named_char','scout',{" + str(BASE[0]) + "," + str(BASE[1]) + "}); "
        "  u=r.unit_number; c=game.get_entity_by_unit_number(u); "
        "  if c then pcall(function() rendering.draw_text{text='scout',surface=c.surface,"
        "    target={entity=c,offset={0,-2.4}},color={r=1,g=0.45,b=0.45},scale=1.3,"
        "    alignment='center',vertical_alignment='bottom'} end) end "
        "end; "
        "if not (c and c.valid) then rcon.print('{\"dead\":true}') return end; "
        "local x,y=c.position.x,c.position.y; "
        "game.forces.player.chart(s,{{x-48,y-48},{x+48,y+48}}); "
        "local ws=remote.call('claude','get_walk_status',u); "
        "if ws.status~='walking' and ws.status~='pathfinding' then "
        "  remote.call('claude','walk_to',u," + str(wx) + "," + str(wy) + ") end; "
        "local pat={}; "
        "for _,res in ipairs({'iron-ore','copper-ore'}) do "
        "  local es=s.find_entities_filtered{name=res,position={x,y},radius=48}; "
        "  local tot=0; for _,e in ipairs(es) do tot=tot+e.amount end; "
        "  if tot>0 then pat[res]=tot end end; "
        "rcon.print(helpers.table_to_json({x=x,y=y,st=ws.status or '?',u=u,patches=pat}))"
    )


def say(r, msg):
    esc = msg.replace("\\", "\\\\").replace("'", "\\'")
    r.command("/silent-command game.print('" + esc + "',{color={r=0.6,g=1,b=0.7}})")


def main() -> int:
    idx = 0
    waited = 0
    last_u = None
    best = {}
    THRESH = 250000
    while True:
        try:
            with RconClient() as r:
                say(r, "[Scout] On foot NE toward the big iron field (~113,-249), revealing the map as I walk -- no shortcuts.")
                while True:
                    wx, wy = WAYPOINTS[idx]
                    out = r.command("/silent-command " + cycle_lua(wx, wy)).strip()
                    data = {}
                    if out.startswith("{"):
                        try:
                            data = json.loads(out)
                        except Exception:  # noqa: BLE001
                            data = {}
                    u = data.get("u")
                    if u is not None and u != last_u:
                        if last_u is not None:
                            say(r, "[Scout] Respawned after a wipe -- restarting the trek NE (careful, biters out there).")
                        last_u = u
                        idx = 0
                        waited = 0
                    for res in ("iron-ore", "copper-ore"):
                        tot = int(data.get("patches", {}).get(res, 0) or 0)
                        if tot >= THRESH and tot > best.get(res, 0):
                            best[res] = tot
                            say(r, f"[Scout] Rich {res} ~({int(data['x'])},{int(data['y'])}): {tot:,} ore -- charted as I passed.")
                    st = data.get("st", "")
                    busy = st in ("walking", "pathfinding")
                    waited += 1
                    if (not busy) or waited >= 18:
                        idx = idx + 1
                        if idx >= len(WAYPOINTS):
                            idx = CIRCLE_START
                        waited = 0
                    time.sleep(2)
        except KeyboardInterrupt:
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"[scout] rcon error: {e}; reconnecting in 2s", flush=True)
            time.sleep(2)


if __name__ == "__main__":
    sys.exit(main())
