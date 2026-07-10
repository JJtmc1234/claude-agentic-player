"""
Claude-brain prototype: Claude drives ONE Factorio character (the builder) via a
perceive -> reason -> act loop, using our RCON/mod functions as its tools.

This is the "make the team smarter" prototype (see thoughts.txt). Instead of a
hardcoded script, each cycle we hand Claude the live game state and a tool set, and
Claude decides what to do. The Anthropic SDK Tool Runner drives the tool-call loop;
prompt caching keeps the big stable system prompt cheap (~0.1x on cache reads).

STATUS: written but UNTESTED — needs ANTHROPIC_API_KEY set and a live game hosting
the claude-companion mod. Run:  python bridge/agent/brain.py
Requires:  pip install anthropic

Design: single-agent driver (the builder). Once proven, generalize to a two-tier
planner (Opus) + per-char executors for the whole team.
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BRIDGE = _HERE.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from rcon_client import RconClient  # noqa: E402

# ---------------------------------------------------------------------------
# Config / connection
# ---------------------------------------------------------------------------

# Two-tier for smart AND fast: a low-latency model drives moment-to-moment
# actions on a tight loop; an occasional Opus planner sets strategy (stub below,
# wired up when we go live). JJ wanted it faster -> Haiku 4.5 for the executor.
FAST_MODEL = "claude-haiku-4-5"    # low-latency executor -- fast reactions
PLANNER_MODEL = "claude-opus-4-8"  # smart periodic strategy (see run_planner note)
CHAR_NAME = "companion"            # the brain's OWN teammate character (NOT JJ's)
OWNER_PLAYER = "Factoriobrine"     # JJ -- spawn the teammate next to him + help him
CYCLE_SECONDS = 1.5                # tight loop for a real-time co-op feel
PLAN_EVERY = 30                    # executor cycles between Opus planner re-strategizing (~45s)


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
_UNUM: int | None = None  # resolved builder unit number


def _rc(lua: str) -> str:
    """Run a /silent-command and return the stripped RCON output."""
    global _RCON
    assert _RCON is not None
    return _RCON.command("/silent-command " + lua).strip()


def _resolve_unum() -> int:
    out = _rc(
        "local ch=remote.call('claude','list_chars'); "
        f"rcon.print(tostring(ch['{CHAR_NAME}']))"
    )
    if not out.isdigit():
        # spawn the teammate right next to JJ so he can play alongside it
        out = _rc(
            f"local p=game.players['{OWNER_PLAYER}']; "
            "local pos=(p and ((p.character and p.character.position) or p.position)) or {x=0,y=0}; "
            f"local r=remote.call('claude','spawn_named_char','{CHAR_NAME}',{{pos.x+3,pos.y}}); "
            "rcon.print(tostring(r.unit_number))"
        )
    return int(out)


# ---------------------------------------------------------------------------
# PERCEIVE — compact live state the model reasons over each cycle
# ---------------------------------------------------------------------------

PERCEIVE_LUA = """
local u=%d
local c=game.get_entity_by_unit_number(u)
if not (c and c.valid) then rcon.print('{"alive":false}') return end
local s=c.surface
local inv=c.get_main_inventory()
local items={}
for _,e in pairs(inv.get_contents()) do
  if type(e)=='table' and e.name then items[e.name]=(items[e.name] or 0)+(e.count or 0) end
end
local ms=remote.call('claude','get_mining_status',u)
local ws=remote.call('claude','get_walk_status',u)
local cs=remote.call('claude','get_craft_status',u)
-- nearby ghosts (what to build) grouped by needed item
local need={}
for _,g in ipairs(s.find_entities_filtered{type='entity-ghost',position=c.position,radius=40,force=c.force}) do
  local it=g.ghost_prototype.items_to_place_this
  local n=(it and it[1] and it[1].name) or g.ghost_name
  need[n]=(need[n] or 0)+1
end
-- nearest resource of each type
local res={}
for _,rn in ipairs({'iron-ore','copper-ore','coal','stone'}) do
  local es=s.find_entities_filtered{name=rn,position=c.position,radius=60}
  local best,bd=nil,1e18
  for _,e in ipairs(es) do local dx=e.position.x-c.position.x;local dy=e.position.y-c.position.y;local d=dx*dx+dy*dy;if d<bd then bd=d;best=e end end
  if best then res[rn]={x=math.floor(best.position.x),y=math.floor(best.position.y),dist=math.floor(math.sqrt(bd))} end
