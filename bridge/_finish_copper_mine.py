"""Finish copper mine setup: drill exists at (87, 41), needs inserter + chest south."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Walk closer to placement zone
print("walking to copper drill area...")
call_mod(r, 'walk_to', unum, 87, 44, 1.5)
for _ in range(40):
    time.sleep(0.5)
    st = call_mod(r, 'get_walk_status', unum)
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  {st}")

# Drill at (87, 41) drops at (87, 43). For inserter pickup tile (87, 43):
# inserter 1x1 at (87.5, 44.5), dir=0 → pickup (87.5, 43.5) = tile (87, 43). ✓
# chest 1x1 at (87.5, 45.5), receives inserter drop at (87.5, 45.5).
print("\nplacing inserter at (87, 44.5) [snap target = (87.5, 44.5)] dir=N...")
ins = call_mod(r, 'place_entity', unum, 'burner-inserter', 87, 44.5, 0)
print(f"  {ins}")

if not ins.get('ok'):
    # Try mining any blockers in that tile
    print("  trying to clear blocker...")
    print(r.command(
        "/silent-command "
        "local s = game.surfaces['nauvis']; "
        "local b = s.find_entities_filtered{position={87.5, 44.5}, radius=0.5}; "
        "for _, e in ipairs(b) do "
        "  if e.valid and e.type == 'tree' then e.destroy(); rcon.print('removed tree') "
        "  elseif e.valid and e.type == 'simple-entity' then e.destroy(); rcon.print('removed rock') "
        "  end "
        "end"
    ))
    ins = call_mod(r, 'place_entity', unum, 'burner-inserter', 87, 44.5, 0)
    print(f"  retry: {ins}")

print("\nplacing chest at (87, 45.5)...")
chest = call_mod(r, 'place_entity', unum, 'wooden-chest', 87, 45.5, 0)
print(f"  {chest}")

if not chest.get('ok'):
    print("  clearing blocker...")
    print(r.command(
        "/silent-command "
        "local s = game.surfaces['nauvis']; "
        "local b = s.find_entities_filtered{position={87.5, 45.5}, radius=0.5}; "
        "for _, e in ipairs(b) do "
        "  if e.valid and (e.type=='tree' or e.type=='simple-entity') then e.destroy(); rcon.print('removed '..e.name) end "
        "end"
    ))
    chest = call_mod(r, 'place_entity', unum, 'wooden-chest', 87, 45.5, 0)
    print(f"  retry: {chest}")

# Fuel inserter
print("\nfueling inserter...")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local i = s.find_entities_filtered{position={87.5, 44.5}, radius=0.5, name='burner-inserter'}[1]; "
    "if not i then rcon.print('NO ins'); return end; "
    "local fi = i.get_fuel_inventory(); "
    "local m = fi.insert{name='wood', count=5}; "
    "if m > 0 then ci.remove{name='wood', count=m} end; "
    "rcon.print('+' .. m .. ' wood, dir=' .. i.direction .. ' status=' .. i.status)"
))

# Wait + verify
time.sleep(20)
print("\nafter 20s:")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local d = s.find_entities_filtered{position={87, 41}, radius=0.5, name='burner-mining-drill'}[1]; "
    "local i = s.find_entities_filtered{position={87.5, 44.5}, radius=0.5, name='burner-inserter'}[1]; "
    "local ch = s.find_entities_filtered{position={87.5, 45.5}, radius=0.5, name='wooden-chest'}[1]; "
    "local chi = ch and ch.get_inventory(defines.inventory.chest); "
    "local ground = s.find_entities_filtered{position={87, 43}, radius=1.5, name='item-on-ground'}; "
    "rcon.print(string.format('drill=%s ins=%s chest_copper=%d ground_items=%d', "
    "  d and d.status or '?', i and i.status or '?', chi and chi.get_item_count('copper-ore') or 0, #ground))"
))
r.close()
