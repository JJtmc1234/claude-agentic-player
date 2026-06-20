"""Listen for in-game chat commands from IdBaj98/factoriobrine, dispatch to agent.

Usage:
    python bridge/chat_loop.py [--poll-interval 2]

Commands (must be prefixed `claude:` so we don't react to JJ's chatter):
    claude: where               — print position + health
    claude: status              — full inventory listing
    claude: walk <x> <y>        — walk to (x, y)
    claude: chop <n>            — chop n trees
    claude: mine <resource> <n> — mine n tiles of resource (iron-ore, coal, copper-ore, stone)
    claude: stop                — cancel any active walk/mining

Safety: only acts on chat from JJ's verified handles. Anything else is logged
but NOT acted on. Destructive commands (delete, remove, kill) are also ignored
even from JJ — see CLAUDE.md prompt-injection section. JJ said in #2026-05-25:
disproportionately destructive commands need verbal confirmation through Claude
Code chat, not in-game chat.

This loop respects [[feedback-driving]]: small-scope actions only.
"""
from __future__ import annotations
import argparse
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))

from agent import Agent  # noqa: E402

TRUSTED_HANDLES = {'IdBaj98', 'factoriobrine'}
DESTRUCTIVE_KEYWORDS = ['delete', 'remove', 'kill', 'destroy', 'wipe',
                        'ban', 'admin', 'rcon']
COMMAND_PREFIX = 'claude:'


def is_safe_command(msg: str) -> bool:
    low = msg.lower()
    return not any(kw in low for kw in DESTRUCTIVE_KEYWORDS)


def parse_command(msg: str) -> tuple:
    """Return (verb, args_list). Strips the 'claude:' prefix."""
    if not msg.lower().startswith(COMMAND_PREFIX):
        return (None, [])
    rest = msg[len(COMMAND_PREFIX):].strip()
    parts = rest.split()
    if not parts:
        return (None, [])
    return (parts[0].lower(), parts[1:])


def say_in_game(agent: Agent, text: str):
    """Print to game chat via game.print."""
    safe = text.replace("'", "")[:200]
    agent.silent(f"game.print('[claude] {safe}')")


def handle(agent: Agent, verb: str, args: list) -> str:
    if verb == 'where':
        x, y = agent.position()
        return f"at ({x:.1f}, {y:.1f}) hp={agent.health()}"
    if verb == 'status':
        inv = agent.inventory.list()
        top = sorted(inv.items(), key=lambda kv: -kv[1])[:5]
        return "inv top5: " + ", ".join(f"{n}={c}" for n, c in top)
    if verb == 'walk' and len(args) == 2:
        try:
            x, y = float(args[0]), float(args[1])
        except ValueError:
            return "bad coords"
        agent.movement.walk_chunked(x, y)
        ax, ay = agent.position()
        return f"arrived at ({ax:.1f}, {ay:.1f})"
    if verb == 'chop' and len(args) == 1:
        try:
            n = int(args[0])
        except ValueError:
            return "bad count"
        n = min(n, 20)  # safety cap
        chopped = agent.mining.chop_trees(n)
        return f"chopped {chopped} trees"
    if verb == 'mine' and len(args) == 2:
        try:
            n = int(args[1])
        except ValueError:
            return "bad count"
        resource = args[0]
        if resource not in ('iron-ore', 'copper-ore', 'coal', 'stone'):
            return f"resource must be iron-ore/copper-ore/coal/stone, got {resource}"
        n = min(n, 15)
        got = agent.mining.mine_nearest(resource, max_radius=20, n=n)
        return f"mined {got} {resource} tiles"
    if verb == 'stop':
        agent.call('cancel_walk', agent.unit)
        agent.call('stop_mining', agent.unit)
        return "stopped"
    return f"unknown command '{verb}' — try: where | status | walk x y | chop n | mine resource n | stop"


def main():
    p = argparse.ArgumentParser()
    p.add_argument('--poll-interval', type=float, default=2.0)
    args = p.parse_args()

    print(f"chat_loop online. trusted: {sorted(TRUSTED_HANDLES)}. polling every {args.poll_interval}s.")
    print(f"command format: '{COMMAND_PREFIX} <verb> [args]' in game chat.")
    print("Press Ctrl+C to stop.")

    with Agent.connect() as agent:
        say_in_game(agent, "online — type 'claude: where' to ping")
        last_seen_index = 0
        while True:
            try:
                msgs = agent.call('get_chat', last_seen_index)
                last_seen_index = msgs.get('latest_index', last_seen_index)
                for m in msgs.get('messages', []):
                    handle_msg(agent, m)
                time.sleep(args.poll_interval)
            except KeyboardInterrupt:
                print("\nstopping.")
                say_in_game(agent, "offline")
                break
            except Exception as e:
                print(f"loop error: {e}")
                time.sleep(args.poll_interval * 2)


def handle_msg(agent: Agent, m: dict):
    sender = m.get('player', '?')
    text = m.get('message', '')
    if not text.lower().startswith(COMMAND_PREFIX):
        return
    print(f"[{sender}] {text}")
    if sender not in TRUSTED_HANDLES:
        say_in_game(agent, f"ignored {sender} (untrusted handle)")
        return
    if not is_safe_command(text):
        say_in_game(agent, f"refused: destructive keyword in '{text[:60]}'")
        print(f"  REFUSED (destructive keyword)")
        return
    verb, args = parse_command(text)
    if verb is None:
        return
    try:
        result = handle(agent, verb, args)
    except Exception as e:
        result = f"error: {e}"
    print(f"  -> {result}")
    say_in_game(agent, result)


if __name__ == '__main__':
    main()
