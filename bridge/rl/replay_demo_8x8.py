"""
Replay the 8x8 hand-built demo and probe what actually happens during sim.
The whole BC-warm-start strategy hinges on this layout producing gears.

Steps:
  1. arena_reset (clear arena, refill input chest).
  2. Apply each demo action via arena_place.
  3. arena_start_simulate.
  4. Every 100 ticks during sim, probe arena_debug_state and print:
     - input chest plate count
     - output chest gear count
     - active assemblers' crafting progress + products_finished + inventory
  5. After sim, print the final arena_score.

Tells us: does the demo actually produce gears? If yes, why didn't BC v3 inherit
that behavior? If no, where does the chain break (no plates flowing? assembler
not crafting? gears stuck on belt?).

Run:
    python bridge/rl/replay_demo_8x8.py
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
from rl.demonstration_8x8 import as_actions


def main() -> int:
    r = RconClient(); r.connect()

    print("[replay] arena_reset ...")
    res = call_mod(r, 'arena_reset', interface='claude_rl')
    print(f"  {res}")

    print("[replay] applying demo actions ...")
    for i, action in enumerate(as_actions(), 1):
        ec, ti, d = action
        res = call_mod(r, 'arena_place', ec, ti, d, interface='claude_rl')
        ok = res.get('ok')
        tag = 'ok' if ok else f"FAIL {res.get('error')}"
        bonus = res.get('chain_bonus', 0)
        print(f"  action {i}: ent={ec} tile={ti:3d} dir={d} -> {tag} (chain_bonus={bonus})")

    print()
    print("[replay] arena_start_simulate ...")
    res = call_mod(r, 'arena_start_simulate', 900, interface='claude_rl')
    print(f"  {res}")

    # Poll + probe.
    print("[replay] polling sim + probing arena every ~0.2s wall ...")
    for poll in range(40):
        time.sleep(0.2)
        st = call_mod(r, 'arena_get_sim_status', interface='claude_rl')
        dbg = call_mod(r, 'arena_debug_state', interface='claude_rl')
        in_count = (dbg.get('input_chest', {}).get('contents') or [])
        in_count = sum(c.get('count', 0) for c in in_count) if isinstance(in_count, list) else 0
        out_count = (dbg.get('output_chest', {}).get('contents') or [])
        out_count = sum(c.get('count', 0) for c in out_count) if isinstance(out_count, list) else 0
        n_asm = dbg.get('n_assemblers', 0)
        asm_info = ""
        for asm in (dbg.get('assemblers') or []):
            pf = asm.get('products_finished', 0)
            cp = asm.get('crafting_progress', 0)
            inv_in = asm.get('input', {})
            inv_out = asm.get('output', {})
            def fmt_inv(inv):
                if isinstance(inv, list):
                    return ','.join(f"{c.get('name')}={c.get('count')}" for c in inv) or 'empty'
                if isinstance(inv, dict) and inv:
                    return ','.join(f"{k}={v}" for k, v in inv.items())
                return 'empty'
            asm_info += f" [pf={pf} cp={cp:.2f} in:{fmt_inv(inv_in)} out:{fmt_inv(inv_out)}]"
        print(f"  poll {poll:2d} sim={st.get('simulating')} ticks={st.get('elapsed_ticks')} "
              f"in_chest_plates={in_count} out_chest_gears={out_count} n_asm={n_asm}{asm_info}")
        if not st.get('simulating'):
            print("[replay] sim ended")
            break

    print()
    print("[replay] arena_score ...")
    score = call_mod(r, 'arena_score', interface='claude_rl')
    print(f"  total={score.get('total')}")
    print(f"  reached={score.get('reached')} output_count={score.get('output_count')}")
    components = score.get('components') or {}
    for k in sorted(components.keys()):
        v = components[k]
        if isinstance(v, (int, float)) and v != 0:
            print(f"    {k}: {v}")

    r.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
