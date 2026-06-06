"""Diagnose what's making the server lag."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
# Total entity counts + game.speed + sim state
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local total = #s.find_entities_filtered{}; "
    "local belts = #s.find_entities_filtered{name='transport-belt'}; "
    "local ins = #s.find_entities_filtered{name='inserter'}; "
    "local asms = #s.find_entities_filtered{name='assembling-machine-1'}; "
    "local walls = #s.find_entities_filtered{name='stone-wall'}; "
    "local stragglers = #s.find_entities_filtered{name='item-on-ground'}; "
    "rcon.print(string.format("
    "  'game.speed=%.1f tick_paused=%s sim=%s | total=%d belts=%d ins=%d asms=%d walls=%d ground=%d', "
    "  game.speed, tostring(game.tick_paused), tostring(storage.arena and storage.arena.simulating), "
    "  total, belts, ins, asms, walls, stragglers))"
))
r.close()
