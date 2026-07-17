"""
dashboard.py — MISSION CONTROL for the companion co-op run.

A live, read-only terminal board so JJ can OVERSEE (not hand-play): what the companion is doing,
the base's health + bottlenecks, production at a glance, and a hint of where to step in. Pure RCON
reads (no LLM, no cost). Refreshes every few seconds.

    python bridge/agent/dashboard.py            # live board (Ctrl-C to stop)
    python bridge/agent/dashboard.py --once      # one snapshot

You act on it by chatting/pinging the companion IN-GAME (it reacts to your messages instantly).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE.parent))
import agent.compete as c  # reuse rcon password resolver
from rcon_client import RconClient

_STATE = _HERE / "state"
_TEAM = _HERE / "team_status"


def _companion_unum() -> str:
    f = _STATE / "companion.unum"
    try:
        return f.read_text(encoding="utf-8").strip()
    except Exception:  # noqa: BLE001
        return ""


_SNAP_LUA = """
local u=%s
local out={}
local c = u~=0 and game.get_entity_by_unit_number(u) or nil
if c and c.valid then
  local inv=c.get_main_inventory(); local items={}
  if inv then for _,it in pairs(inv.get_contents()) do if type(it)=='table' and it.count then items[it.name]=it.count end end end
  out.comp={x=math.floor(c.position.x),y=math.floor(c.position.y),health=math.floor(c.health or 0),items=items}
end
-- JJ
local jj=game.players['Factoriobrine'] or game.players['IdBaj98']
if jj and jj.character then out.jj={x=math.floor(jj.character.position.x),y=math.floor(jj.character.position.y)} end
-- base machines: counts + bottlenecks (unhealthy status) on the player force
local s=game.surfaces['nauvis']
local snames={}; for k,v in pairs(defines.entity_status) do snames[v]=k end
local good={working=true, normal=true}
local kinds={'assembling-machine','furnace','mining-drill','lab','boiler','generator'}
local counts={}; local bott={}
for _,ty in ipairs(kinds) do
  local es=s.find_entities_filtered{force='player',type=ty}
  local work=0
  for _,e in ipairs(es) do
    local nm=snames[e.status] or 'unknown'
    if nm=='working' or nm=='normal' then work=work+1
    elseif #bott<12 then bott[#bott+1]={name=e.name,x=math.floor(e.position.x),y=math.floor(e.position.y),status=nm} end
  end
  if #es>0 then counts[ty]={work=work, total=#es} end
end
out.counts=counts; out.bottlenecks=bott
-- research
local f=game.forces['player']
if f.current_research then out.research={name=f.current_research.name, pct=math.floor((f.research_progress or 0)*100)} end
rcon.print(helpers.table_to_json(out))
"""


def snapshot(rcon: RconClient, u: str) -> dict:
    try:
        out = rcon.command("/silent-command " + (_SNAP_LUA % (u if u.isdigit() else "0")),
                           drain_timeout=10).strip()
        return json.loads(out)
    except Exception:  # noqa: BLE001
        return {}


def companion_action() -> tuple:
    f = _TEAM / "companion.json"
    try:
        d = json.loads(f.read_text(encoding="utf-8"))
        return d.get("action", "?"), int(time.time() - d.get("t", 0))
    except Exception:  # noqa: BLE001
        return "?", -1


def render(snap: dict, action: str, age: int) -> str:
    L = []
    L.append("=" * 60)
    L.append("  MISSION CONTROL -- companion co-op (read-only)")
    L.append("=" * 60)
    comp = snap.get("comp")
    if comp:
        top = sorted(comp.get("items", {}).items(), key=lambda kv: -kv[1])[:6]
        inv = "  ".join(f"{n}:{q}" for n, q in top) or "(empty)"
        L.append(f"COMPANION  @({comp['x']},{comp['y']})  hp{comp['health']}  action:{action} ({age}s ago)")
        L.append(f"  carrying: {inv}")
    else:
        L.append("COMPANION  (no character — spawning / game loading?)")
    jj = snap.get("jj")
    L.append(f"YOU  @({jj['x']},{jj['y']})" if jj else "YOU  (no character)")
    rs = snap.get("research")
    L.append(f"RESEARCH  {rs['name']} {rs['pct']}%" if rs else "RESEARCH  (none queued)")
    L.append("-" * 60)
    counts = snap.get("counts", {})
    if counts:
        L.append("MACHINES (working/total):")
        for ty, cc in counts.items():
            flag = "  <-- some stalled" if cc["work"] < cc["total"] else ""
            L.append(f"  {ty:<20} {cc['work']}/{cc['total']}{flag}")
    else:
        L.append("MACHINES  (none built yet)")
    L.append("-" * 60)
    bott = snap.get("bottlenecks", [])
    if bott:
        L.append(f"BOTTLENECKS ({len(bott)}):")
        for b in bott[:12]:
            L.append(f"  {b['name']}:{b['status']} @({b['x']},{b['y']})")
        L.append("")
        L.append("  YOUR MOVE: if the companion isn't clearing these, ping/chat it in-game")
        L.append("  (e.g. \"drain the furnaces at " + f"{bott[0]['x']},{bott[0]['y']}" + "\").")
    else:
        L.append("BOTTLENECKS  none - base is flowing. Consider giving a next goal.")
    L.append("=" * 60)
    return "\n".join(L)


def main() -> int:
    ap = argparse.ArgumentParser(description="mission-control dashboard for the companion")
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--poll", type=float, default=4.0)
    args = ap.parse_args()
    os.environ.setdefault("FACTORIO_RCON_PASSWORD", c._resolve_rcon_password())
    is_tty = sys.stdout.isatty()
    try:
        with RconClient() as rcon:
            while True:
                u = _companion_unum()
                snap = snapshot(rcon, u)
                action, age = companion_action()
                board = render(snap, action, age)
                if is_tty:
                    os.system("cls" if os.name == "nt" else "clear")
                print(board, flush=True)
                if args.once:
                    break
                time.sleep(args.poll)
    except KeyboardInterrupt:
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