end
-- nearest biter (threat)
local threat=nil
local en=s.find_nearest_enemy{position=c.position,max_distance=60,force=c.force}
if en and en.valid then threat={x=math.floor(en.position.x),y=math.floor(en.position.y),dist=math.floor(((en.position.x-c.position.x)^2+(en.position.y-c.position.y)^2)^0.5)} end
rcon.print(helpers.table_to_json({
  alive=true, x=math.floor(c.position.x), y=math.floor(c.position.y),
  health=math.floor(c.health or 0),
  inventory=items, mining=ms.mining or false, walking=(ws.status=='walking' or ws.status=='pathfinding'),
  crafting=(cs.status=='crafting'), ghosts_needed=need, nearest_resource=res, threat=threat,
}))
"""


def perceive() -> dict:
    out = _rc(PERCEIVE_LUA % _UNUM)
    try:
        return json.loads(out)
    except Exception:  # noqa: BLE001
        return {"alive": False, "raw": out}


# ---------------------------------------------------------------------------
# TOOLS — the actions Claude can take (thin wrappers over the mod's remote fns)
# ---------------------------------------------------------------------------

try:
    from anthropic import Anthropic, beta_tool
except Exception:  # noqa: BLE001
    Anthropic = None  # type: ignore
    def beta_tool(fn):  # type: ignore
        return fn


@beta_tool
def walk_to(x: int, y: int) -> str:
    """Walk the character to map coordinate (x, y). Returns immediately; walking
    continues in the background. Use look() next cycle to check arrival."""
    _rc(f"remote.call('claude','walk_to',{_UNUM},{x},{y})")
    return f"walking toward ({x},{y})"


@beta_tool
def mine_nearest(resource: str) -> str:
    """Mine the nearest tile of `resource` (iron-ore, copper-ore, coal, or stone).
    Walks to it if out of reach. One call mines one ore; call again to keep mining."""
    lua = (
        f"local u={_UNUM}; local c=game.get_entity_by_unit_number(u); local s=c.surface; "
        f"local es=s.find_entities_filtered{{name='{resource}',position=c.position,radius=60}}; "
        "local best,bd=nil,1e18; for _,e in ipairs(es) do local dx=e.position.x-c.position.x;local dy=e.position.y-c.position.y;local d=dx*dx+dy*dy;if d<bd then bd=d;best=e end end; "
        "if not best then rcon.print('none nearby') return end; "
        "local r=remote.call('claude','start_mining',u,best.position.x,best.position.y); "
        "if r.ok then rcon.print('mining') else remote.call('claude','walk_to',u,best.position.x,best.position.y); rcon.print('too far, walking to it') end"
    )
    return _rc(lua)


@beta_tool
def craft(recipe: str, count: int) -> str:
    """Hand-craft `count` of `recipe` (only unlocked, non-fluid recipes; ingredients
    must be in inventory — craft lower tiers first). Runs in the background."""
    out = _rc(
        f"local r=remote.call('claude','craft',{_UNUM},'{recipe}',{count}); "
        "rcon.print(r.ok and 'crafting' or ('cannot: '..tostring(r.error)))"
    )
    return out


@beta_tool
def place(item: str, x: int, y: int, direction: int = 0) -> str:
    """Place `item` from inventory as an entity at (x, y). direction 0/4/8/12 =
    N/E/S/W (matters for inserters/drills). Fails if blocked or not in inventory."""
    out = _rc(
        f"local r=remote.call('claude','place_entity',{_UNUM},'{item}',{x},{y},{direction}); "
        "rcon.print(r.ok and ('placed '..r.entity_name) or ('cannot: '..tostring(r.error)))"
    )
    return out


@beta_tool
def build_ghosts(radius: int = 14) -> str:
    """Revive nearby blueprint ghosts you have the items for (walk near them first).
    Returns how many were built / are still missing items."""
    out = _rc(
        f"local r=remote.call('claude','build_ghosts_in_range',{_UNUM},{radius}); "
        "rcon.print('built '..#(r.built or {})..', missing-items '..#(r.missing or {})..', seen '..(r.ghosts_seen or 0))"
    )
    return out


@beta_tool
def insert_into(x: int, y: int, item: str, count: int, slot: str) -> str:
    """Put `count` of `item` from inventory into an entity at (x, y). slot is one of
    'fuel' (burner fuel), 'input' (furnace/assembler input), or 'chest'."""
    slots = {
        "fuel": "defines.inventory.fuel",
        "input": "(defines.inventory.furnace_source or defines.inventory.crafter_input)",
        "chest": "defines.inventory.chest",
    }
    sl = slots.get(slot, "defines.inventory.chest")
    out = _rc(
        f"local r=remote.call('claude','insert_into_entity',{_UNUM},{x},{y},'{item}',{count},{sl}); "
        "rcon.print(r.ok and ('moved '..r.moved) or ('cannot: '..tostring(r.error)))"
    )
    return out


@beta_tool
def say(message: str) -> str:
    """Send a short message to JJ in the in-game chat. Use for milestones or blockers."""
    esc = message.replace("\\", "\\\\").replace("'", "\\'")
    _rc(f"game.print('[Companion] {esc}',{{color={{r=0.35,g=0.7,b=1}}}})")
    return "said"


@beta_tool
def look() -> str:
    """Re-read the live game state (your position, inventory, status, nearby ghosts,
    resources, and threats). Call this when you need fresh information."""
    return json.dumps(perceive())


TOOLS = [walk_to, mine_nearest, craft, place, build_ghosts, insert_into, say, look]

# ---------------------------------------------------------------------------
# REASON — the cached system prompt + the per-cycle decision
# ---------------------------------------------------------------------------

SYSTEM = """You are JJ's autonomous TEAMMATE — your own character in a Factorio
co-op game, separate from JJ's character. JJ plays alongside you in real time.
Stay near him, read what he's doing, and help: mine what's short, build his
ghosts, fetch/craft parts, cover him. You act FAST — pick one clear action and do
it; don't overthink, you'll re-decide in ~1.5 seconds.

