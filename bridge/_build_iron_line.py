"""Place a basic iron line: burner-drill on iron ore, furnace south, chest south.
Fuel both with wood from inventory.

Layout (anchor at drill center):
  drill  (-24.5, 89.5)  facing south, 2x2 → output at (-24.5, 91)
  furnace (-24.5, 91.5) 2x2, receives ore from drill, smelts iron
  chest  (-24.5, 93.5)  1x1, but actually 2x2 wooden-chest no, 1x1
    -> need an inserter from furnace to chest, or chest directly past furnace edge
For simplicity: drill -> furnace direct contact, then inserter into chest.

Even simpler: drill + furnace (direct adjacency means ore/plates pipeline)
+ leave chest for later when we have inserters.
"""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
out = r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip()
unum = int(out)
# Verify character exists
chk = r.command(f"/silent-command local c = game.get_entity_by_unit_number({unum}); rcon.print(tostring(c and c.valid))")
if 'true' not in chk:
    raise RuntimeError(f"stored unum {unum} not valid — re-run _claim_char.py")

# 1. Walk into reach of the iron tile (-24.5, 89.5)
print("walking into placement range...")
res = call_mod(r, 'walk_to', unum, -24.5, 89.5, 4.0)
print(f"  {res}")
for _ in range(20):
    time.sleep(0.5)
    st = call_mod(r, 'get_walk_status', unum)
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  arrived: {st}")

# Position check
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f)', c.position.x, c.position.y))"
))

# 2. Place drill at iron tile, facing south (direction=8)
# Burner drill is 2x2; center at integer + 0.5
print("\nplacing drill at (-24.5, 89.5) facing south...")
res = call_mod(r, 'place_entity', unum, 'burner-mining-drill', -24.5, 89.5, 8)
print(f"  {res}")

# 3. Fuel drill with wood
print("\nfuelling drill with wood...")
res = call_mod(r, 'insert_into_entity', unum, -24.5, 89.5, 'wood', 5, 1)  # 1 = fuel slot
print(f"  {res}")

# 4. Place furnace 2 tiles south to receive ore (drill output drops at center+1.5 south)
print("\nplacing furnace at (-24.5, 91.5)...")
res = call_mod(r, 'place_entity', unum, 'stone-furnace', -24.5, 91.5, 0)
print(f"  {res}")

# 5. Fuel furnace with wood
print("\nfuelling furnace with wood...")
res = call_mod(r, 'insert_into_entity', unum, -24.5, 91.5, 'wood', 5, 1)
print(f"  {res}")

# 6. Wait a few seconds and check both entities
print("\nwaiting 5s for things to start...")
time.sleep(5)
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local d = s.find_entities_filtered{position={-24.5, 89.5}, radius=0.5, name='burner-mining-drill'}[1]; "
    "local f = s.find_entities_filtered{position={-24.5, 91.5}, radius=0.5, name='stone-furnace'}[1]; "
    "local msg = ''; "
    "if d then "
    "  local fuel = d.get_fuel_inventory(); "
    "  msg = msg .. 'drill: status=' .. d.status .. ' fuel=' .. (fuel and fuel.get_item_count('wood') or 0); "
    "end; "
    "if f then "
    "  local fuel = f.get_fuel_inventory(); "
    "  local src = f.get_inventory(defines.inventory.furnace_source); "
    "  local res = f.get_inventory(defines.inventory.furnace_result); "
    "  msg = msg .. ' | furnace: status=' .. f.status "
    "    .. ' fuel=' .. (fuel and fuel.get_item_count('wood') or 0) "
    "    .. ' ore=' .. (src and src.get_item_count('iron-ore') or 0) "
    "    .. ' plates=' .. (res and res.get_item_count('iron-plate') or 0); "
    "end; "
    "rcon.print(msg)"
))
r.close()
