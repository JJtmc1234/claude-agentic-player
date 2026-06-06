"""Replay the multi-product circuit demo and probe whether it actually
produces circuits via the cable->circuit chain."""

from __future__ import annotations

import sys
import time
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from _claude import call_mod
from rcon_client import RconClient
from rl.demonstration_circuits_16x16_mastery import as_actions


def main() -> int:
    r = RconClient(); r.connect()

    spec = {
        'recipe_name': 'electronic-circuit',
        'recipe_options': ['copper-cable', 'electronic-circuit'],
        'output_item': 'electronic-circuit',
        'target_output': 20,
        'input_items': [
            {'name': 'iron-plate', 'count': 30},
            {'name': 'copper-plate', 'count': 60},
        ],
        'sim_max_ticks': 3600,
    }
    print('[mastery] set_task:', call_mod(r, 'arena_set_task', spec, interface='claude_rl').get('ok'))
    print('[mastery] reset:', call_mod(r, 'arena_reset', interface='claude_rl'))

    for i, action in enumerate(as_actions(), 1):
        ec, ti, d = action
        res = call_mod(r, 'arena_place', ec, ti, d, interface='claude_rl')
        ok = res.get('ok')
        tag = 'ok' if ok else f"FAIL {res.get('error')}"
        bonus = res.get('chain_bonus', 0)
        print(f"  {i:2d}: ent={ec} tile={ti:3d} dir={d} -> {tag} bonus={bonus}")

    print()
    print('[mastery] arena_start_simulate (3600 ticks) ...')
    print(f"  {call_mod(r, 'arena_start_simulate', 3600, interface='claude_rl')}")

    print('[mastery] polling ...')
    for poll in range(50):
        time.sleep(0.3)
        st = call_mod(r, 'arena_get_sim_status', interface='claude_rl')
        dbg = call_mod(r, 'arena_debug_state', interface='claude_rl')
        out_contents = dbg.get('output_chest', {}).get('contents') or []
        circuits = sum(c.get('count', 0) for c in out_contents if c.get('name') == 'electronic-circuit') if isinstance(out_contents, list) else 0
        n_asm = dbg.get('n_assemblers', 0)
        asm_info = ''
        for asm in dbg.get('assemblers') or []:
            pf = asm.get('products_finished', 0)
            cp = asm.get('crafting_progress', 0)
            rec = asm.get('recipe', '?')
            asm_info += f" [{rec[:7]} pf={pf} cp={cp:.2f}]"
        print(f"  poll {poll:2d} sim={st.get('simulating')} circuits={circuits} n_asm={n_asm}{asm_info}")
        if not st.get('simulating'):
            break

    score = call_mod(r, 'arena_score', interface='claude_rl')
    print()
    print(f"[mastery] total={score.get('total')} reached={score.get('reached')} output={score.get('output_count')}")
    r.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
