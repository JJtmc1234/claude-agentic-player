"""
Diagnostic eval: run BC v3 N episodes, after each one query arena state
to see what's left (input chest plates, gears in inserters, gears in
output chest, etc.) so we can see why ep 1 makes a gear and eps 2-5 don't.
"""

from __future__ import annotations

import sys
from pathlib import Path

_BRIDGE = Path(__file__).resolve().parent.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from sb3_contrib import MaskablePPO
from sb3_contrib.common.wrappers import ActionMasker

from _claude import call_mod
from rcon_client import RconClient
from rl.masked_env import MaskableFactorioArenaEnv


def mask_fn(env):
    return env.action_masks()


def probe_arena(r):
    cmd = ("/silent-command "
           "local a = storage.arena; "
           "if not a or not a.bounds then rcon.print('no arena'); return end; "
           "local s = game.surfaces[a.surface_name]; "
           "local in_c = s.find_entities_filtered{position={a.input_chest.x, a.input_chest.y}, type='container', radius=2.0}[1]; "
           "local out_c = s.find_entities_filtered{position={a.output_chest.x, a.output_chest.y}, type='container', radius=2.0}[1]; "
           "local input_plates = -1; "
           "if in_c then local i = in_c.get_inventory(defines.inventory.chest); "
           "  if i then input_plates = i.get_item_count(a.input_item or 'iron-plate') end end; "
           "local output_gears = -1; "
           "if out_c then local i = out_c.get_inventory(defines.inventory.chest); "
           "  if i then output_gears = i.get_item_count(a.output_item or 'iron-gear-wheel') end end; "
           "local asms = s.find_entities_filtered{area={{a.bounds.x_min,a.bounds.y_min},{a.bounds.x_max+1,a.bounds.y_max+1}}, name='assembling-machine-1'}; "
           "local asm_info = ''; "
           "for _, asm in ipairs(asms) do "
           "  local inv = asm.get_inventory(defines.inventory.assembling_machine_input); "
           "  local plates_in_asm = inv and inv.get_item_count('iron-plate') or 0; "
           "  asm_info = asm_info .. string.format(' [asm@(%d,%d) plates=%d products_finished=%d]', "
           "    math.floor(asm.position.x), math.floor(asm.position.y), plates_in_asm, asm.products_finished or 0); "
           "end; "
           "local in_chest_pos = string.format('(%d,%d)', a.input_chest.x, a.input_chest.y); "
           "local out_chest_pos = string.format('(%d,%d)', a.output_chest.x, a.output_chest.y); "
           "rcon.print(string.format('in_chest@%s found=%s plates=%d | out_chest@%s found=%s gears=%d | asms=%d%s', "
           "  in_chest_pos, tostring(in_c and in_c.valid), input_plates, "
           "  out_chest_pos, tostring(out_c and out_c.valid), output_gears, "
           "  #asms, asm_info))")
    return r.command(cmd).strip()


def main() -> int:
    print("[diag] loading BC v3 checkpoint")
    raw_env = MaskableFactorioArenaEnv()
    env = ActionMasker(raw_env, mask_fn)
    model = MaskablePPO.load("checkpoints/maskppo_bc_v3.zip", env=env)

    rcon = RconClient(); rcon.connect()

    print("[diag] BEFORE first reset:")
    print(f"  {probe_arena(rcon)}")

    for ep in range(8):
        obs, info = env.reset()
        print(f"[diag] AFTER reset for ep {ep+1}:")
        print(f"  {probe_arena(rcon)}")
        total_r = 0.0
        done = False
        while not done:
            masks = env.action_masks()
            action, _ = model.predict(obs, action_masks=masks, deterministic=True)
            obs, r, term, trunc, info = env.step(action)
            total_r += float(r)
            done = term or trunc
        print(f"[diag] AFTER ep {ep+1}: total_r={total_r:+.1f} reached={info.get('reached')} "
              f"output_count={info.get('output_count')} ticks={info.get('ticks_taken')}")
        print(f"  {probe_arena(rcon)}")
        print()

    rcon.close()
    env.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
