"""Spawn a free-standing character for Claude to drive (no player_index).
Gives it a starter kit so basic actions work."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()

# Spawn character at the nauvis spawn point area + give starter inventory
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local force = game.forces.player; "
    # Find a clear spot near 0,0
    "local pos = s.find_non_colliding_position('character', {0, 0}, 20, 0.5); "
    "if not pos then rcon.print('NO SPAWN POSITION'); return end; "
    "local c = s.create_entity{name='character', position=pos, force=force}; "
    "if not (c and c.valid) then rcon.print('SPAWN FAILED'); return end; "
    # Starter kit
    "local inv = c.get_main_inventory(); "
    "if inv then "
    "  inv.insert{name='iron-plate', count=50}; "
    "  inv.insert{name='wood', count=20}; "
    "  inv.insert{name='stone', count=20}; "
    "  inv.insert{name='burner-mining-drill', count=2}; "
    "  inv.insert{name='stone-furnace', count=2}; "
    "  inv.insert{name='wooden-chest', count=5}; "
    "end; "
    "storage.claude_char_unum = c.unit_number; "
    "rcon.print(string.format('CLAUDE spawned at (%.1f,%.1f) unum=%d', "
    "  pos.x, pos.y, c.unit_number))"
))
r.close()
