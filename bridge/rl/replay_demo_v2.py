"""
Same as replay_demo_8x8.py but for the V2 layout (asm shifted right).
Tells us whether the V2 demo actually produces gears before we use it
in multi-demo BC training.
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
from rl.demonstration_8x8_v2 import as_actions


def main() -> int:
    r = RconClient(); r.connect()

    print("[replay-v2] arena_reset ...")
    print(f"  {call_mod(r, 'arena_reset', interface='claude_rl')}")

    print("[replay-v2] applying demo v2 actions ...")
    for i, action in enumerate(as_actions(), 1):
        ec, ti, d = action
        res = call_mod(r, 'arena_place', ec, ti, d, interface='claude_rl')
        ok = res.get('ok')
        tag = 'ok' if ok else f"FAIL {res.get('error')}"
        bonus = res.get('chain_bonus', 0)
        print(f"  action {i}: ent={ec} tile={ti:3d} dir={d} -> {tag} (chain_bonus={bonus})")

    print()
    print("[replay-v2] arena_start_simulate ...")
    print(f"  {call_mod(r, 'arena_start_simulate', 1800, interface='claude_rl')}")

    print("[replay-v2] polling ...")
    for poll in range(40):
        time.sleep(0.2)
        st = call_mod(r, 'arena_get_sim_status', interface='claude_rl')
        dbg = call_mod(r, 'arena_debug_state', interface='claude_rl')
        in_chest = dbg.get('input_chest', {}).get('contents') or []
        in_count = sum(c.get('count', 0) for c in in_chest) if isinstance(in_chest, list) else 0
        out_chest = dbg.get('output_chest', {}).get('contents') or []
        out_count = sum(c.get('count', 0) for c in out_chest) if isinstance(out_chest, list) else 0
        n_asm = dbg.get('n_assemblers', 0)
        print(f"  poll {poll:2d} sim={st.get('simulating')} plates={in_count} gears={out_count} n_asm={n_asm}")
        if not st.get('simulating'):
            print("[replay-v2] sim ended")
            break

    score = call_mod(r, 'arena_score', interface='claude_rl')
    print()
    print(f"[replay-v2] total={score.get('total')} reached={score.get('reached')} output={score.get('output_count')}")
    r.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
