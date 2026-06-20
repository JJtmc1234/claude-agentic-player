"""Walk to base, refuel iron + copper lines with wood."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Walk to iron line area
print("=== walking to base ===")
call_mod(r, 'walk_to', unum, -11, 53, 2.0)
for _ in range(60):
    time.sleep(1)
    st = call_mod(r, 'get_walk_status', unum)
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  {st}")

# Refuel all 6 entities by exact unum/position
print("\n=== refueling iron + copper ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local function fuel(name, x, y, n) "
    "  local e = s.find_entities_filtered{position={x,y}, radius=0.6, name=name}[1]; "
    "  if not e then return name..'@('..x..','..y..'):missing' end; "
    "  local fi = e.get_fuel_inventory(); "
    "  if not fi then return name..':no fuel inv' end; "
    "  local have = ci.get_item_count('wood'); "
    "  if have < 1 then return name..':no wood' end; "
    "  local moved = fi.insert{name='wood', count=math.min(n, have)}; "
    "  ci.remove{name='wood', count=moved}; "
    "  return name..' +'..moved..' (status='..e.status..')' "
    "end; "
    "rcon.print(fuel('burner-mining-drill', -14, 51, 8)); "
    "rcon.print(fuel('stone-furnace', -14, 53, 8)); "
    "rcon.print(fuel('burner-inserter', -13.5, 54.5, 4)); "
    "rcon.print(fuel('stone-furnace', -11, 52, 8)); "
    "rcon.print(fuel('burner-inserter', -10.5, 54.5, 4))"
))

# Wait + verify chest progress
time.sleep(20)
print("\n=== status after 20s ===")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local function chc(x, y, item) "
    "  local ch = s.find_entities_filtered{position={x,y}, radius=0.5, name='wooden-chest'}[1]; "
    "  if not ch then return -1 end; "
    "  local inv = ch.get_inventory(defines.inventory.chest); "
    "  return inv and inv.get_item_count(item) or 0 "
    "end; "
    "rcon.print('iron_chest=' .. chc(-13.5, 55.5, 'iron-plate')); "
    "rcon.print('copper_chest=' .. chc(-10.5, 55.5, 'copper-plate'))"
))

inv = call_mod(r, 'get_character_inventory', unum)
print("\n=== inventory ===")
for it in sorted(inv['items'], key=lambda x: -x['count']):
    print(f"  {it['name']}: {it['count']}")
r.close()
