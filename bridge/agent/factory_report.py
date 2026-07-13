#!/usr/bin/env python
"""
factory_report.py — generate a FACTORY REPORT from JJ's live game (read-only RCON).

Project BRAIN's employees build the factory; when they've made real progress (or JJ asks),
run this to get a snapshot the manager relays to JJ. Works across ALL surfaces (K2SE = many
planets), and reads whatever entities/recipes the modpack actually has (no vanilla names).

Run:  python bridge/agent/factory_report.py
"""

from __future__ import annotations

import json
import os
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
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
local out={research={}, surfaces={}, team={}}
local f=game.forces.player
local cur=f.current_research
out.research.current = cur and cur.name or 'none'
out.research.progress = cur and math.floor((f.research_progress or 0)*100) or 0
local done=0; for _,t in pairs(f.technologies) do if t.researched then done=done+1 end end
out.research.completed = done
-- who's on the team right now (named chars)
local ok,chars = pcall(function() return remote.call('claude','list_chars') end)
if ok and chars then for name,u in pairs(chars) do local c=game.get_entity_by_unit_number(u); out.team[#out.team+1]=name..(c and c.valid and (' @'..c.surface.name) or ' (dead)') end end
-- per-surface factory summary
for _,s in pairs(game.surfaces) do
  local ents=s.find_entities_filtered{force='player'}
  local n=0; for _,e in ipairs(ents) do if e.type~='character' then n=n+1 end end
  if n>0 then
    local bytype={}; local idle=0; local idle_examples={}
    for _,e in ipairs(ents) do
      if e.type~='character' then
        bytype[e.type]=(bytype[e.type] or 0)+1
        local prod = (e.type=='assembling-machine' or e.type=='furnace' or e.type=='lab' or e.type=='mining-drill')
        if prod and e.status and e.status~=1 then idle=idle+1; if #idle_examples<6 then idle_examples[#idle_examples+1]=e.name..':st'..e.status end end
      end
    end
    local tl={}; for k,v in pairs(bytype) do tl[#tl+1]={k,v} end
    table.sort(tl,function(a,b) return a[2]>b[2] end)
    local top={}; for i=1,math.min(#tl,14) do top[#top+1]=tl[i][1]..'='..tl[i][2] end
    out.surfaces[s.name]={total=n, top=top, idle_machines=idle, idle_examples=idle_examples}
  end
end
rcon.print(helpers.table_to_json(out))
"""


def generate() -> str:
    os.environ["FACTORIO_RCON_PASSWORD"] = _pw()
    with RconClient() as r:
        r.command("/silent-command rcon.print('warmup')")  # first-command quirk
        raw = r.command("/silent-command " + LUA).strip()
    try:
        d = json.loads(raw)
    except Exception:  # noqa: BLE001
        return "FACTORY REPORT: query failed -> " + raw[:300]
    lines = ["===== FACTORY REPORT ====="]
    rr = d.get("research", {})
    lines.append(f"Research: {rr.get('current')} ({rr.get('progress')}%) | {rr.get('completed')} techs completed")
    team = d.get("team", [])
    if team:
        lines.append("Team: " + ", ".join(team))
    for sname, s in (d.get("surfaces") or {}).items():
        lines.append(f"\n[{sname}] {s.get('total')} structures | machines idle/blocked: {s.get('idle_machines')}")
        lines.append("  " + ", ".join(s.get("top", [])))
        if s.get("idle_examples"):
            lines.append("  idle e.g.: " + ", ".join(s["idle_examples"]))
    return "\n".join(lines)


def main() -> int:
    report = generate()
    print(report)
    try:
        (Path(__file__).resolve().parent / "factory_report.txt").write_text(report, encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
