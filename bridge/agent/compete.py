"""
compete.py — Agent Competition referee + live scoreboard (per-force tournament).

Turns the 4-agent BRAIN team into a spectator sport. Each employee (miner/courier/builder/
scout) plays on ITS OWN Factorio force in its own corner of the world. A round names one target
item; the FIRST force to have produced >= 1 of it (mined or refined) wins the round. Points are
awarded 100 / 50 / 10 / 0 for 1st / 2nd / 3rd / 4th and accumulate across rounds into a running
tournament standings.

It sets the round goal for the brains by swapping goal.txt with a RACE directive (brains read
goal.txt every cycle as their standing mission -> no brain-code change), scores each force over
RCON via its item production statistics, renders a live leaderboard to the terminal + in-game
chat, then awards points and restores the normal goal.txt when the round ends.

Prereq: run setup_arena.py once (after the mod is loaded + chars exist) to create the 4 forces
and put each employee's character on its force.

Run:
    python bridge/agent/compete.py --item wood  --round "chop a tree"
    python bridge/agent/compete.py --item iron-ore --round "mine iron" --secs 240
    python bridge/agent/compete.py --standings          # show cumulative standings
    python bridge/agent/compete.py --reset              # clear standings (new tournament)
    python bridge/agent/compete.py --restore            # just put the normal goal.txt back

Stop a round anytime with Ctrl-C — it scores what happened, then restores goal.txt.
"""

from __future__ import annotations

import argparse
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

CONTESTANTS = ["miner", "courier", "builder", "scout"]
POINTS = [100, 50, 10, 0]            # 1st, 2nd, 3rd, 4th+
_GOAL_FILE = _HERE / "goal.txt"
_BACKUP_FILE = _HERE / "goal.race-backup.txt"
_STANDINGS_FILE = _HERE / "compete_standings.json"
_RACE_FILE = _HERE / "race.json"          # brains read this: {item,goal,active} -> race mode
_ID_RE = re.compile(r"[^a-z0-9_-]")


def _safe(name: str) -> str:
    """Constrain an item name to Factorio's id charset so it can't break/inject the Lua."""
    return _ID_RE.sub("", str(name).lower())


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


def _say(rcon: RconClient, msg: str) -> None:
    """Broadcast a line into the in-game chat, colored like the other Claude messages."""
    esc = msg.replace("\\", "\\\\").replace("'", "\\'").replace("\r", " ").replace("\n", " ")
    rcon.command("/silent-command game.print('[Race] " + esc + "', {color={r=1,g=0.85,b=0.4}})")


# ---------------------------------------------------------------------------
# scoring — one batched RCON read of how much of the target item each force HOLDS
#
# JJ's rule: each employee is its OWN force; a round is won when "at least one (mined/refined)
# item exists in their force." The mod mines by inserting items straight into inventory, which
# does NOT register in force PRODUCTION STATISTICS -> we instead count the item across every
# inventory owned by the force (its character + any chests it builds). We score the DELTA since
# round start so a force's pre-round stock doesn't count.
# ---------------------------------------------------------------------------
def _produced_lua(item: str) -> str:
    forces = "{" + ",".join("'" + n + "'" for n in CONTESTANTS) + "}"
    return (
        "local item='" + item + "'; local names=" + forces + ";"
        "local surf=game.surfaces['nauvis']; local out={};"
        "for _,fn in ipairs(names) do local f=game.forces[fn]; local n=-1;"
        "  if f then n=0;"
        "    for _,e in ipairs(surf.find_entities_filtered{force=fn}) do if e.valid then"
        "      local ok,inv=pcall(function() return e.get_main_inventory() end);"
        "      if ok and inv then n=n+inv.get_item_count(item) end end end end;"
        "  out[fn]=n end;"
        "rcon.print(helpers.table_to_json(out))"
    )


def read_produced(rcon: RconClient, item: str) -> dict:
    """Return {name: item_held_by_force}; -1 means that force does not exist yet."""
    result = {n: -1 for n in CONTESTANTS}
    try:
        out = rcon.command("/silent-command " + _produced_lua(item)).strip()
        data = json.loads(out)
        for n in CONTESTANTS:
            result[n] = int(data.get(n, -1))
    except Exception:  # noqa: BLE001
        pass
    return result


