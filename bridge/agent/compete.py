"""
compete.py — Agent Competition referee + live scoreboard.

Turns the 4-agent BRAIN team into a spectator sport. It:
  1. Sets a shared CHALLENGE (be first to produce N of an item).
  2. Biases every BRAIN toward it by rewriting goal.txt with a RACE directive (each brain
     reads goal.txt every cycle as its standing mission — no brain-code change needed).
  3. Scores each contestant over RCON (item held in their own inventory) and renders a live
     leaderboard in the terminal AND to in-game chat, so JJ can watch the race unfold in-game.
  4. Declares a winner and restores the normal goal.txt when the race ends.

Score = target item each agent has PRODUCED since the race started (current inventory count
minus their starting count, clamped >= 0). The race directive tells them to HOLD the item on
their character (not deposit / share / consume it), which is what makes the count attributable.

Run:
    python bridge/agent/compete.py --item electronic-circuit --goal 50
    python bridge/agent/compete.py --item iron-gear-wheel --goal 100 --secs 600
    python bridge/agent/compete.py --restore      # just put the normal goal.txt back

Stop anytime with Ctrl-C — it restores goal.txt and posts the final standings.
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
_GOAL_FILE = _HERE / "goal.txt"
_BACKUP_FILE = _HERE / "goal.race-backup.txt"
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
# scoring — one batched RCON read for all contestants
#
# Each BRAIN saves the unit_number of the character it drives to state/<name>.unum and
# rewrites it on respawn, so that file is the authoritative "which char is <name>". (The mod's
# list_chars registry is only populated when a brain spawns via spawn_named_char; brains that
# reuse a saved unum never register there, so list_chars can't be trusted for scoring.)
# ---------------------------------------------------------------------------
def _read_unums() -> dict:
    """Return {name: unum} for each contestant that has a saved unum file."""
    out = {}
    for n in CONTESTANTS:
        f = _HERE / "state" / f"{n}.unum"
        try:
            s = f.read_text(encoding="utf-8").strip()
            if s.isdigit():
                out[n] = int(s)
        except Exception:  # noqa: BLE001
            pass
    return out


def _scores_lua(item: str, unums: dict) -> str:
    m = "{" + ",".join(f"{n}={u}" for n, u in unums.items()) + "}"
    return (
        "local item='" + item + "'; local m=" + m + "; local out={};"
        "for nm,u in pairs(m) do local n=-1;"
        "  local c=game.get_entity_by_unit_number(u);"
        "  if c and c.valid then local inv=c.get_main_inventory();"
        "    n = inv and inv.get_item_count(item) or 0 end;"
        "  out[nm]=n end;"
        "rcon.print(helpers.table_to_json(out))"
    )


def read_counts(rcon: RconClient, item: str) -> dict:
    """Return {name: held_count}; -1 means that contestant has no live character."""
    unums = _read_unums()
    result = {n: -1 for n in CONTESTANTS}
    if not unums:
        return result
    try:
        out = rcon.command("/silent-command " + _scores_lua(item, unums)).strip()
        data = json.loads(out)
        for n in CONTESTANTS:
            result[n] = int(data.get(n, -1))
    except Exception:  # noqa: BLE001
        pass
    return result


# ---------------------------------------------------------------------------
# goal.txt swap (the race directive the brains read each cycle)
# ---------------------------------------------------------------------------
def _race_directive(item: str, goal: int) -> str:
    return (
        "*** AGENT COMPETITION — THIS IS A RACE (overrides your normal role) ***\n"
        "There is a live contest between the four of you (miner, courier, builder, scout).\n"
        f"CHALLENGE: be the FIRST to have {goal} x {item} in YOUR OWN character inventory.\n\n"
        "RULES OF THE RACE:\n"
        f"- Your score = how many {item} you are currently HOLDING (main inventory). Make/obtain\n"
        f"  {item} as fast as you can and KEEP them on you. Do NOT deposit them in chests, do NOT\n"
        "  hand them to teammates, do NOT consume them.\n"
        "- This is COMPETITIVE: do NOT help teammates and do NOT split the work to share — RACE\n"
        "  them. Grab raw materials from the base (belts/chests), mine, craft intermediates, and\n"
        f"  craft {item} yourself. Build an assembler for it if that's faster. Whatever wins.\n"
        f"- Verify the real recipe live (this is a K2 Spaced Out modpack, not vanilla) and only\n"
        "  build unlocked recipes. Never spawn items — craft/produce them for real.\n"
        "- JJ STILL COMES FIRST: if JJ pings or asks you something, help him, then resume racing.\n"
        "- A little trash talk to JJ is fine, but keep chat minimal — don't spam.\n"
        f"FIRST TO {goal} WINS. GO!\n"
    )


def start_race(item: str, goal: int) -> None:
    if not _BACKUP_FILE.exists():        # preserve the REAL goal only once (repeat starts are safe)
        try:
            _BACKUP_FILE.write_text(_GOAL_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        except FileNotFoundError:
            _BACKUP_FILE.write_text("", encoding="utf-8")
    _GOAL_FILE.write_text(_race_directive(item, goal), encoding="utf-8")


def restore_goal() -> bool:
    """Put the pre-race goal.txt back. Returns True if a backup was restored."""
    if _BACKUP_FILE.exists():
        _GOAL_FILE.write_text(_BACKUP_FILE.read_text(encoding="utf-8"), encoding="utf-8")
        _BACKUP_FILE.unlink()
        return True
    return False


# ---------------------------------------------------------------------------
# leaderboard rendering
# ---------------------------------------------------------------------------
def _bar(score: int, goal: int, width: int = 24) -> str:
    filled = 0 if goal <= 0 else max(0, min(width, round(width * score / goal)))
    return "#" * filled + "-" * (width - filled)


def render(scores: dict, goal: int, item: str, elapsed: float) -> str:
    rows = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    lead = rows[0][1] if rows else 0
    lines = [
        f"CHALLENGE: first to {goal} x {item}     elapsed {int(elapsed)}s",
        "-" * 52,
    ]
    for i, (name, sc) in enumerate(rows):
        tag = " <-- LEAD" if sc == lead and sc > 0 else ""
        shown = f"{sc:>4}" if sc >= 0 else "  --"   # -- = no character
        lines.append(f"{i+1}. {name:<8} {shown}  {_bar(max(sc,0), goal)}{tag}")
    lines.append("-" * 52)
    return "\n".join(lines)


def scoreboard_chat(scores: dict) -> str:
    rows = sorted(scores.items(), key=lambda kv: kv[1], reverse=True)
    return "  |  ".join(f"{n}:{s if s >= 0 else '-'}" for n, s in rows)


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Agent competition referee + live scoreboard")
    ap.add_argument("--item", default="electronic-circuit", help="target item to race for")
    ap.add_argument("--goal", type=int, default=50, help="count needed to win")
    ap.add_argument("--secs", type=int, default=0, help="optional time cap (0 = until someone wins)")
    ap.add_argument("--poll", type=float, default=3.0, help="seconds between score reads")
    ap.add_argument("--chat-every", type=float, default=20.0, help="seconds between in-game score posts")
    ap.add_argument("--restore", action="store_true", help="just restore the normal goal.txt and exit")
    args = ap.parse_args()

    os.environ.setdefault("FACTORIO_RCON_PASSWORD", _resolve_rcon_password())

    if args.restore:
        print("restored normal goal.txt" if restore_goal() else "no race backup to restore")
        return 0

    item = _safe(args.item)
    goal = max(1, args.goal)
    is_tty = sys.stdout.isatty()

    start_race(item, goal)
    print(f"[compete] race started: first to {goal} x {item}. goal.txt swapped (backup saved).",
          flush=True)

    baseline: dict = {}
    last_chat = 0.0
    last_lead = None
    winner = None
    t0 = time.time()

    try:
        with RconClient() as rcon:
            _say(rcon, f"CHALLENGE! First to {goal} {item} wins. "
                       f"{' vs '.join(CONTESTANTS)} -- GO!")
            while True:
                raw = read_counts(rcon, item)
                for n, c in raw.items():                 # set baseline on first real read per name
                    if c >= 0 and n not in baseline:
                        baseline[n] = c
                scores = {n: max(0, raw[n] - baseline.get(n, 0)) if raw[n] >= 0 else -1
                          for n in CONTESTANTS}
                elapsed = time.time() - t0

                board = render(scores, goal, item, elapsed)
                if is_tty:
                    os.system("cls" if os.name == "nt" else "clear")
                    print(board, flush=True)
                else:
                    print("\n" + board, flush=True)

                # winner?
                topped = [n for n in CONTESTANTS if scores[n] >= goal]
                if topped:
                    winner = max(topped, key=lambda n: scores[n])
                    break
                if args.secs and elapsed >= args.secs:
                    winner = max(CONTESTANTS, key=lambda n: scores[n])
                    break

                # periodic in-game feed + lead-change callouts
                now = time.time()
                lead_name = max(CONTESTANTS, key=lambda n: scores[n])
                if scores[lead_name] > 0 and lead_name != last_lead:
                    _say(rcon, f"{lead_name} takes the lead! ({scoreboard_chat(scores)})")
                    last_lead = lead_name
                    last_chat = now
                elif now - last_chat >= args.chat_every:
                    _say(rcon, scoreboard_chat(scores))
                    last_chat = now

                time.sleep(args.poll)

            final = f"WINNER: {winner} -- {scores[winner]} {item}! Final: {scoreboard_chat(scores)}"
            print("\n" + final, flush=True)
            _say(rcon, final + " GG.")
    except KeyboardInterrupt:
        print("\n[compete] interrupted.", flush=True)
    finally:
        restore_goal()
        print("[compete] normal goal.txt restored; team back to standing mission.", flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
