"""Set inserter direction to north (pickup north=furnace, drop south=chest) + refuel."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "local s = c.surface; "
    "local ci = c.get_main_inventory(); "
    "local i = s.find_entities_filtered{position={-23.5, 93.5}, radius=0.5, name='burner-inserter'}[1]; "
    "if not i then rcon.print('MISSING'); return end; "
    "i.direction = 0; "
    "local fi = i.get_fuel_inventory(); "
    "local have = ci.get_item_count('wood'); "
    "local moved = fi.insert{name='wood', count=math.min(5, have)}; "
    "ci.remove{name='wood', count=moved}; "
    "rcon.print('after: dir=' .. i.direction .. ' fuel_wood=' .. fi.get_item_count('wood') .. ' status=' .. i.status)"
))

time.sleep(8)
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local f = s.find_entities_filtered{position={-24, 92}, radius=0.5, name='stone-furnace'}[1]; "
    "local i = s.find_entities_filtered{position={-23.5, 93.5}, radius=0.5, name='burner-inserter'}[1]; "
    "local ch = s.find_entities_filtered{position={-23.5, 94.5}, radius=0.5, name='wooden-chest'}[1]; "
    "local res = f.get_inventory(defines.inventory.furnace_result); "
    "local chi = ch.get_inventory(defines.inventory.chest); "
    "rcon.print('furnace=' .. res.get_item_count('iron-plate') "
    "  .. ' ins.status=' .. i.status .. ' ins.held=' .. (i.held_stack.valid_for_read and i.held_stack.name or 'none') "
    "  .. ' chest=' .. chi.get_item_count('iron-plate'))"
))
r.close()
