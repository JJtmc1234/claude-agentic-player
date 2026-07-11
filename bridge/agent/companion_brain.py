"""
companion_brain.py — Project BRAIN, the JJ-centric intent loop.

Goal: make the companion feel like playing with someone INTELLIGENT — a teammate, not a
bot. The flip vs the old brain: its #1 job each cycle is JJ, not the base. It:
  1. PINGS = "do that, there."   JJ alt-clicks a spot -> go do the sensible thing there.
  2. CONVERSATION + REQUESTS.    Understands "grab some copper", "what are you doing?",
     "need help?" -> replies naturally AND acts.
  3. WATCH & COMPLEMENT.         Notices what JJ just built and extends/feeds it.
  4. AUTONOMOUS FALLBACK.        When JJ isn't directing, advance the base (goal.txt).

Two tiers:
  - INTENT brain (Opus 4.8): reads JJ's chat/pings/actions + game state -> decides
    {reply, action}. This is where the "intelligence" is. Called on any JJ event, or on a
    slower autonomous tick -- not every idle cycle (keeps it responsive AND affordable).
  - EXECUTION: deterministic tools + build-macros (build_macros.py) carry the action out.

STATUS: UNTESTED end-to-end (needs a live game + the claude-companion mod). Tune the feel
live with JJ driving pings/chat. Run: python bridge/agent/companion_brain.py
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
import agent.build_macros as bm      # noqa: E402  (share the RCON connection + reuse macros)

# ---------------------------------------------------------------------------
# config
# ---------------------------------------------------------------------------
INTENT_MODEL = "claude-opus-4-8"   # the "intelligence" — reasons about JJ's intent
CHAR_NAME = "companion"
OWNER = "Factoriobrine"             # JJ's in-game handle
OWNERS = (OWNER, "IdBaj98")
CYCLE_SECONDS = 1.0                 # read chat + react EVERY SECOND (JJ wants snappy responses)
AUTONOMOUS_EVERY = 15               # cycles between autonomous ticks when JJ is quiet (~15s)


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
_UNUM: int | None = None


def _rc(lua: str) -> str:
    assert _RCON is not None
    return _RCON.command("/silent-command " + lua).strip()


# ---------------------------------------------------------------------------
# PERCEIVE — JJ-centric: what is JJ doing/saying/pinging, plus the world
# ---------------------------------------------------------------------------
PERCEIVE_LUA = """
local u=%d
local c=game.get_entity_by_unit_number(u)
if not (c and c.valid) then rcon.print('{"alive":false}') return end
local s=c.surface
local inv=c.get_main_inventory()
local items={}
for _,e in pairs(inv.get_contents()) do if type(e)=='table' and e.name then items[e.name]=(items[e.name] or 0)+(e.count or 0) end end
-- JJ
local jj=game.players['%s']
local jp = jj and ((jj.character and jj.character.position) or jj.position)
local jjcursor = (jj and jj.cursor_stack and jj.cursor_stack.valid_for_read) and jj.cursor_stack.name or nil
local jjmining = (jj and jj.character and jj.mining_state and jj.mining_state.mining) or false
local jjdist = jp and math.floor(((jp.x-c.position.x)^2+(jp.y-c.position.y)^2)^0.5) or nil
-- entities JJ's force has near JJ (for watch-and-complement: Python diffs vs last cycle)
local nearjj={}
if jp then for _,e in ipairs(s.find_entities_filtered{position=jp,radius=16,force='player'}) do
  if e.type~='character' and e.unit_number then nearjj[#nearjj+1]={n=e.name,x=math.floor(e.position.x),y=math.floor(e.position.y),id=e.unit_number} end
end end
-- nearest resource of each type to the companion
local res={}
for _,rn in ipairs({'iron-ore','copper-ore','coal','stone'}) do
  local es=s.find_entities_filtered{name=rn,position=c.position,radius=60}
  local best,bd=nil,1e18
  for _,e in ipairs(es) do local dx=e.position.x-c.position.x;local dy=e.position.y-c.position.y;local d=dx*dx+dy*dy;if d<bd then bd=d;best=e end end
  if best then res[rn]={x=math.floor(best.position.x),y=math.floor(best.position.y),dist=math.floor(bd^0.5)} end
end
-- nearest biter/threat
local threat=nil
local en=s.find_nearest_enemy{position=c.position,max_distance=70,force=c.force}
if en and en.valid then threat={name=en.name,x=math.floor(en.position.x),y=math.floor(en.position.y),dist=math.floor(((en.position.x-c.position.x)^2+(en.position.y-c.position.y)^2)^0.5)} end
-- do I have combat gear? (so the brain knows if it can fight or must retreat)
local armed=(inv.get_item_count('submachine-gun')>0 or inv.get_item_count('pistol')>0) and (inv.get_item_count('firearm-magazine')>0 or inv.get_item_count('piercing-rounds-magazine')>0)
local ag=c.get_inventory(defines.inventory.character_guns)
local equipped_gun = ag and ag[1] and ag[1].valid_for_read or false
rcon.print(helpers.table_to_json({
  alive=true, x=math.floor(c.position.x), y=math.floor(c.position.y), health=math.floor(c.health or 0),
  inventory=items,
  jj = jp and {x=math.floor(jp.x),y=math.floor(jp.y),holding=jjcursor,mining=jjmining,dist=jjdist} or nil,
  near_jj=nearjj, nearest_resource=res, threat=threat, have_weapon=armed, weapon_equipped=equipped_gun,
}))
"""


def perceive() -> dict:
    out = _rc(PERCEIVE_LUA % (_UNUM, OWNER))
    try:
        return json.loads(out)
    except Exception:  # noqa: BLE001
        return {"alive": False, "raw": out}


# --- chat + pings (JJ talks to us; a map ping arrives as a [gps=x,y] chat tag) ---
_CHAT_INDEX = 0
_CHAT_RECENT: list = []
_LAST_PING: dict | None = None
_PING_SEQ = 0                      # bumps when a NEW owner ping arrives
_GPS_RE = re.compile(r"\[gps=(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)")


def read_chat() -> list:
    """Pull new chat since cursor; return the NEW messages this cycle; track pings."""
    global _CHAT_INDEX, _LAST_PING, _PING_SEQ
    out = _rc(f"local r=remote.call('claude','get_chat',{_CHAT_INDEX}); rcon.print(helpers.table_to_json(r))")
    fresh = []
    try:
        data = json.loads(out)
    except Exception:  # noqa: BLE001
        return fresh
    _CHAT_INDEX = data.get("latest_index", _CHAT_INDEX)
    for m in data.get("messages", []):
        player = m.get("player", "")
        text = str(m.get("message", ""))
        if text.startswith("[Companion]"):
            continue
        owner = player in OWNERS
        gm = _GPS_RE.search(text)
        if gm and owner:
            _LAST_PING = {"x": int(float(gm.group(1))), "y": int(float(gm.group(2)))}
            _PING_SEQ += 1
        rec = {"from": player, "owner": owner, "text": text}
        fresh.append(rec)
        _CHAT_RECENT.append(rec)
    del _CHAT_RECENT[:-8]
    return fresh


# ---------------------------------------------------------------------------
# INTENT — Opus decides {reply, action} with JJ as the priority
# ---------------------------------------------------------------------------
try:
    from anthropic import Anthropic
except Exception:  # noqa: BLE001
    Anthropic = None  # type: ignore

INTENT_SYSTEM = """You are JJ's in-game Factorio TEAMMATE (a character named 'companion',
separate from JJ). You are helpful, competent, and talk like a real co-op partner — warm,
brief, a little personality; never robotic, never spammy.

