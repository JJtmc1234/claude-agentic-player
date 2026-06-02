"""Replay the 2nd circuit demo (asm shifted +1) to verify it works."""

from __future__ import annotations

import sys
import time
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from _claude import call_mod
from rcon_client import RconClient
from rl.demonstration_circuits_8x8_v2 import as_actions


def main() -> int:
    r = RconClient(); r.connect()
    spec = {
        'recipe_name': 'electronic-circuit',
        'output_item': 'electronic-circuit',
        'target_output': 10,
        'input_items': [
            {'name': 'iron-plate', 'count': 20},
            {'name': 'copper-cable', 'count': 60},
        ],
        'sim_max_ticks': 3600,
    }
    print('set_task:', call_mod(r, 'arena_set_task', spec, interface='claude_rl'))
    print('reset:', call_mod(r, 'arena_reset', interface='claude_rl'))
    for i, action in enumerate(as_actions(), 1):
        ec, ti, d = action
        res = call_mod(r, 'arena_place', ec, ti, d, interface='claude_rl')
        tag = 'ok' if res.get('ok') else f"FAIL {res.get('error')}"
        print(f"  {i}: ent={ec} tile={ti:3d} dir={d} -> {tag} bonus={res.get('chain_bonus', 0)}")
    print('start:', call_mod(r, 'arena_start_simulate', 3600, interface='claude_rl'))
    for poll in range(60):
        time.sleep(0.2)
        st = call_mod(r, 'arena_get_sim_status', interface='claude_rl')
        dbg = call_mod(r, 'arena_debug_state', interface='claude_rl')
        contents = dbg.get('output_chest', {}).get('contents') or []
        circs = sum(c.get('count', 0) for c in contents if c.get('name') == 'electronic-circuit') if isinstance(contents, list) else 0
        print(f"  poll {poll:2d} sim={st.get('simulating')} circuits={circs}")
        if not st.get('simulating'):
            break
    score = call_mod(r, 'arena_score', interface='claude_rl')
    print(f"total={score.get('total')} reached={score.get('reached')} output={score.get('output_count')}")
    r.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
