"""
Programmatically add a 2nd input chest + loader for the cable feed,
then re-run arena_setup so the mod picks them up.

Layout target:
  - 2nd steel-chest at (-22.5, 78.5)  (one row south of current input chest)
  - 2nd loader at (-21, 78.5) facing EAST so items flow into arena

After placement, run arena_setup with whichever player is connected
(or fall back to a synthetic dummy via /sc — but arena_setup needs a
real player.surface, so we need at least one player connected).
"""

import json
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod


def main():
    r = RconClient(); r.connect()

    # Get existing arena info via remote (mod context).
    dbg = call_mod(r, 'arena_debug_state', interface='claude_rl')
    if not dbg.get('ok'):
        print(f"arena_debug_state failed: {dbg}")
        r.close()
        return 1
    ld_pos = dbg.get('input_loader')
    if not ld_pos:
        print(f"no input loader in mod storage: {dbg}")
        r.close()
        return 1
    # Now find what TYPE of loader is at that position so we can match.
    cmd = (
        "/silent-command "
        f"local s = game.surfaces['nauvis']; "
        f"local existing = s.find_entities_filtered{{ "
        f"  position = {{ {ld_pos['x']}, {ld_pos['y']} }}, "
        f"  type = {{ 'loader', 'loader-1x1' }}, radius = 1.0 }}[1]; "
        "rcon.print(existing and existing.name or 'none')"
    )
    loader_name = r.command(cmd).strip()
    print(f"existing loader prototype: {loader_name!r}")
    if not loader_name or loader_name == 'none':
        print("[place] couldn't identify existing input loader; aborting")
        r.close()
        return 1

    # Player name optional now (mod 0.9.2 supports nil).
    player = None

    # Place chest + loader at (-22.5, 78.5) and (-21, 78.5).
    # direction=4 is EAST in Factorio 2.0.
    place_cmd = (
        "/silent-command "
        "local s = game.surfaces['nauvis']; "
        "local force = game.forces.player; "
        # Destroy anything already at those positions to avoid collisions.
        "for _, e in pairs(s.find_entities_filtered{ "
        "  area = {{-23, 78}, {-20, 79}}, type = {'container', 'loader', 'loader-1x1'} }) do "
        "  if e.valid then e.destroy() end "
        "end "
        # Place chest first.
        f"local c = s.create_entity{{ name='steel-chest', position={{-22.5, 78.5}}, force=force, raise_built=true }}; "
        # Place loader (east-facing => items flow east into arena).
        f"local l = s.create_entity{{ name='{loader_name}', position={{-21, 78.5}}, force=force, direction=4, raise_built=true }}; "
        "rcon.print('chest=' .. tostring(c and c.valid) .. ' loader=' .. tostring(l and l.valid))"
    )
    res = r.command(place_cmd).strip()
    print(f"placement result: {res}")

    # Now run arena_setup (headless — no player needed in 0.9.2).
    setup = call_mod(r, 'arena_setup', interface='claude_rl')
    print('arena_setup:')
    print(json.dumps(setup, indent=2)[:1500])
    if not setup.get('ok'):
        print("[place] arena_setup failed; manual investigation needed")
        r.close()
        return 3

    # Verify multi-input state.
    state = call_mod(r, 'arena_debug_state', interface='claude_rl')
    print()
    print('input_chests:')
    print(json.dumps(state.get('input_chests'), indent=2))
    print('input_loaders:')
    print(json.dumps(state.get('input_loaders'), indent=2))

    r.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
