"""Craft burner-inserter, place it + chest, fuel everything."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Craft 1 iron-gear-wheel (=2 iron) + 1 burner-inserter (=1 iron+1 gear)
print("crafting 1 iron-gear-wheel...")
call_mod(r, 'craft', unum, 'iron-gear-wheel', 1)
while True:
    time.sleep(1)
    st = call_mod(r, 'get_craft_status', unum)
    if st.get('status') != 'crafting': print(f"  {st}"); break

print("\ncrafting 1 burner-inserter...")
call_mod(r, 'craft', unum, 'burner-inserter', 1)
while True:
    time.sleep(1)
    st = call_mod(r, 'get_craft_status', unum)
    if st.get('status') != 'crafting': print(f"  {st}"); break

# Drill at (-14,51), furnace at (-14,53). Inserter at (-14,54) facing N. Chest at (-14,55).
print("\nplacing inserter at (-14, 54) facing NORTH...")
ins = call_mod(r, 'place_entity', unum, 'burner-inserter', -14, 54, 0)
print(f"  {ins}")

print("\nplacing chest at (-14, 55)...")
chest = call_mod(r, 'place_entity', unum, 'wooden-chest', -14, 55, 0)
print(f"  {chest}")

# Fuel everything
print("\nfueling all by name...")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local function fuel(name, x, y, n) "
    "  local e = s.find_entities_filtered{position={x,y}, radius=0.5, name=name}[1]; "
    "  if not e then rcon.print(name..' missing'); return end; "
    "  local fi = e.get_fuel_inventory(); local have = ci.get_item_count('wood'); "
    "  local moved = fi.insert{name='wood', count=math.min(n, have)}; "
    "  ci.remove{name='wood', count=moved}; "
    "  rcon.print(name..' +' ..moved..' wood') "
    "end; "
    "fuel('burner-mining-drill', -14, 51, 5); "
    "fuel('stone-furnace', -14, 53, 5); "
    "fuel('burner-inserter', -14, 54, 3)"
))

time.sleep(15)
print("\nstatus after 15s:")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local d = s.find_entities_filtered{position={-14, 51}, radius=0.5, name='burner-mining-drill'}[1]; "
    "local f = s.find_entities_filtered{position={-14, 53}, radius=0.5, name='stone-furnace'}[1]; "
    "local i = s.find_entities_filtered{position={-14, 54}, radius=0.5, name='burner-inserter'}[1]; "
    "local ch = s.find_entities_filtered{position={-14, 55}, radius=0.5, name='wooden-chest'}[1]; "
    "local ci = ch and ch.get_inventory(defines.inventory.chest); "
    "rcon.print(string.format('drill=%s furn=%s ins=%s chest_plates=%d', "
    "  d and d.status or '?', f and f.status or '?', i and i.status or '?', "
    "  ci and ci.get_item_count('iron-plate') or 0))"
))
r.close()