# ---------------------------------------------------------------------------
# standings (persistent across rounds)
# ---------------------------------------------------------------------------
def load_standings() -> dict:
    try:
        return json.loads(_STANDINGS_FILE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"points": {n: 0 for n in CONTESTANTS}, "rounds": []}


def save_standings(st: dict) -> None:
    _STANDINGS_FILE.write_text(json.dumps(st, indent=2), encoding="utf-8")


def standings_str(st: dict) -> str:
    pts = st.get("points", {})
    rows = sorted(CONTESTANTS, key=lambda n: pts.get(n, 0), reverse=True)
    return "  |  ".join(f"{n}:{pts.get(n, 0)}" for n in rows)


# ---------------------------------------------------------------------------
# goal.txt swap (the race directive the brains read each cycle)
# ---------------------------------------------------------------------------
def _race_directive(item: str, goal: int, round_name: str) -> str:
    label = round_name or f"first to {item}"
    return (
        "*** AGENT COMPETITION — LIVE RACE (overrides your normal role) ***\n"
        f"ROUND: {label}\n"
        f"CHALLENGE: be the FIRST to produce {goal} x {item} for your force. Just get it — "
        "mine/gather it in YOUR corner of the map as fast as you possibly can.\n\n"
        "RULES:\n"
        "- You each have your OWN corner stocked with all raw resources (iron, copper, coal,\n"
        "  stone, water, oil, fish, wood, uranium). Work in YOUR corner only.\n"
        f"- Win = your force has produced >= {goal} {item} (mined or refined). Speed is all that\n"
        "  matters. Do the single fastest thing that yields it (e.g. chop a tree for wood, mine\n"
        "  an ore tile). Don't over-build; just GET the item.\n"
        "- This is COMPETITIVE: race the others, don't help them.\n"
        "- Verify the real item name live if unsure (K2 Spaced Out modpack, not vanilla). Only\n"
        "  build unlocked recipes; never spawn items — mine/craft for real.\n"
        "- JJ STILL COMES FIRST: if JJ pings or asks you something, help him, then resume racing.\n"
        "- Keep chat minimal; a little trash talk to JJ is fine.\n"
        f"GO — first to {goal} {item} wins the round!\n"
    )


def _set_race(item: str, goal: int, active: bool) -> None:
    _RACE_FILE.write_text(json.dumps({"item": item, "goal": goal, "active": active}),
                          encoding="utf-8")


