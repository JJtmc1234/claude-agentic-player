"""
Replay the 2-input circuit demo. Confirms the chain actually produces
circuits before we BC-train on it.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from _claude import call_mod
from rcon_client import RconClient
from rl.demonstration_circuits_8x8 import as_actions


def main() -> int:
    r = RconClient(); r.connect()

    # Make sure task is circuits.
    spec = {
        'recipe_name': 'electronic-circuit',
        'output_item': 'electronic-circuit',
        'target_output': 10,
        'input_items': [
            {'name': 'iron-plate', 'count': 20},
            {'name': 'copper-cable', 'count': 60},
        ],
        'sim_max_ticks': 1800,
    }
    print('[replay-circ] set_task:', call_mod(r, 'arena_set_task', spec, interface='claude_rl'))
    print('[replay-circ] reset:', call_mod(r, 'arena_reset', interface='claude_rl'))

    print('[replay-circ] applying demo actions ...')
    for i, action in enumerate(as_actions(), 1):
        ec, ti, d = action
        res = call_mod(r, 'arena_place', ec, ti, d, interface='claude_rl')
        ok = res.get('ok')
        tag = 'ok' if ok else f"FAIL {res.get('error')}"
        bonus = res.get('chain_bonus', 0)
        print(f"  action {i}: ent={ec} tile={ti:3d} dir={d} -> {tag} (chain_bonus={bonus})")

    print()
    print('[replay-circ] arena_start_simulate (1800 ticks) ...')
    print(f"  {call_mod(r, 'arena_start_simulate', 1800, interface='claude_rl')}")

    print('[replay-circ] polling ...')
    for poll in range(40):
        time.sleep(0.2)
        st = call_mod(r, 'arena_get_sim_status', interface='claude_rl')
        dbg = call_mod(r, 'arena_debug_state', interface='claude_rl')
        out_count = dbg.get('output_chest', {}).get('contents') or []
        if isinstance(out_count, list):
            circuits = sum(c.get('count', 0) for c in out_count if c.get('name') == 'electronic-circuit')
        else:
            circuits = 0
        n_asm = dbg.get('n_assemblers', 0)
        asm_info = ''
        for asm in dbg.get('assemblers') or []:
            pf = asm.get('products_finished', 0)
            cp = asm.get('crafting_progress', 0)
            inv_in = asm.get('input', [])
            inv_in_str = ','.join(f"{c.get('name')}={c.get('count')}" for c in inv_in) if isinstance(inv_in, list) and inv_in else 'empty'
            asm_info += f" [pf={pf} cp={cp:.2f} in:{inv_in_str}]"
        print(f"  poll {poll:2d} sim={st.get('simulating')} circuits={circuits} n_asm={n_asm}{asm_info}")
        if not st.get('simulating'):
            print('[replay-circ] sim ended')
            break

    score = call_mod(r, 'arena_score', interface='claude_rl')
    print()
    print(f"[replay-circ] total={score.get('total')} reached={score.get('reached')} output_count={score.get('output_count')}")
    components = score.get('components') or {}
    for k in sorted(components.keys()):
        v = components[k]
        if isinstance(v, (int, float)) and v != 0:
            print(f"    {k}: {v}")
    r.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
