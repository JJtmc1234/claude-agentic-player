"""Fuel the drill + furnace at their actual placed positions.
The helper picks the first inventory-having entity at a position, so for the
drill (placed on iron ore) we need to disambiguate: search by ENTITY NAME."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Refactor: instead of going through the inventory helper, do it directly so we
# can pick the entity by NAME. Drill at (-24, 90), furnace at (-24, 92).
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "local s = c.surface; "
    "local char_inv = c.get_main_inventory(); "
    "local function fuel(name, x, y, want) "
    "  local e = s.find_entities_filtered{position={x,y}, radius=0.6, name=name}[1]; "
    "  if not e then return name .. '@(' .. x .. ',' .. y .. '): NOT FOUND' end; "
    "  local fi = e.get_fuel_inventory(); "
    "  if not fi then return name .. ': no fuel inventory' end; "
    "  local have = char_inv.get_item_count('wood'); "
    "  local n = math.min(want, have); "
    "  local moved = fi.insert{name='wood', count=n}; "
    "  if moved > 0 then char_inv.remove{name='wood', count=moved} end; "
    "  return name .. ': fuelled +' .. moved .. ' wood' "
    "end; "
    "rcon.print(fuel('burner-mining-drill', -24, 90, 5)); "
    "rcon.print(fuel('stone-furnace', -24, 92, 5))"
))

# Wait then check
time.sleep(8)
print("\nstatus after 8s:")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local d = s.find_entities_filtered{position={-24, 90}, radius=0.5, name='burner-mining-drill'}[1]; "
    "local f = s.find_entities_filtered{position={-24, 92}, radius=0.5, name='stone-furnace'}[1]; "
    "local msg = ''; "
    "if d then "
    "  local fuel = d.get_fuel_inventory(); "
    "  msg = msg .. 'drill: ' .. d.status .. ' fuel_wood=' .. (fuel and fuel.get_item_count('wood') or 0); "
    "end; "
    "if f then "
    "  local fuel = f.get_fuel_inventory(); "
    "  local src = f.get_inventory(defines.inventory.furnace_source); "
    "  local res = f.get_inventory(defines.inventory.furnace_result); "
    "  msg = msg .. ' | furnace: ' .. f.status "
    "    .. ' fuel_wood=' .. (fuel and fuel.get_item_count('wood') or 0) "
    "    .. ' ore=' .. (src and src.get_item_count('iron-ore') or 0) "
    "    .. ' plates=' .. (res and res.get_item_count('iron-plate') or 0); "
    "end; "
    "rcon.print(msg)"
))
r.close()
