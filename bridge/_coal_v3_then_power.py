"""Per JJ: skip the inserter, mine directly into a chest. Scale up.

Phase 1 (here at coal): craft drill+furnace, place drill at rich-coal tile (54, -48),
  place chest at (54.5, -46.5) to catch drop directly.
Phase 2: walk to water (-42, 22), build offshore-pump + boiler + steam-engine + poles.
"""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

def wait_craft():
    while True:
        time.sleep(1)
        st = call_mod(r, 'get_craft_status', unum)
        if st.get('status') != 'crafting': return st

# Phase 1: scale coal mine
print("=== craft 1 furnace + 1 drill ===")
call_mod(r, 'craft', unum, 'stone-furnace', 1); wait_craft()
call_mod(r, 'craft', unum, 'iron-gear-wheel', 3); wait_craft()
call_mod(r, 'craft', unum, 'burner-mining-drill', 1); print(f"  drill: {wait_craft()}")

# Take old inserter we placed earlier at (45.5, -39.5) (we're not using inserters anymore)
print("\n=== removing old coal inserter ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local i = s.find_entities_filtered{position={45.5, -39.5}, radius=0.5, name='burner-inserter'}[1]; "
    "if i then local fi=i.get_fuel_inventory(); for _,st in ipairs(fi.get_contents()) do ci.insert{name=st.name,count=st.count} end; "
    "  ci.insert{name='burner-inserter', count=1}; i.destroy(); rcon.print('removed inserter') "
    "else rcon.print('no inserter') end"
))

# Walk close to drill spot (54, -48). Stand a few south
print("\n=== walk to (54, -44) ===")
call_mod(r, 'walk_to', unum, 54, -44, 1.0)
for _ in range(40):
    time.sleep(0.5)
    st = call_mod(r, 'get_walk_status', unum)
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  {st}")

# Place drill at (54, -48) facing south
print("\n=== place drill (54, -48) ===")
# Clear blockers first
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local b = s.find_entities_filtered{area={{53, -49}, {55, -47}}}; "
    "for _, e in ipairs(b) do "
    "  if e.valid and (e.type=='tree' or e.type=='simple-entity') then e.destroy(); rcon.print('cleared '..e.name) end "
    "end"
))
drill = call_mod(r, 'place_entity', unum, 'burner-mining-drill', 54, -48, 8)
print(f"  drill: {drill}")
if drill.get('ok'):
    dx, dy = drill['position']['x'], drill['position']['y']
    # Chest directly south to catch drop at (54.5, -46.7) which is in tile (54, -47)
    # 1x1 chest at center (54.5, -46.5) covers tile (54, -47). ✓
    chest = call_mod(r, 'place_entity', unum, 'wooden-chest', dx + 0.5, dy + 1.5, 0)
    print(f"  chest: {chest}")
    # Fuel drill
    print(r.command(
        "/silent-command "
        f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
        f"local d = s.find_entities_filtered{{position={{{dx},{dy}}}, radius=0.5, name='burner-mining-drill'}}[1]; "
        "if d then local fi=d.get_fuel_inventory(); local m=fi.insert{name='wood', count=8}; ci.remove{name='wood', count=m}; "
        "  rcon.print('coal drill +' .. m .. ' wood st=' .. d.status) end"
    ))
    time.sleep(15)
    print(r.command(
        "/silent-command "
        "local s = game.surfaces['nauvis']; "
        f"local ch = s.find_entities_filtered{{position={{{dx + 0.5},{dy + 1.5}}}, radius=0.5, name='wooden-chest'}}[1]; "
        f"local d = s.find_entities_filtered{{position={{{dx},{dy}}}, radius=0.5, name='burner-mining-drill'}}[1]; "
        "local chi = ch and ch.get_inventory(defines.inventory.chest); "
        "rcon.print('drill=' .. (d and d.status or -1) .. ' chest_coal=' .. (chi and chi.get_item_count('coal') or 0))"
    ))

# Phase 2: walk to water and build power
print("\n=== walk to water (-42, 22) ===")
call_mod(r, 'walk_to', unum, -42, 20, 2.0)
for i in range(180):
    time.sleep(1)
    st = call_mod(r, 'get_walk_status', unum)
    if i % 15 == 0 or st.get('status') != 'walking':
        print(f"  t={i}s {st.get('status')}")
    if st.get('status') in ('completed', 'error', 'idle'): break
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d', c.position.x, c.position.y, c.health))"
))

# Find a water tile + adjacent land for boiler/engine placement
print("\n=== find water tile + land setup spot ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; "
    "local water = s.find_tiles_filtered{position=c.position, radius=20, name={'water','deepwater'}}; "
    "if #water == 0 then rcon.print('no water near'); return end; "
    "local best, bd = nil, 1e9; "
    "for _, t in ipairs(water) do "
    "  local dx = t.position.x - c.position.x; local dy = t.position.y - c.position.y; "
    "  local d = dx*dx + dy*dy; "
    "  if d < bd then bd = d; best = t end "
    "end; "
    "rcon.print(string.format('water at (%.1f, %.1f)', best.position.x, best.position.y))"
))
r.close()
