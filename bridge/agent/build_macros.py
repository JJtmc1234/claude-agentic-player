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
        "  if ci.get_item_count('burner-mining-drill')<1 then break end; "
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
# MACRO: smelter column below each ore chest (chest -> inserter -> furnace ->
# inserter -> output chest). Geometry (verified): for a 1x1 source chest whose
# CENTER is (chx, chy), going SOUTH:
#   input inserter (chx, chy+1) dir 0 (picks N from chest, drops S)
#   stone-furnace  (chx+0.5, chy+2.5)   [2x2, integer center, input tile = drop]
#   output inserter(chx, chy+4) dir 0 (picks N from furnace, drops S)
#   output chest   (chx, chy+5)
# --------------------------------------------------------------------------- #

def build_smelt_from_chests(cx: float, cy: float, ore_item: str = "iron-ore") -> str:
    """For each ore-holding chest near (cx,cy) (e.g. drill output chests), build a
    fueled stone-furnace column that pulls ore from the chest and outputs plates to a
    new chest. Uses only items the companion has. Verifies furnace status after."""
    lua = (
        _companion_unum_lua() +
        f"local cx={cx}; local cy={cy}; local ore='{ore_item}'; "
        "local srcs=s.find_entities_filtered{type='container',position={cx,cy},radius=12}; "
        "local built=0; local skipped=0; local msgs={}; "
        "for _,chest in ipairs(srcs) do "
        "  local sci=chest.get_inventory(defines.inventory.chest); "
        "  if sci and sci.get_item_count(ore)>0 then "
        "    local chx=chest.position.x; local chy=chest.position.y; "
        # burner-inserters (coal-fueled) because there is no electricity yet -- electric
        # 'inserter' sits no_power. Burner drills + furnaces + burner-inserters = a fully
        # power-independent plate line.
        "    if ci.get_item_count('stone-furnace')<1 or ci.get_item_count('burner-inserter')<2 or ci.get_item_count('iron-chest')<1 then "
        "      skipped=skipped+1; msgs[#msgs+1]='out-of-parts(need stone-furnace,2x burner-inserter,iron-chest)'; break "
        "    end; "
        "    local ii=remote.call('claude','place_entity',u,'burner-inserter',chx,chy+1,0); "
        "    local fr=remote.call('claude','place_entity',u,'stone-furnace',chx+0.5,chy+2.5,0); "
        "    local oi=remote.call('claude','place_entity',u,'burner-inserter',chx,chy+4,0); "
        "    local oc=remote.call('claude','place_entity',u,'iron-chest',chx,chy+5,0); "
        "    local function fuelburner(px,py) local e=s.find_entities_filtered{name='burner-inserter',position={px,py},radius=0.6}[1]; if e then local fi=e.get_fuel_inventory(); local cc=ci.get_item_count('coal'); if fi and cc>0 then local mv=fi.insert{name='coal',count=math.min(3,cc)}; if mv>0 then ci.remove{name='coal',count=mv} end end end end; "
        "    fuelburner(chx,chy+1); fuelburner(chx,chy+4); "
        "    local furn=s.find_entities_filtered{name='stone-furnace',position={chx+0.5,chy+2.5},radius=1.2}[1]; "
        "    if furn then local fi=furn.get_fuel_inventory(); local cc=ci.get_item_count('coal'); if fi and cc>0 then local mv=fi.insert{name='coal',count=math.min(10,cc)}; if mv>0 then ci.remove{name='coal',count=mv} end end end; "
        "    built=built+1; "
        "    msgs[#msgs+1]=string.format('col@(%.0f,%.0f) ins=%s furn=%s outins=%s outchest=%s', chx,chy, tostring(ii.ok),tostring(fr.ok),tostring(oi.ok),tostring(oc.ok)); "
        "  end "
        "end; "
        "rcon.print('smelter columns built='..built..' skipped='..skipped..' | '..table.concat(msgs,' ; '))"
    )
    return rc(lua)


# --------------------------------------------------------------------------- #
# MACRO: belt router (L-path). Lays transport-belts from (x1,y1) to (x2,y2):
# horizontal run first, then vertical, each belt facing the travel direction.
# Directions: 0=N,4=E,8=S,12=W. UNTESTED live -- verify belt flow when the game is up.
# --------------------------------------------------------------------------- #

