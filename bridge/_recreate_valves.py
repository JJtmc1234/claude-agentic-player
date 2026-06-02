import sys, json
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
# Wipe any existing valves, then place fresh at corners matching the
# original arena bounds (x_min=-20, x_max=-13, y_min=73, y_max=80).
# Valve centers must be at (tile + 0.5) so math.floor gives the tile.
cmd = ("/silent-command "
       "local s = game.surfaces['nauvis']; "
       "for _, v in pairs(s.find_entities_filtered{ type='valve' }) do if v.valid then v.destroy() end end; "
       "local force = game.forces.player; "
       "local v1 = s.create_entity{ name='top-up-valve', position={-19.5, 73.5}, force=force }; "
       "local v2 = s.create_entity{ name='top-up-valve', position={-12.5, 80.5}, force=force }; "
       "rcon.print('v1=' .. tostring(v1 and v1.valid) .. ' v2=' .. tostring(v2 and v2.valid))")
print(r.command(cmd))
print()
print('arena_setup:', json.dumps(call_mod(r, 'arena_setup', interface='claude_rl'), indent=2)[:2000])
r.close()
