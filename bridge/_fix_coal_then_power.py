"""Fix coal mine offset first (per JJ), then walk to water and build power.

Coal mine: drill at (45, -41), drop_pos = (45.5, -39.7) = tile (45, -40).
Existing chest at (45.5, -38.5) = tile (45, -39). 1 tile too south.
Fix: add a burner-inserter at (45.5, -39.5) dir=N (picks tile (45, -40), drops tile (45, -39) = chest)."""
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

# Craft 1 inserter + 4 cables + 2 poles
print("crafting inserter + cables + poles...")
call_mod(r, 'craft', unum, 'burner-inserter', 1); wait_craft()
call_mod(r, 'craft', unum, 'copper-cable', 2); wait_craft()  # 4 more cables
call_mod(r, 'craft', unum, 'small-electric-pole', 2); print(f"  poles: {wait_craft()}")

# Walk to coal mine
print("\n=== walking to coal mine (45, -41) ===")
call_mod(r, 'walk_to', unum, 45, -39, 1.5)
for i in range(120):
    time.sleep(1)
    st = call_mod(r, 'get_walk_status', unum)
    if i % 10 == 0 or st.get('status') != 'walking':
        print(f"  t={i}s {st.get('status')}")
    if st.get('status') in ('completed', 'error', 'idle'): break
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d', c.position.x, c.position.y, c.health))"
))

# Add inserter at the right spot: (45.5, -39.5)
print("\n=== add coal inserter at (45.5, -39.5) ===")
# First clear anything blocking that tile
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local b = s.find_entities_filtered{position={45.5, -39.5}, radius=0.4}; "
    "for _, e in ipairs(b) do "
    "  if e.valid and (e.type=='tree' or e.type=='simple-entity' or e.name=='item-on-ground') then "
    "    e.destroy(); rcon.print('cleared ' .. e.name) "
    "  end "
    "end"
))
ins = call_mod(r, 'place_entity', unum, 'burner-inserter', 45.5, -39.5, 0)
print(f"  ins: {ins}")
# Fuel it
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local i = s.find_entities_filtered{position={45.5, -39.5}, radius=0.5, name='burner-inserter'}[1]; "
    "if not i then rcon.print('NO ins'); return end; "
    "local fi = i.get_fuel_inventory(); "
    "local have = ci.get_item_count('wood'); "
    "local m = fi.insert{name='wood', count=math.min(5, have)}; "
    "if m > 0 then ci.remove{name='wood', count=m} end; "
    "rcon.print('+' .. m .. ' wood, dir=' .. i.direction)"
))

# Also fuel the coal drill (if stalled)
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local d = s.find_entities_filtered{position={45, -41}, radius=0.5, name='burner-mining-drill'}[1]; "
    "if not d then rcon.print('NO drill'); return end; "
    "local fi = d.get_fuel_inventory(); "
    "local have = ci.get_item_count('wood'); "
    "local m = fi.insert{name='wood', count=math.min(5, have)}; "
    "if m > 0 then ci.remove{name='wood', count=m} end; "
    "rcon.print('drill: +' .. m .. ' wood (st=' .. d.status .. ')')"
))

time.sleep(20)
# Verify chest receiving coal now
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local ch = s.find_entities_filtered{position={45.5, -38.5}, radius=0.5, name='wooden-chest'}[1]; "
    "local d = s.find_entities_filtered{position={45, -41}, radius=0.5, name='burner-mining-drill'}[1]; "
    "local i = s.find_entities_filtered{position={45.5, -39.5}, radius=0.5, name='burner-inserter'}[1]; "
    "local chi = ch and ch.get_inventory(defines.inventory.chest); "
    "rcon.print(string.format('drill=%d ins=%d chest_coal=%d', "
    "  d and d.status or -1, i and i.status or -1, chi and chi.get_item_count('coal') or 0))"
))
r.close()