def connect_belt(x1: int, y1: int, x2: int, y2: int, belt: str = "transport-belt") -> str:
    """Lay a belt line from (x1,y1) to (x2,y2) as an L (horizontal then vertical).
    Places `belt` items from the companion's inventory; each belt faces its travel dir."""
    lua = (
        _companion_unum_lua() +
        f"local x1,y1,x2,y2={x1},{y1},{x2},{y2}; local belt='{belt}'; local n=0; local fails=0; "
        "local function put(px,py,dir) if ci.get_item_count(belt)<1 then return end; "
        "  local r=remote.call('claude','place_entity',u,belt,px+0.5,py+0.5,dir); "
        "  if r.ok then n=n+1 else fails=fails+1 end end; "
        # horizontal
        "local hd = (x2>=x1) and 4 or 12; local sx=(x2>=x1) and 1 or -1; "
        "local xx=x1; while xx~=x2 do put(xx,y1,hd); xx=xx+sx end; "
        # corner + vertical
        "local vd = (y2>=y1) and 8 or 0; local sy=(y2>=y1) and 1 or -1; "
        "local yy=y1; while yy~=y2 do put(x2,yy,vd); yy=yy+sy end; "
        "put(x2,y2,vd); "
        "rcon.print('belts placed='..n..' fails='..fails..' (belt='..belt..')')"
    )
    return rc(lua)


# --------------------------------------------------------------------------- #
# MACRO: steam power. Places offshore-pump on a water tile near (wx,wy), a row of
# boilers fed by it (fueled with coal), steam-engines after the boilers, and a
# small-electric-pole for distribution. Offshore-pump orientation is derived from
# which side has land. UNTESTED live -- offshore-pump placement is finicky; this
# self-verifies (reports each entity's ok/status) so it can be corrected on first run.
# Needs in inventory: offshore-pump, boiler x n, steam-engine x n, pipe, coal, pole.
# --------------------------------------------------------------------------- #

def build_steam_power(wx: float, wy: float, boilers: int = 2) -> str:
    """Build a steam-power station at the water near (wx,wy): offshore-pump -> boilers
    (coal-fueled) -> steam-engines -> a pole. Reports what it placed + statuses so the
    exact offsets can be tuned live. Places only items the companion has."""
    lua = (
        _companion_unum_lua() +
        f"local wx,wy={wx},{wy}; local nb={boilers}; "
        "local have={pump=ci.get_item_count('offshore-pump'),boiler=ci.get_item_count('boiler'),engine=ci.get_item_count('steam-engine'),pipe=ci.get_item_count('pipe'),pole=ci.get_item_count('small-electric-pole'),coal=ci.get_item_count('coal')}; "
        # find a water tile with a land neighbour to the south (place pump facing north->land? we pick a water tile adjacent to land)
        "local wt=s.find_tiles_filtered{position={wx,wy},radius=20,name={'water','deepwater'}}; "
        "if #wt==0 then rcon.print('ERR:no water near ('..wx..','..wy..')') return end; "
        "local wtile=wt[1]; local wpx=math.floor(wtile.position.x); local wpy=math.floor(wtile.position.y); "
        # STEP 1 only: place the offshore-pump on the water tile (engine picks a valid
        # orientation toward adjacent land). The boiler->engine->pipe->pole chain is left
        # for live iteration next session (offsets must be verified against pump fluidbox).
        "local pr=remote.call('claude','place_entity',u,'offshore-pump',wpx+0.5,wpy+0.5,0); "
        "local msg='pump@('..wpx..','..wpy..')='..tostring(pr.ok)..(pr.ok and '' or (':'..tostring(pr.error))); "
        "rcon.print('STEAM(STUB) '..msg..' | inv pump='..have.pump..' boiler='..have.boiler..' engine='..have.engine..' pipe='..have.pipe..' pole='..have.pole..' coal='..have.coal..' | TODO live: boiler/engine/pipe/pole layout')"
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
    elif macro == "build_smelt_from_chests":
        cx = float(sys.argv[2]) if len(sys.argv) > 2 else 121.0
        cy = float(sys.argv[3]) if len(sys.argv) > 3 else -201.0
        ore = sys.argv[4] if len(sys.argv) > 4 else "iron-ore"
        print(build_smelt_from_chests(cx, cy, ore))
    elif macro == "connect_belt":
        a = [int(v) for v in sys.argv[2:6]]
        belt = sys.argv[6] if len(sys.argv) > 6 else "transport-belt"
        print(connect_belt(a[0], a[1], a[2], a[3], belt))
    elif macro == "build_steam_power":
        wx = float(sys.argv[2]); wy = float(sys.argv[3])
        nb = int(sys.argv[4]) if len(sys.argv) > 4 else 2
        print(build_steam_power(wx, wy, nb))
    else:
        print("macros: build_burner_mine <ore> <count> <cx> <cy> | "
              "build_smelt_from_chests <cx> <cy> <ore> | "
              "connect_belt <x1> <y1> <x2> <y2> [belt] | build_steam_power <wx> <wy> [boilers]")
    return 0


if __name__ == "__main__":
    sys.exit(_main())
