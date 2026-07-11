"""
Project BRAIN — scripted build macros (deterministic base construction).

The reactive per-action executor (Haiku loop) cannot build coherent, WORKING layouts --
it places one entity at a time and loses track, producing non-functional spaghetti. This
module replaces that layer: each macro places a whole CORRECT, CONNECTED block in one call
(drills fueled + feeding chests/belts, furnaces fueled + fed, power wired, labs powered).

Design rules:
- CRAFT, DON'T SPAWN. Macros place items the companion actually HAS in inventory (crafted/
  mined). If materials are short, the macro reports exactly what's missing -- it never
  conjures items. A higher-level planner (Opus) is responsible for having the companion
  craft/stage the needed items first.
- GEOMETRY IS EXACT. All offsets use verified facts (see CLAUDE.md / context.txt):
    * burner-mining-drill is 2x2; facing SOUTH (dir 8) it drops at center+(0, 1.296875) --
      the FIRST tile row south of its south edge. We read drill.drop_position live and place
      the receiving chest exactly there rather than trusting a hardcoded offset.
    * inserter `direction` = the side it PICKS FROM (0=N,4=E,8=S,12=W); drop is opposite.
    * crafters (furnace/assembler) use inventory crafter_input(2)/crafter_output(3); read
      via get_output_inventory()/get_fuel_inventory() (this modpack has no furnace_source).
- IDEMPOTENT-ISH: every placement is checked; failures are collected and returned, not
  raised, so one bad tile doesn't abort the whole block.

Each macro returns a dict: {ok, placed:[...], missing:{item:count}, errors:[...], notes}.
Run standalone to test:  python bridge/agent/build_macros.py <macro> [args]
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))
from rcon_client import RconClient  # noqa: E402


# --------------------------------------------------------------------------- #
# connection + low-level helpers
# --------------------------------------------------------------------------- #

def _resolve_rcon_password() -> str:
    pw = os.environ.get("FACTORIO_RCON_PASSWORD")
    if pw:
        return pw
    bat = Path(r"C:\FactorioServer\start-server.bat")
    if bat.exists():
        m = re.search(r'--rcon-password "([^"]+)"', bat.read_text())
        if m:
            return m.group(1)
    raise RuntimeError("no FACTORIO_RCON_PASSWORD and start-server.bat unreadable")


_RCON: RconClient | None = None
CHAR_NAME = "companion"


def rc(lua: str) -> str:
    assert _RCON is not None
    return _RCON.command("/silent-command " + lua).strip()


def _companion_unum_lua() -> str:
    """Lua snippet that binds `u` = companion unit_number and `c` = its entity."""
    return (
        "local ch=remote.call('claude','list_chars'); local u=ch['" + CHAR_NAME + "']; "
        "local c=u and game.get_entity_by_unit_number(u); "
        "if not (c and c.valid) then rcon.print('ERR:no-companion') return end; "
        "local s=c.surface; local ci=c.get_main_inventory(); "
    )


# --------------------------------------------------------------------------- #
# MACRO: automated burner-mining line
# --------------------------------------------------------------------------- #

def build_burner_mine(ore_name: str, count: int, cx: float, cy: float) -> str:
    """Place `count` burner-mining-drills on the `ore_name` patch nearest (cx,cy), fuel each
    with the companion's coal, and set an iron-chest at each drill's real drop_position so it
    mines hands-free. Places only items the companion HAS; reports shortfalls. Returns a
    human-readable summary line.

    This is the reliable, geometry-correct replacement for the reactive place_miner spam:
    it finds a run of ore tiles, spaces the drills 2 apart (2x2 footprint), and verifies
    each drill+chest after placing. (cx,cy) is where to build -- e.g. an ore-square center.
    """
    lua = (
        _companion_unum_lua() +
        f"local ore='{ore_name}'; local want={count}; local cx={cx}; local cy={cy}; "
        "local have_d=ci.get_item_count('burner-mining-drill'); "
        "local have_ch=ci.get_item_count('iron-chest'); "
        "local coal=ci.get_item_count('coal'); "
        # find ore tiles near the target center
        "local tiles=s.find_entities_filtered{name=ore,position={cx,cy},radius=40}; "
        "if #tiles==0 then rcon.print('ERR:no '..ore..' within 40 of ('..cx..','..cy..')') return end; "
        # greedily pick non-overlapping 2x2 drill centers on ore, spaced 2 tiles
        "local used={}; local function key(x,y) return math.floor(x)..','..math.floor(y) end; "
        "local placed=0; local nofuel=0; local nochest=0; local fails=0; "
        "for _,e in ipairs(tiles) do "
        "  if placed>=want then break end; "
        "  local px=math.floor(e.position.x)+0.0; local py=math.floor(e.position.y)+0.0; "
        "  local k=key(px,py); "
        "  if not used[k] then "
        "    local r=remote.call('claude','place_entity',u,'burner-mining-drill',px,py,8); "
        "    if r.ok then "
        "      used[k]=true; used[key(px+1,py)]=true; used[key(px,py+1)]=true; used[key(px+1,py+1)]=true; "
        "      local drill=nil; for _,d in ipairs(s.find_entities_filtered{name='burner-mining-drill',position={px,py},radius=1.5}) do drill=d break end; "
        "      if drill then "
        "        placed=placed+1; "
        "        local fi=drill.get_fuel_inventory(); local ccount=ci.get_item_count('coal'); "
        "        if fi and ccount>0 then local mv=fi.insert{name='coal',count=math.min(5,ccount)}; if mv>0 then ci.remove{name='coal',count=mv} else nofuel=nofuel+1 end else nofuel=nofuel+1 end; "
        "        local dp=drill.drop_position; "
        "        if ci.get_item_count('iron-chest')>0 then local cr=remote.call('claude','place_entity',u,'iron-chest',dp.x,dp.y,0); if not cr.ok then nochest=nochest+1 end else nochest=nochest+1 end; "
        "      end "
        "    else fails=fails+1 end "
        "  end "
        "end; "
        "rcon.print(string.format('placed %d/%d drills on %s (had drills=%d chests=%d coal=%d) | unfueled=%d nochest=%d placefails=%d', placed, want, ore, have_d, have_ch, coal, nofuel, nochest, fails))"
    )
    return rc(lua)


# --------------------------------------------------------------------------- #
# standalone test harness
# --------------------------------------------------------------------------- #

def _main() -> int:
    global _RCON
    os.environ["FACTORIO_RCON_PASSWORD"] = _resolve_rcon_password()
    _RCON = RconClient()
    _RCON.connect()
    macro = sys.argv[1] if len(sys.argv) > 1 else "help"
    if macro == "build_burner_mine":
        ore = sys.argv[2] if len(sys.argv) > 2 else "iron-ore"
        n = int(sys.argv[3]) if len(sys.argv) > 3 else 3
        cx = float(sys.argv[4]) if len(sys.argv) > 4 else 130.0
        cy = float(sys.argv[5]) if len(sys.argv) > 5 else -164.0
        print(build_burner_mine(ore, n, cx, cy))
    else:
        print("macros: build_burner_mine <ore> <count> <cx> <cy>")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