def start_round(item: str, goal: int, round_name: str) -> None:
    if not _BACKUP_FILE.exists():        # preserve the REAL goal only once (repeat starts are safe)
        try:
            _BACKUP_FILE.write_text(_GOAL_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        except FileNotFoundError:
            _BACKUP_FILE.write_text("", encoding="utf-8")
    _GOAL_FILE.write_text(_race_directive(item, goal, round_name), encoding="utf-8")
    _set_race(item, goal, True)          # flip brains into deterministic race mode


def restore_goal() -> bool:
    """End race mode + put the pre-race goal.txt back. Returns True if a backup was restored."""
    _set_race("", 0, False)              # brains leave race mode -> back to normal LLM loop
    if _BACKUP_FILE.exists():
        _GOAL_FILE.write_text(_BACKUP_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        _BACKUP_FILE.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# leaderboard rendering
# ---------------------------------------------------------------------------
def render(scores: dict, finished: list, goal: int, item: str, rnd: str, elapsed: float) -> str:
    def rank_key(n):
        return (finished.index(n) if n in finished else 99, -scores.get(n, 0))
    order = sorted(CONTESTANTS, key=rank_key)
    lines = [f"ROUND: {rnd or item}   (first to {goal} {item})   elapsed {int(elapsed)}s", "-" * 52]
    for i, n in enumerate(order):
        sc = scores.get(n, -1)
        if n in finished:
            tag = f" DONE #{finished.index(n)+1} (+{POINTS[min(finished.index(n), 3)]})"
        elif sc < 0:
            tag = " (no force!)"
        else:
            tag = ""
        shown = f"{max(sc, 0):>4}"
        lines.append(f"{i+1}. {n:<8} {shown}/{goal}{tag}")
    lines.append("-" * 52)
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Agent competition referee (per-force tournament)")
    ap.add_argument("--item", default="wood", help="target item for this round")
    ap.add_argument("--round", dest="round_name", default="", help="round label (e.g. 'chop a tree')")
    ap.add_argument("--goal", type=int, default=1, help="count needed to win the round (default 1)")
    ap.add_argument("--secs", type=int, default=300, help="round time cap; unfinished forces get 0")
    ap.add_argument("--poll", type=float, default=2.0, help="seconds between score reads")
    ap.add_argument("--chat-every", type=float, default=20.0, help="seconds between in-game posts")
    ap.add_argument("--standings", action="store_true", help="print cumulative standings and exit")
    ap.add_argument("--reset", action="store_true", help="clear standings (new tournament) and exit")
    ap.add_argument("--restore", action="store_true", help="restore the normal goal.txt and exit")
    args = ap.parse_args()

    if args.standings:
        print("STANDINGS:", standings_str(load_standings()))
        return 0
    if args.reset:
        save_standings({"points": {n: 0 for n in CONTESTANTS}, "rounds": []})
        print("standings reset.")
        return 0

    os.environ.setdefault("FACTORIO_RCON_PASSWORD", _resolve_rcon_password())

    if args.restore:
        print("restored normal goal.txt" if restore_goal() else "no race backup to restore")
        return 0

    item = _safe(args.item)
    goal = max(1, args.goal)
    rnd = args.round_name
    is_tty = sys.stdout.isatty()

    start_round(item, goal, rnd)
    print(f"[compete] round '{rnd or item}' started: first to {goal} x {item}.", flush=True)

    baseline: dict = {}
    finished: list = []            # names in the order they crossed the goal
    last_chat = 0.0
    t0 = time.time()

    try:
        with RconClient() as rcon:
            missing = [n for n, v in read_produced(rcon, item).items() if v < 0]
            if missing:
                _say(rcon, f"WARNING: forces missing ({', '.join(missing)}) — run setup_arena.py first.")
                print(f"[compete] WARNING: forces do not exist: {missing} — run setup_arena.py",
                      flush=True)

            _say(rcon, f"ROUND: {rnd or item}! First force to {goal} {item} wins. GO!")
            while True:
                raw = read_produced(rcon, item)
                for n, c in raw.items():
                    if c >= 0 and n not in baseline:
                        baseline[n] = c
                scores = {n: (raw[n] - baseline.get(n, 0)) if raw[n] >= 0 else -1 for n in CONTESTANTS}
                elapsed = time.time() - t0

                for n in CONTESTANTS:                       # record finishers in crossing order
                    if n not in finished and scores[n] >= goal:
                        finished.append(n)
                        _say(rcon, f"{n} finishes #{len(finished)}! (+{POINTS[min(len(finished)-1,3)]})")

                board = render(scores, finished, goal, item, rnd, elapsed)
                if is_tty:
                    os.system("cls" if os.name == "nt" else "clear")
                    print(board, flush=True)
                else:
                    print("\n" + board, flush=True)

                # round ends when everyone finished, or the time cap hits
                live = [n for n in CONTESTANTS if scores[n] >= 0]
                if finished and all(n in finished for n in live):
                    break
                if args.secs and elapsed >= args.secs:
                    break

                now = time.time()
                if now - last_chat >= args.chat_every:
                    prog = "  ".join(f"{n}:{max(scores[n],0)}" for n in CONTESTANTS)
                    _say(rcon, prog)
                    last_chat = now

                time.sleep(args.poll)

            # award points: finishers by order, everyone else 0 (tie for last)
            st = load_standings()
            gained = {}
            for i, n in enumerate(finished):
                p = POINTS[i] if i < len(POINTS) else 0
                gained[n] = p
                st["points"][n] = st["points"].get(n, 0) + p
            for n in CONTESTANTS:
                gained.setdefault(n, 0)
            st.setdefault("rounds", []).append(
                {"item": item, "round": rnd, "order": finished, "gained": gained, "t": time.time()})
            save_standings(st)

            res = (f"ROUND OVER ({rnd or item}): "
                   + ", ".join(f"{n}+{gained[n]}" for n in finished)
                   + (" | nobody finished" if not finished else ""))
            print("\n" + res, flush=True)
            print("STANDINGS:", standings_str(st), flush=True)
            _say(rcon, res)
            _say(rcon, "STANDINGS  " + standings_str(st))
    except KeyboardInterrupt:
        print("\n[compete] interrupted — no points awarded for this round.", flush=True)
    finally:
        restore_goal()
        print("[compete] normal goal.txt restored.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
