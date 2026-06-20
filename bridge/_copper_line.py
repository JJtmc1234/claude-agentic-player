"""Walk back to base, build a copper smelting line beside the iron one.
Plan:
  - Walk to (-12, 51) (a bit east of iron line)
  - Place spare furnace at (-11, 52)
  - Place chest at (-11, 55)
  - Place inserter at (-11, 54) facing NORTH (picks from furnace, drops south)
  - Hand-load furnace with copper ore + coal fuel
  - Wait, check plates
"""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Walk back near base
print("=== walking back to base region ===")
res = call_mod(r, 'walk_to', unum, -10, 51, 2.0)
print(f"  start: {res}")
for i in range(120):
    time.sleep(1)
    st = call_mod(r, 'get_walk_status', unum)
    if i % 10 == 0 or st.get('status') != 'walking':
        print(f"  t={i}s {st.get('status')} wp={st.get('current_index')}/{st.get('total_waypoints')}")
    if st.get('status') in ('completed', 'error', 'idle'): break
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d', c.position.x, c.position.y, c.health))"
))

# Craft 1 inserter (gear+iron in inv check)
print("\n=== crafting 1 iron-gear + 1 burner-inserter ===")
call_mod(r, 'craft', unum, 'iron-gear-wheel', 1)
while True:
    time.sleep(1)
    if call_mod(r, 'get_craft_status', unum).get('status') != 'crafting': break
call_mod(r, 'craft', unum, 'burner-inserter', 1)
while True:
    time.sleep(1)
    if call_mod(r, 'get_craft_status', unum).get('status') != 'crafting': break

# Place furnace at (-11, 52), inserter at (-11, 54) dir=N, chest at (-11, 55)
print("\n=== placing copper smelter ===")
furn = call_mod(r, 'place_entity', unum, 'stone-furnace', -11, 52, 0)
print(f"  furn: {furn}")
ins = call_mod(r, 'place_entity', unum, 'burner-inserter', -11, 54, 0)
print(f"  ins:  {ins}")
chest = call_mod(r, 'place_entity', unum, 'wooden-chest', -11, 55, 0)
print(f"  chest: {chest}")

# Fuel + load via name lookup (use unums where possible)
fx, fy = furn['position']['x'], furn['position']['y']
ix, iy = ins['position']['x'], ins['position']['y']
cx, cy = chest['position']['x'], chest['position']['y']

print("\n=== loading furnace with copper-ore + coal fuel ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    f"local f = s.find_entities_filtered{{position={{{fx},{fy}}}, radius=0.5, name='stone-furnace'}}[1]; "
    f"local ins = s.find_entities_filtered{{position={{{ix},{iy}}}, radius=0.5, name='burner-inserter'}}[1]; "
    "if not f then rcon.print('NO furnace'); return end; "
    # Load copper-ore into furnace source slot
    "local src = f.get_inventory(defines.inventory.furnace_source); "
    "local have_ore = ci.get_item_count('copper-ore'); "
    "local moved_ore = src.insert{name='copper-ore', count=have_ore}; "
    "ci.remove{name='copper-ore', count=moved_ore}; "
    # Fuel furnace with coal
    "local fi = f.get_fuel_inventory(); "
    "local have_coal = ci.get_item_count('coal'); "
    "local moved_coal = fi.insert{name='coal', count=math.min(3, have_coal)}; "
    "ci.remove{name='coal', count=moved_coal}; "
    # Fuel inserter with coal
    "if ins then "
    "  local ifi = ins.get_fuel_inventory(); "
    "  local have_coal2 = ci.get_item_count('coal'); "
    "  local m2 = ifi.insert{name='coal', count=math.min(1, have_coal2)}; "
    "  ci.remove{name='coal', count=m2}; "
    "  rcon.print('inserter +' .. m2 .. ' coal dir=' .. ins.direction) "
    "end; "
    "rcon.print('furnace +' .. moved_ore .. ' copper-ore, +' .. moved_coal .. ' coal')"
))

time.sleep(15)
print("\n=== status after 15s ===")
print(r.command(
    "/silent-command "
    f"local s = game.surfaces['nauvis']; "
    f"local f = s.find_entities_filtered{{position={{{fx},{fy}}}, radius=0.5, name='stone-furnace'}}[1]; "
    f"local ch = s.find_entities_filtered{{position={{{cx},{cy}}}, radius=0.5, name='wooden-chest'}}[1]; "
    "local res = f and f.get_inventory(defines.inventory.furnace_result); "
    "local src = f and f.get_inventory(defines.inventory.furnace_source); "
    "local chi = ch and ch.get_inventory(defines.inventory.chest); "
    "rcon.print(string.format('furnace status=%s src_ore=%d output_plates=%d chest_plates=%d', "
    "  f and f.status or '?', "
    "  src and src.get_item_count('copper-ore') or 0, "
    "  res and res.get_item_count('copper-plate') or 0, "
    "  chi and chi.get_item_count('copper-plate') or 0))"
))

# Also check iron chest while at it
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local ich = s.find_entities_filtered{position={-13.5, 55.5}, radius=0.5, name='wooden-chest'}[1]; "
    "local chi = ich and ich.get_inventory(defines.inventory.chest); "
    "rcon.print('iron_chest_plates=' .. (chi and chi.get_item_count('iron-plate') or 0))"
))
r.close()