HARD RULES (never violate):
- CRAFT, DON'T SPAWN. Only ever build things by mining, crafting, and placing real
  items. Never assume items appear from nowhere.
- Don't cheat exploration: only act on what your tools report.
- Survive: if a biter threat is within ~20 tiles or your health is low, walk AWAY
  from it toward the base. Don't fight — you have no weapons.
- Only craft unlocked, non-fluid recipes, and craft lower tiers first (the game
  won't auto-craft sub-ingredients).

HOW YOU WORK each turn: you are given the current game state. Decide the single most
useful next step toward the goal and take it with tools. Prefer: build nearby
blueprint ghosts you have items for; if you lack items, craft them; if you lack
ingredients, mine the raw resource. Keep moves small and concrete — you'll get fresh
state next turn. If nothing useful can be done, say so briefly and stop.

GEOMETRY NOTES: inserter `direction` is the side it PICKS FROM (0=N,4=E,8=S,12=W),
drop is opposite. A burner-mining-drill placed facing south drops ~1.3 tiles south
of its center. Furnaces/drills are 2x2.
"""

DEFAULT_GOAL = (
    "Help JJ in real time: stay near him, build any blueprint ghosts nearby, mine and "
    "fetch/craft what he needs, and keep yourself alive."
)


# --- planner tier: an occasional Opus call sets the teammate's current goal ---
PLANNER_SYSTEM = (
    "You are the STRATEGIST for JJ's autonomous Factorio teammate. Given the live game "
    "state and the standing mission, output ONE short paragraph (2-3 sentences) telling "
    "the teammate what to focus on next -- concrete and current (e.g. 'JJ is laying a "
    "drill blueprint east of you; mine iron to feed it, then build the ghosts'). No "
    "preamble, just the goal."
)

_current_goal = DEFAULT_GOAL


def _replan(client, state) -> None:
    """Smart tier (Opus): (re)set the teammate's current goal from live state."""
    global _current_goal
    try:
        resp = client.messages.create(
            model=PLANNER_MODEL,
            max_tokens=400,
            system=PLANNER_SYSTEM,
            thinking={"type": "adaptive"},
            output_config={"effort": "low"},
            messages=[{"role": "user", "content":
                "Standing mission: " + DEFAULT_GOAL +
                "\nLive state (JSON): " + json.dumps(state) +
                "\nWrite the teammate's current goal."}],
        )
        txt = "".join(b.text for b in resp.content
                      if getattr(b, "type", "") == "text").strip()
        if txt:
            _current_goal = txt
            print(f"[planner] goal -> {txt}", flush=True)
    except Exception as e:  # noqa: BLE001
        print(f"[planner] error: {e}", flush=True)


def run() -> int:
    if Anthropic is None:
        print("anthropic SDK not installed. run: pip install anthropic", file=sys.stderr)
        return 1
    client = Anthropic()  # reads ANTHROPIC_API_KEY (or an `ant auth login` profile)
    # Cache the STABLE prefix (rules + geometry). The goal is NOT in here -- it goes in
    # the per-cycle user message, so the planner can change it without busting the cache.
    system = [{
        "type": "text",
        "text": SYSTEM,
        "cache_control": {"type": "ephemeral"},  # cache reads ~0.1x
    }]
    print(f"[brain] driving teammate '{CHAR_NAME}' (unum {_UNUM}); "
          f"executor={FAST_MODEL} planner={PLANNER_MODEL}. Ctrl-C to stop.")
    cyc = 0
    while True:
        state = perceive()
        if not state.get("alive"):
            print("[brain] character not alive; waiting.")
            time.sleep(CYCLE_SECONDS)
            continue
        if cyc % PLAN_EVERY == 0:
            _replan(client, state)  # smart tier: refresh strategy periodically
        user = (
            "Current goal: " + _current_goal +
            "\nGame state (JSON):\n" + json.dumps(state) +
            "\n\nPick the single best next action toward the goal and do it with your "
            "tools NOW. Be fast: as few tool calls as possible -- fresh state in ~1.5s."
        )
        try:
            # Fast executor: Haiku, no extended thinking, small max_tokens = low latency.
            runner = client.beta.messages.tool_runner(
                model=FAST_MODEL,
                max_tokens=800,
                system=system,
                tools=TOOLS,
                messages=[{"role": "user", "content": user}],
            )
            for _msg in runner:
                pass  # tools execute inside the runner; we just drain it
        except KeyboardInterrupt:
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"[brain] error: {e}", flush=True)
        cyc += 1
        time.sleep(CYCLE_SECONDS)


def main() -> int:
    global _RCON, _UNUM
    os.environ["FACTORIO_RCON_PASSWORD"] = _resolve_rcon_password()
    _RCON = RconClient()
    _RCON.connect()
    _UNUM = _resolve_unum()
    return run()


if __name__ == "__main__":
    sys.exit(main())
