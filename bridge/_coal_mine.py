"""Walk to coal patch, place drill + chest, fuel drill with wood.
Coal drops directly into the chest at drop position (no inserter needed
if chest aligns with drill drop tile)."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# 1. Walk to coal (-56.5, 91.5), goal radius 3 so we land in placement reach
print("walking to coal...")
res = call_mod(r, 'walk_to', unum, -56.5, 91.5, 3.0)
print(f"  initial: {res}")
for i in range(120):
    time.sleep(1.0)
    st = call_mod(r, 'get_walk_status', unum)
    if i % 5 == 0:
        print(f"  t={i}s  status={st.get('status')} wp={st.get('current_index')}/{st.get('total_waypoints')}")
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  final: {st}")

# Show position
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f)', c.position.x, c.position.y))"
))

# 2. Place drill on coal (-56.5, 91.5) facing south → drop at (-56.5, 93.5)
print("\nplacing drill at coal (-56.5, 91.5) facing south...")
res = call_mod(r, 'place_entity', unum, 'burner-mining-drill', -56.5, 91.5, 8)
print(f"  {res}")
drill_pos = res.get('position') if res.get('ok') else None

# 3. Place wooden-chest 2 tiles south of drill center to catch the drop
if drill_pos:
    dx, dy = drill_pos['x'], drill_pos['y']
    chest_y = dy + 2  # drop position for south-facing 2x2 drill
    print(f"\nplacing chest at ({dx}, {chest_y})...")
    res = call_mod(r, 'place_entity', unum, 'wooden-chest', dx, chest_y, 0)
    print(f"  {res}")

# 4. Fuel drill with wood (find by name to avoid the coal-ore entity)
print("\nfueling drill with wood...")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    f"local s = c.surface; "
    f"local ci = c.get_main_inventory(); "
    f"local d = s.find_entities_filtered{{position={{ {drill_pos['x']}, {drill_pos['y']} }}, radius=0.5, name='burner-mining-drill'}}[1]; "
    "if not d then rcon.print('drill MISSING'); return end; "
    "local fi = d.get_fuel_inventory(); "
    "local n = math.min(5, ci.get_item_count('wood')); "
    "local moved = fi.insert{name='wood', count=n}; "
    "ci.remove{name='wood', count=moved}; "
    "rcon.print('drill fueled +' .. moved .. ' wood')"
))

# 5. Wait + check chest contents
time.sleep(10)
print("\nstatus after 10s:")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    f"local d = s.find_entities_filtered{{position={{ {drill_pos['x']}, {drill_pos['y']} }}, radius=0.5, name='burner-mining-drill'}}[1]; "
    f"local ch = s.find_entities_filtered{{position={{ {drill_pos['x']}, {drill_pos['y'] + 2} }}, radius=0.5, name='wooden-chest'}}[1]; "
    "local msg = ''; "
    "if d then "
    "  local fi = d.get_fuel_inventory(); "
    "  msg = msg .. 'drill: status=' .. d.status .. ' wood=' .. (fi and fi.get_item_count('wood') or 0); "
    "end; "
    "if ch then "
    "  local chi = ch.get_inventory(defines.inventory.chest); "
    "  msg = msg .. ' | chest_coal=' .. (chi and chi.get_item_count('coal') or 0); "
    "end; "
    # Check for items on ground (in case drill missed the chest)
    "local ground = s.find_entities_filtered{position={" + str(drill_pos['x']) + ", " + str(drill_pos['y'] + 2) + "}, radius=1.5, name='item-on-ground'}; "
    "msg = msg .. ' | items_on_ground=' .. #ground; "
    "rcon.print(msg)"
))
r.close()