YOUR #1 JOB EVERY TURN IS JJ. Priority order:
1. If JJ PINGED a location (owner_ping + a fresh ping this turn) -> that's "do that, there":
   go help at that spot (mine the ore there, build there, or just go to him).
2. If JJ made a REQUEST in chat ("grab copper", "build X here", "come help", "bring me 100
   iron plates", "what are you doing?") -> understand it and act. His NEWEST message
   (new_chat_this_turn / the last recent_chat line) is the CURRENT order and overrides older
   ones — if he now wants iron plates, stop hitting rocks and fetch the plates. To mine rocks
   use resource "coal" (auto-targets huge-rock, which gives coal) or "huge-rock"/"big-rock".
3. If JJ just BUILT something (near_jj shows new entities) -> complement it (extend the line,
   feed it, belt it) rather than starting something unrelated.
4. Only if JJ isn't directing -> advance the base yourself (the standing mission).

Talk to JJ when it's useful: acknowledge his request, answer his questions, report a win,
or a quick quip. Keep it to one short sentence. Don't narrate every micro-action; NEVER
repeat the same line twice in a row (if you already said you're on it, stay quiet and act).
If a request is genuinely ambiguous in a way that changes what you'd build, ask ONE short
question — otherwise just pick and go.

EXPLAIN YOUR REASONING: when you start something on your own or make a notable call, add a
short WHY so JJ knows you're thinking ahead — e.g. "grabbing copper, we'll need it for
circuits" or "walling the east first, that's where biters come from." One line, not a lecture.

FETCH / COURIER: if JJ asks you to bring him something, use `fetch` — you gather it (from
your inventory or base chests) and deliver into his hands. BUT fetch only moves items that
ALREADY EXIST. Check your `inventory` first: if you don't have it and none exists yet (e.g.
he wants 100 iron plates but nothing's been smelted), do NOT pretend to deliver or say you're
on the way — tell him honestly ("no iron plates yet, nothing's smelted — want me to mine and
smelt some?"). If he says yes, PRODUCE it: mine the ore, build_smelt to make plates, then
fetch. Never claim you're bringing something you don't have.

COMBAT & SAFETY: `threat` is the nearest enemy; `have_weapon` / `weapon_equipped` say if you
can fight. If a threat is close: WARN JJ ("biters east, ~30 tiles!"). If you're armed, `equip`
then `attack` to fight alongside him or defend the base; if NOT armed or health is low,
retreat toward JJ / the base — don't die. Build turret defenses when asked.

RULES: CRAFT/PLACE real items only (never spawn). Only build unlocked recipes. No power yet
means burner machines + burner inserters.

YOU CAN DESIGN YOUR OWN ACTIONS. You are NOT limited to the presets — compose the PRIMITIVES
below into a `plan` (an ordered list of steps) to build or do anything JJ asks. If you invent
a useful multi-step action, `remember` it with a name so you can `recall` it later — that's
how you get smarter over time. Think for yourself; the presets are a starting kit, not a cage.

OUTPUT: reply with ONLY a JSON object, no prose:
{"reply": "<one short line to JJ, or null>", "action": {"type": "...", ...}}

Composition:
  {"type":"plan","steps":[<action>, <action>, ...]}   run steps in order (design a custom action)
  {"type":"remember","name":"wall_segment","steps":[...]}   save a named custom action for reuse
  {"type":"recall","name":"wall_segment"}             run a previously-remembered action

Primitives (compose these freely):
  {"type":"goto","x":N,"y":N}                         walk to a spot
  {"type":"mine","resource":"iron-ore|copper-ore|coal|stone"}
  {"type":"place","item":"...","x":N,"y":N,"dir":0|4|8|12}   place an item from inventory (dir = for
                                                       inserters the side it PICKS FROM; N=0 E=4 S=8 W=12)
  {"type":"insert","x":N,"y":N,"item":"...","count":N,"slot":"fuel|input|chest"}   into a machine there
  {"type":"take","x":N,"y":N,"item":"...","count":N,"slot":"output|fuel|chest"}     out of a machine there
  {"type":"craft","recipe":"...","count":N}
  {"type":"research","tech":"..."}
  {"type":"fetch","item":"...","count":N}             gather item + deliver it to JJ
  {"type":"equip"}                                     wear/wield any combat gear you have
  {"type":"attack","x":N,"y":N}                        equip + go fight enemies at (x,y) (omit x,y = nearest)
Presets (validated shortcuts — use when they fit):
  {"type":"build_mine","resource":"...","x":N,"y":N,"count":N}   automated drills+chests on ore there
  {"type":"build_smelt","x":N,"y":N,"resource":"..."}            fueled furnace columns by ore chests there
  {"type":"say"} / {"type":"idle"}
Pick the SINGLE best action (a `plan` counts as one). Prefer JJ's ping/request over anything else.
No power yet -> use BURNER inserters (electric ones sit dead). CRAFT/PLACE real items, never spawn.
"""


def decide(client, state: dict, fresh_chat: list, ping_is_new: bool, mission: str) -> dict:
    ctx = {
        "companion": {"pos": [state.get("x"), state.get("y")], "health": state.get("health"),
                      "inventory": state.get("inventory", {}),
                      "have_weapon": state.get("have_weapon"), "weapon_equipped": state.get("weapon_equipped")},
        "jj": state.get("jj"),
        "jj_new_builds": state.get("_new_builds", []),
        "owner_ping": _LAST_PING if ping_is_new else None,
        "recent_chat": list(_CHAT_RECENT),
        "new_chat_this_turn": fresh_chat,
        "nearest_resource": state.get("nearest_resource", {}),
        "threat": state.get("threat"),
        "standing_mission": mission,
    }
    try:
        resp = client.messages.create(
            model=INTENT_MODEL,
            max_tokens=1024,      # plenty for {reply, action}; no thinking -> no truncation
            system=INTENT_SYSTEM,
            messages=[{"role": "user", "content": "Situation (JSON):\n" + json.dumps(ctx) +
                       "\nReply with ONLY the compact JSON decision, no prose, no code fence."}],
        )
        txt = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        i, j = txt.find("{"), txt.rfind("}")
        if i < 0 or j <= i:
            return {"reply": None, "action": {"type": "idle"}}
        return json.loads(txt[i:j + 1])
    except Exception as e:  # noqa: BLE001
        print(f"[intent] parse/api error: {e} | raw={txt[:120] if 'txt' in dir() else '?'}", flush=True)
        return {"reply": None, "action": {"type": "idle"}}


# ---------------------------------------------------------------------------
# EXECUTE — carry out the decided action with tools + macros
# ---------------------------------------------------------------------------
_LAST_SAY = {"t": 0.0, "msg": ""}


def say(message: str) -> None:
    """Talk to JJ, but never spam. Suppress near-duplicates (same opening) for 25s, and
    keep a light 3s global throttle so it can converse without machine-gunning."""
    if not message:
        return
    now = time.time()
    m = message.strip()
    prev = _LAST_SAY["msg"]
    # same opening phrase recently -> it's repeating itself; stay quiet
    if prev and m[:18].lower() == prev[:18].lower() and now - _LAST_SAY["t"] < 25:
        return
    if now - _LAST_SAY["t"] < 3:
        return
    _LAST_SAY["t"] = now
    _LAST_SAY["msg"] = m
    esc = m.replace("\\", "\\\\").replace("'", "\\'")
    _rc(f"game.print('[Companion] {esc}',{{color={{r=0.35,g=0.7,b=1}}}})")


# --- learned actions: the companion can invent + name custom actions and reuse them ---
_LEARNED_FILE = _HERE / "learned_actions.json"
_LEARNED: dict = {}


def _load_learned() -> None:
    global _LEARNED
    try:
        if _LEARNED_FILE.exists():
            _LEARNED = json.loads(_LEARNED_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        _LEARNED = {}


def _save_learned() -> None:
    try:
        _LEARNED_FILE.write_text(json.dumps(_LEARNED, indent=1), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


# --- safe primitives (real items only; crafter-inventory + character-exclusion aware) ---
def _prim_place(item: str, x, y, dir=0) -> None:
    _rc(f"remote.call('claude','place_entity',{_UNUM},'{item}',{float(x)},{float(y)},{int(dir)})")


def _prim_move_inv(x, y, item, count, slot, take: bool) -> None:
    if take:
        inv_expr = {"output": "ent.get_output_inventory()", "fuel": "ent.get_fuel_inventory()",
                    "chest": "ent.get_inventory(defines.inventory.chest)"}.get(slot, "ent.get_output_inventory()")
    else:
        inv_expr = {"fuel": "ent.get_fuel_inventory()",
                    "input": "ent.get_inventory(defines.inventory.crafter_input or defines.inventory.furnace_source or defines.inventory.lab_input or 2)",
                    "chest": "ent.get_inventory(defines.inventory.chest)"}.get(slot, "ent.get_inventory(defines.inventory.chest)")
    lua = (
        f"local u={_UNUM}; local c=game.get_entity_by_unit_number(u); local s=c.surface; local ci=c.get_main_inventory(); "
        f"local cand=s.find_entities_filtered{{position={{{float(x)},{float(y)}}},radius=0.7}}; local ent=nil; "
        "for _,e in ipairs(cand) do if e.valid and e.type~='character' and e.get_inventory then ent=e break end end; "
        "if not ent then return end; "
        f"local inv={inv_expr}; if not inv then return end; ")
    if take:
        lua += (f"local avail=inv.get_item_count('{item}'); local w=math.min({int(count)},avail); if w<=0 then return end; "
                f"local mv=ci.insert{{name='{item}',count=w}}; if mv>0 then inv.remove{{name='{item}',count=mv}} end")
    else:
        lua += (f"local have=ci.get_item_count('{item}'); local w=math.min({int(count)},have); if w<=0 then return end; "
                f"local mv=inv.insert{{name='{item}',count=w}}; if mv>0 then ci.remove{{name='{item}',count=mv}} end")
    _rc(lua)


def act(action: dict, _depth: int = 0) -> None:
    if not isinstance(action, dict) or _depth > 3:
        return
    t = action.get("type", "idle")
    try:
        if t == "plan":
            for step in (action.get("steps") or [])[:24]:
                act(step, _depth + 1)
        elif t == "remember":
            name = str(action.get("name", "")).strip()
            steps = action.get("steps") or []
            if name and steps:
                _LEARNED[name] = steps; _save_learned()
                print(f"[learned] saved custom action '{name}' ({len(steps)} steps)", flush=True)
        elif t == "recall":
            steps = _LEARNED.get(str(action.get("name", "")).strip())
            if steps:
                act({"type": "plan", "steps": steps}, _depth + 1)
        elif t == "goto":
            _rc(f"remote.call('claude','walk_to',{_UNUM},{int(action['x'])},{int(action['y'])})")
        elif t == "mine":
            res = action.get("resource", "iron-ore")
            _rc(f"local u={_UNUM}; local c=game.get_entity_by_unit_number(u); local s=c.surface; local res='{res}'; "
                "local best,bd=nil,1e18; "
                "for _,e in ipairs(s.find_entities_filtered{name=res,position=c.position,radius=250}) do local dx=e.position.x-c.position.x;local dy=e.position.y-c.position.y;local d=dx*dx+dy*dy;if d<bd then bd=d;best=e end end; "
                # coal/stone also come from ROCKS — prefer huge-rock (gives coal), then big-rock
                "if (not best or bd>60*60) and (res=='coal' or res=='stone') then local rb,rbd=nil,1e18; "
                "for _,rn in ipairs({'huge-rock','big-rock','big-sand-rock'}) do for _,e in ipairs(s.find_entities_filtered{name=rn,position=c.position,radius=150}) do local dx=e.position.x-c.position.x;local dy=e.position.y-c.position.y;local d=dx*dx+dy*dy;if d<rbd then rbd=d;rb=e end end; if rb then break end end; "
                "if rb then best=rb;bd=rbd end end; "
                "if best then local r=remote.call('claude','start_mining',u,best.position.x,best.position.y); if not(r and r.ok) then remote.call('claude','walk_to',u,best.position.x,best.position.y) end end")
        elif t == "place":
            _prim_place(action["item"], action["x"], action["y"], action.get("dir", 0))
        elif t == "insert":
            _prim_move_inv(action["x"], action["y"], action["item"], action.get("count", 5), action.get("slot", "chest"), take=False)
        elif t == "take":
            _prim_move_inv(action["x"], action["y"], action["item"], action.get("count", 50), action.get("slot", "output"), take=True)
        elif t == "research":
            tech = action.get("tech", "")
            _rc(f"local ok=game.forces.player.add_research('{tech}'); rcon.print('research {tech} -> '..tostring(ok))")
        elif t == "craft":
            rec = action.get("recipe"); cnt = int(action.get("count", 1))
            _rc(f"local u={_UNUM}; local c=game.get_entity_by_unit_number(u); local fr=c.force.recipes['{rec}']; "
                f"if fr and fr.enabled then remote.call('claude','craft',u,'{rec}',{cnt}) end")
        elif t == "fetch":
            # courier: top up `item` from nearby base chests, walk to JJ, deliver into his inventory
            item = action.get("item", ""); want = int(action.get("count", 10))
            _rc(f"local u={_UNUM}; local c=game.get_entity_by_unit_number(u); local s=c.surface; local ci=c.get_main_inventory(); "
                f"local item='{item}'; local want={want}; local have=ci.get_item_count(item); "
                "if have<want then for _,ch in ipairs(s.find_entities_filtered{type={'container','logistic-container'},position=c.position,radius=40}) do "
                "  local cin=ch.get_inventory(defines.inventory.chest); if cin then local av=cin.get_item_count(item); local tk=math.min(want-have,av); if tk>0 then local mv=ci.insert{name=item,count=tk}; if mv>0 then cin.remove{name=item,count=mv}; have=have+mv end end end; if have>=want then break end end end; "
                "local jj=game.players['Factoriobrine']; local jp=jj and ((jj.character and jj.character.position) or jj.position); "
                "if jp then remote.call('claude','walk_to',u,jp.x,jp.y); if jj.character and ((jp.x-c.position.x)^2+(jp.y-c.position.y)^2)<100 then local give=math.min(ci.get_item_count(item),want); if give>0 then local mv=jj.character.get_main_inventory().insert{name=item,count=give}; if mv>0 then ci.remove{name=item,count=mv} end end end end")
        elif t == "equip":
            _rc(f"local u={_UNUM}; local c=game.get_entity_by_unit_number(u); local ci=c.get_main_inventory(); "
                "local function eq(it) local h=ci.get_item_count(it); if h<=0 then return end; local p=prototypes.item[it]; local ty=p and p.type; local inv; "
                "if ty=='armor' then inv=c.get_inventory(defines.inventory.character_armor) elseif ty=='gun' then inv=c.get_inventory(defines.inventory.character_guns) elseif ty=='ammo' then inv=c.get_inventory(defines.inventory.character_ammo) else return end; "
                "if inv then local mv=inv.insert{name=it,count=h}; if mv>0 then ci.remove{name=it,count=mv} end end end; "
                "for _,it in ipairs({'power-armor','modular-armor','heavy-armor','light-armor','submachine-gun','pistol','piercing-rounds-magazine','firearm-magazine'}) do eq(it) end")
        elif t == "attack":
            # equip whatever we have, then approach the nearest enemy (character auto-fires if armed)
            act({"type": "equip"}, _depth + 1)
            tx = action.get("x"); ty = action.get("y")
            if tx is not None and ty is not None:
                _rc(f"remote.call('claude','walk_to',{_UNUM},{int(tx)},{int(ty)})")
            else:
                _rc(f"local u={_UNUM}; local c=game.get_entity_by_unit_number(u); local en=c.surface.find_nearest_enemy{{position=c.position,max_distance=50,force=c.force}}; "
                    "if en and en.valid then remote.call('claude','walk_to',u,en.position.x,en.position.y) end")
        elif t == "build_mine":
            bm.build_burner_mine(action.get("resource", "iron-ore"), int(action.get("count", 3)),
                                 float(action["x"]), float(action["y"]))
        elif t == "build_smelt":
            bm.build_smelt_from_chests(float(action["x"]), float(action["y"]),
                                       action.get("resource", "iron-ore"))
        # 'say' and 'idle' need no physical action
    except Exception as e:  # noqa: BLE001
        print(f"[act] {t} error: {e}", flush=True)


# ---------------------------------------------------------------------------
# LOOP
# ---------------------------------------------------------------------------
def _mission() -> str:
    f = _HERE / "goal.txt"
    try:
        if f.exists():
            t = f.read_text(encoding="utf-8").strip()
            if t:
                return t
    except Exception:  # noqa: BLE001
        pass
    return "Help JJ and build a clean, automated base."


def _resolve_unum() -> int:
    out = _rc("local ch=remote.call('claude','list_chars'); rcon.print(tostring(ch['" + CHAR_NAME + "']))")
    if not out.isdigit():
        out = _rc(f"local p=game.players['{OWNER}']; local pos=(p and ((p.character and p.character.position) or p.position)) or {{x=0,y=0}}; "
                  f"local r=remote.call('claude','spawn_named_char','{CHAR_NAME}',{{pos.x+3,pos.y}}); rcon.print(tostring(r.unit_number))")
    return int(out)


def run() -> int:
    if Anthropic is None:
        print("anthropic SDK not installed: pip install anthropic", file=sys.stderr)
        return 1
    client = Anthropic()
    print(f"[companion_brain] JJ-centric loop live; intent={INTENT_MODEL}. Ctrl-C to stop.")
    seen_ids: set = set()
    last_ping_seq = _PING_SEQ
    had_threat = False
    cyc = 0
    while True:
        try:
            state = perceive()
            if not state.get("alive"):
                time.sleep(CYCLE_SECONDS); continue
            fresh_chat = read_chat()
            # watch-and-complement: which entities near JJ are NEW since last cycle
            cur_ids = {e["id"]: e for e in state.get("near_jj", [])}
            new_builds = [e for eid, e in cur_ids.items() if eid not in seen_ids]
            seen_ids = set(cur_ids.keys())
            state["_new_builds"] = new_builds
            ping_is_new = _PING_SEQ != last_ping_seq
            threat_now = bool(state.get("threat"))
            threat_new = threat_now and not had_threat
            had_threat = threat_now
            # ONLY talk when JJ actually interacts (chat/ping) or a threat just appeared.
            # Never chatter on autonomous ticks -> that was the spam.
            talk_ok = bool(fresh_chat) or ping_is_new or threat_new
            jj_event = talk_ok or bool(new_builds)
            if jj_event or cyc % AUTONOMOUS_EVERY == 0:
                d = decide(client, state, fresh_chat, ping_is_new, _mission())
                if ping_is_new:
                    last_ping_seq = _PING_SEQ
                reply = d.get("reply")
                if talk_ok and reply and str(reply).lower() != "null":
                    say(str(reply))
                act(d.get("action") or {"type": "idle"})
        except KeyboardInterrupt:
            return 0
        except Exception as e:  # noqa: BLE001
            print(f"[loop] error: {e}", flush=True)
        cyc += 1
        time.sleep(CYCLE_SECONDS)


def main() -> int:
    global _RCON, _UNUM
    os.environ["FACTORIO_RCON_PASSWORD"] = _resolve_rcon_password()
    _RCON = RconClient(); _RCON.connect()
    bm._RCON = _RCON  # share the connection so build-macros run on it
    _load_learned()   # restore any custom actions the companion invented before
    _UNUM = _resolve_unum()
    return run()


if __name__ == "__main__":
    sys.exit(main())
