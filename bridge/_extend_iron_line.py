"""Craft a burner-inserter, place it at furnace output to feed a wooden chest.
Layout:
  drill(-24,90) -> furnace(-24,92) -> [burner-inserter at (-24,93)] -> chest(-24,94)
"""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# 1. Craft 2 burner-inserters (cost: 2 * (1 iron + 1 gear) = 2 iron + 2 gears = 6 iron)
# But iron-gear-wheel is its own recipe. We need to craft gears first.
print("crafting 4 iron-gear-wheel (2 iron each = 8 iron)...")
res = call_mod(r, 'craft', unum, 'iron-gear-wheel', 4)
print(f"  {res}")
# Wait for craft completion
while True:
    time.sleep(1)
    st = call_mod(r, 'get_craft_status', unum)
    print(f"  status: {st.get('status')} crafted={st.get('crafted')}/{st.get('requested')}")
    if st.get('status') in ('completed', 'error', 'idle'): break

print("\ncrafting 2 burner-inserter...")
res = call_mod(r, 'craft', unum, 'burner-inserter', 2)
print(f"  {res}")
while True:
    time.sleep(1)
    st = call_mod(r, 'get_craft_status', unum)
    print(f"  status: {st.get('status')} crafted={st.get('crafted')}/{st.get('requested')}")
    if st.get('status') in ('completed', 'error', 'idle'): break

# 2. Walk to furnace position to be in placement reach
print("\nwalking to furnace area...")
res = call_mod(r, 'walk_to', unum, -24, 92, 3.0)
for _ in range(20):
    time.sleep(0.5)
    st = call_mod(r, 'get_walk_status', unum)
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  {st}")

# 3. Place burner-inserter at (-24, 93), facing south (pickup north = furnace, drop south = chest)
# Inserter direction is the direction it picks FROM. To pick from furnace (north) and drop south,
# direction should be... NORTH=0 (pickup north, drop south). Actually inserter direction is the
# direction it drops TOWARD. So drop south = direction south = 8. Pickup is opposite = north.
# Per Factorio: defines.direction.south = 8 means inserter rotated to face south.
# An inserter "facing south" picks from north and drops south. Perfect.
print("\nplacing burner-inserter at (-24, 93) facing south...")
res = call_mod(r, 'place_entity', unum, 'burner-inserter', -24, 93, 8)
print(f"  {res}")

# 4. Place wooden-chest at (-24, 94)
print("\nplacing wooden-chest at (-24, 94)...")
res = call_mod(r, 'place_entity', unum, 'wooden-chest', -24, 94, 0)
print(f"  {res}")

# 5. Fuel inserter
print("\nfuelling inserter...")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "local s = c.surface; "
    "local char_inv = c.get_main_inventory(); "
    "local i = s.find_entities_filtered{position={-24, 93}, radius=0.5, name='burner-inserter'}[1]; "
    "if not i then rcon.print('no inserter at -24,93'); return end; "
    "local fi = i.get_fuel_inventory(); "
    "local moved = fi.insert{name='wood', count=3}; "
    "char_inv.remove{name='wood', count=moved}; "
    "rcon.print('inserter fuelled +' .. moved .. ' wood')"
))

# 6. Wait + check
time.sleep(10)
print("\nstatus after 10s:")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local d = s.find_entities_filtered{position={-24, 90}, radius=0.5, name='burner-mining-drill'}[1]; "
    "local f = s.find_entities_filtered{position={-24, 92}, radius=0.5, name='stone-furnace'}[1]; "
    "local i = s.find_entities_filtered{position={-24, 93}, radius=0.5, name='burner-inserter'}[1]; "
    "local ch = s.find_entities_filtered{position={-24, 94}, radius=0.5, name='wooden-chest'}[1]; "
    "local msg = ''; "
    "if d then msg = msg .. 'drill=' .. d.status end; "
    "if f then "
    "  local res_inv = f.get_inventory(defines.inventory.furnace_result); "
    "  msg = msg .. ' | furnace=' .. f.status .. ' plates_in_furnace=' .. (res_inv and res_inv.get_item_count('iron-plate') or 0); "
    "end; "
    "if i then msg = msg .. ' | inserter=' .. i.status end; "
    "if ch then "
    "  local chi = ch.get_inventory(defines.inventory.chest); "
    "  msg = msg .. ' | chest_plates=' .. (chi and chi.get_item_count('iron-plate') or 0); "
    "end; "
    "rcon.print(msg)"
))
r.close()
