"""Check chest plate count after inserter flip."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
for t in range(3):
    print(r.command(
        "/silent-command "
        "local s = game.surfaces['nauvis']; "
        "local f = s.find_entities_filtered{position={-24, 92}, radius=0.5, name='stone-furnace'}[1]; "
        "local i = s.find_entities_filtered{position={-23.5, 93.5}, radius=0.5, name='burner-inserter'}[1]; "
        "local ch = s.find_entities_filtered{position={-23.5, 94.5}, radius=0.5, name='wooden-chest'}[1]; "
        "local msg = 'tick=' .. game.tick; "
        "if f then "
        "  local res = f.get_inventory(defines.inventory.furnace_result); "
        "  msg = msg .. ' fpla=' .. (res and res.get_item_count('iron-plate') or 0); "
        "end; "
        "if i then msg = msg .. ' ins=' .. i.status .. ' dir=' .. i.direction end; "
        "if ch then "
        "  local chi = ch.get_inventory(defines.inventory.chest); "
        "  msg = msg .. ' chpla=' .. (chi and chi.get_item_count('iron-plate') or 0); "
        "end; "
        "rcon.print(msg)"
    ))
    time.sleep(5)
r.close()
