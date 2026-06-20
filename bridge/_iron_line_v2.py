"""Walk to iron at (-14.5, 50.5), build drill+furnace+inserter+chest.
Uses what I learned last time:
  - Inserter direction = side it picks FROM (north=0 picks from north neighbor)
  - 2x2 entities snap to integer centers; 1x1 to integer+0.5
  - Use entity-name disambiguation when fueling (don't let the helper pick ore)
"""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Walk
print("walking to iron (-14.5, 50.5)...")
res = call_mod(r, 'walk_to', unum, -14.5, 50.5, 3.0)
print(f"  initial: {res}")
for i in range(120):
    time.sleep(1.0)
    st = call_mod(r, 'get_walk_status', unum)
    if i % 5 == 0 or st.get('status') != 'walking':
        print(f"  t={i}s {st}")
    if st.get('status') in ('completed', 'error', 'idle'): break

# Position + safety check
pos_out = r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d', c.position.x, c.position.y, c.health))"
)
print(f"  {pos_out}")

# Place drill on iron, facing south
print("\nplacing drill at (-14.5, 50.5) facing south (8)...")
drill = call_mod(r, 'place_entity', unum, 'burner-mining-drill', -14.5, 50.5, 8)
print(f"  {drill}")
dx, dy = drill['position']['x'], drill['position']['y']

print(f"\nplacing furnace 2 south at ({dx}, {dy+2})...")
furn = call_mod(r, 'place_entity', unum, 'stone-furnace', dx, dy+2, 0)
print(f"  {furn}")

# Inserter at dy+3 facing NORTH (picks from furnace, drops south to chest)
print(f"\nplacing inserter at ({dx}, {dy+3}) facing NORTH (0) - picks from furnace, drops south...")
ins = call_mod(r, 'place_entity', unum, 'burner-inserter', dx, dy+3, 0)
print(f"  {ins}")
ix, iy = ins['position']['x'], ins['position']['y']

# Chest at iy+1
print(f"\nplacing chest at ({ix}, {iy+1})...")
chest = call_mod(r, 'place_entity', unum, 'wooden-chest', ix, iy+1, 0)
print(f"  {chest}")
cx, cy = chest['position']['x'], chest['position']['y']

# Fuel each by name
print("\nfueling drill+furnace+inserter (wood) by entity name...")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    f"local s = c.surface; local ci = c.get_main_inventory(); "
    f"local function fuel(name, x, y, n) "
    f"  local e = s.find_entities_filtered{{position={{x,y}}, radius=0.5, name=name}}[1]; "
    f"  if not e then rcon.print(name .. ' not found at ('..x..','..y..')'); return end; "
    f"  local fi = e.get_fuel_inventory(); local moved = fi.insert{{name='wood', count=n}}; "
    f"  ci.remove{{name='wood', count=moved}}; "
    f"  rcon.print(name .. ' fueled +' .. moved .. ' wood') "
    f"end; "
    f"fuel('burner-mining-drill', {dx}, {dy}, 5); "
    f"fuel('stone-furnace', {dx}, {dy+2}, 5); "
    f"fuel('burner-inserter', {ix}, {iy}, 3)"
))

time.sleep(12)
print("\nstatus after 12s:")
print(r.command(
    "/silent-command "
    f"local s = game.surfaces['nauvis']; "
    f"local d = s.find_entities_filtered{{position={{{dx},{dy}}}, radius=0.5, name='burner-mining-drill'}}[1]; "
    f"local f = s.find_entities_filtered{{position={{{dx},{dy+2}}}, radius=0.5, name='stone-furnace'}}[1]; "
    f"local i = s.find_entities_filtered{{position={{{ix},{iy}}}, radius=0.5, name='burner-inserter'}}[1]; "
    f"local ch = s.find_entities_filtered{{position={{{cx},{cy}}}, radius=0.5, name='wooden-chest'}}[1]; "
    "rcon.print(string.format('drill=%s furn=%s ins=%s plates=%d', "
    "  d and d.status or '?', f and f.status or '?', i and i.status or '?', "
    "  (ch and ch.get_inventory(defines.inventory.chest):get_item_count('iron-plate') or 0)))"
))
r.close()
