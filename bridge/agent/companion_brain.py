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
CYCLE_SECONDS = 1.5                 # tight loop so it reacts to JJ quickly
AUTONOMOUS_EVERY = 12              # cycles between autonomous ticks when JJ is quiet (~18s)


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
rcon.print(helpers.table_to_json({
  alive=true, x=math.floor(c.position.x), y=math.floor(c.position.y), inventory=items,
  jj = jp and {x=math.floor(jp.x),y=math.floor(jp.y),holding=jjcursor,mining=jjmining,dist=jjdist} or nil,
  near_jj=nearjj, nearest_resource=res,
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
2. If JJ made a REQUEST in chat ("grab copper", "build X here", "come help", "what are you
   doing?") -> understand it and reply + act on it.
3. If JJ just BUILT something (near_jj shows new entities) -> complement it (extend the line,
   feed it, belt it) rather than starting something unrelated.
4. Only if JJ isn't directing -> advance the base yourself (the standing mission).

Talk to JJ when it's useful: acknowledge his request, answer his questions, report a win,
or a quick quip. Keep it to one short sentence. Don't narrate every micro-action; don't
repeat yourself. If a request is genuinely ambiguous in a way that changes what you'd build,
ask ONE short question — otherwise just pick and go.

RULES: CRAFT/PLACE real items only (never spawn). Only build unlocked recipes. No power yet
means burner machines + burner inserters. Don't die to biters (retreat if low/threatened).

OUTPUT: reply with ONLY a JSON object, no prose:
{"reply": "<one short line to JJ, or null>", "action": {"type": "...", ...}}
action types:
  {"type":"goto","x":N,"y":N}                      walk to a spot (a ping, or to JJ)
  {"type":"mine","resource":"iron-ore|copper-ore|coal|stone"}   mine nearest of a resource
  {"type":"build_mine","resource":"...","x":N,"y":N,"count":N}  automated drills on ore there
  {"type":"build_smelt","x":N,"y":N,"resource":"..."}           furnace columns by ore chests there
  {"type":"craft","recipe":"...","count":N}
  {"type":"say"}                                   just talk (reply only, no physical action)
  {"type":"idle"}                                  nothing useful right now
Pick the SINGLE best action. Prefer acting on JJ's ping/request over anything else.
"""


def decide(client, state: dict, fresh_chat: list, ping_is_new: bool, mission: str) -> dict:
    ctx = {
        "companion": {"pos": [state.get("x"), state.get("y")], "inventory": state.get("inventory", {})},
        "jj": state.get("jj"),
        "jj_new_builds": state.get("_new_builds", []),
        "owner_ping": _LAST_PING if ping_is_new else None,
        "recent_chat": list(_CHAT_RECENT),
        "new_chat_this_turn": fresh_chat,
        "nearest_resource": state.get("nearest_resource", {}),
        "standing_mission": mission,
    }
    try:
        resp = client.messages.create(
            model=INTENT_MODEL,
            max_tokens=500,
            system=INTENT_SYSTEM,
            thinking={"type": "adaptive"},
            messages=[{"role": "user", "content": "Situation (JSON):\n" + json.dumps(ctx) +
                       "\nReply with the JSON decision only."}],
        )
        txt = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text").strip()
        txt = txt[txt.find("{"): txt.rfind("}") + 1]
        return json.loads(txt)
    except Exception as e:  # noqa: BLE001
        print(f"[intent] error: {e}", flush=True)
        return {"reply": None, "action": {"type": "idle"}}


# ---------------------------------------------------------------------------
# EXECUTE — carry out the decided action with tools + macros
# ---------------------------------------------------------------------------
_LAST_SAY = {"t": 0.0, "msg": ""}


def say(message: str) -> None:
    """Talk to JJ. Light throttle only (dedupe + 4s) — this is conversation, not spam-guard."""
    if not message:
        return
    now = time.time()
    if message.strip() == _LAST_SAY["msg"] or now - _LAST_SAY["t"] < 4:
        return
    _LAST_SAY["t"] = now
    _LAST_SAY["msg"] = message.strip()
    esc = message.replace("\\", "\\\\").replace("'", "\\'")
    _rc(f"game.print('[Companion] {esc}',{{color={{r=0.35,g=0.7,b=1}}}})")


def act(action: dict) -> None:
    t = action.get("type", "idle")
    try:
        if t == "goto":
            _rc(f"remote.call('claude','walk_to',{_UNUM},{int(action['x'])},{int(action['y'])})")
        elif t == "mine":
            res = action.get("resource", "iron-ore")
            _rc(f"local u={_UNUM}; local c=game.get_entity_by_unit_number(u); local s=c.surface; "
                f"local es=s.find_entities_filtered{{name='{res}',position=c.position,radius=60}}; "
                "local best,bd=nil,1e18; for _,e in ipairs(es) do local dx=e.position.x-c.position.x;local dy=e.position.y-c.position.y;local d=dx*dx+dy*dy;if d<bd then bd=d;best=e end end; "
                "if best then local r=remote.call('claude','start_mining',u,best.position.x,best.position.y); if not(r and r.ok) then remote.call('claude','walk_to',u,best.position.x,best.position.y) end end")
        elif t == "build_mine":
            bm.build_burner_mine(action.get("resource", "iron-ore"), int(action.get("count", 3)),
                                 float(action["x"]), float(action["y"]))
        elif t == "build_smelt":
            bm.build_smelt_from_chests(float(action["x"]), float(action["y"]),
                                       action.get("resource", "iron-ore"))
        elif t == "craft":
            rec = action.get("recipe"); cnt = int(action.get("count", 1))
            _rc(f"local u={_UNUM}; local c=game.get_entity_by_unit_number(u); local fr=c.force.recipes['{rec}']; "
                f"if fr and fr.enabled then remote.call('claude','craft',u,'{rec}',{cnt}) end")
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
            # decide when there's a JJ event, or on the slow autonomous tick
            jj_event = bool(fresh_chat) or ping_is_new or bool(new_builds)
            if jj_event or cyc % AUTONOMOUS_EVERY == 0:
                d = decide(client, state, fresh_chat, ping_is_new, _mission())
                if ping_is_new:
                    last_ping_seq = _PING_SEQ
                reply = d.get("reply")
                if reply and str(reply).lower() != "null":
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
    _UNUM = _resolve_unum()
    return run()


if __name__ == "__main__":
    sys.exit(main())
