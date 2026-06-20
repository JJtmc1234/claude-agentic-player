"""Mine the misplaced drill, re-place 1 tile south so it actually covers ore.
Old: drill(87,41) ins(87.5,44.5) chest(87.5,45.5)
New: drill(87,42) ins(87.5,45.5) chest(87.5,46.5)"""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Mine old setup via silent-command
print("=== mining old setup ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local function take(name, x, y) "
    "  local e = s.find_entities_filtered{position={x,y}, radius=0.6, name=name}[1]; "
    "  if not e then return name..':missing' end; "
    "  local fi = e.get_fuel_inventory(); if fi then for _,st in ipairs(fi.get_contents()) do ci.insert{name=st.name, count=st.count} end end; "
    "  local oi = e.get_output_inventory(); if oi then for _,st in ipairs(oi.get_contents()) do ci.insert{name=st.name, count=st.count} end end; "
    "  local chinv = e.get_inventory(defines.inventory.chest); if chinv then for _,st in ipairs(chinv.get_contents()) do ci.insert{name=st.name, count=st.count} end end; "
    "  ci.insert{name=name, count=1}; e.destroy(); return name..':removed' "
    "end; "
    "rcon.print(take('burner-mining-drill', 87, 41)); "
    "rcon.print(take('burner-inserter', 87.5, 44.5)); "
    "rcon.print(take('wooden-chest', 87.5, 45.5))"
))

# Re-place 1 row south so drill actually covers copper-ore tile (87, 42)
print("\n=== re-placing 1 tile south ===")
drill = call_mod(r, 'place_entity', unum, 'burner-mining-drill', 87, 42, 8)
print(f"  drill: {drill}")
if drill.get('ok'):
    dx, dy = drill['position']['x'], drill['position']['y']
    print(f"  actual drill center: ({dx}, {dy})")
    # Inserter pickup tile = drop tile = (dx, dy+2). Inserter at (dx+0.5, dy+3.5).
    ins = call_mod(r, 'place_entity', unum, 'burner-inserter', dx, dy + 3.5, 0)
    print(f"  inserter: {ins}")
    chest = call_mod(r, 'place_entity', unum, 'wooden-chest', dx, dy + 4.5, 0)
    print(f"  chest: {chest}")

# Fuel drill + inserter
print("\n=== fueling ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local function fuel(name, x, y, n) "
    "  local e = s.find_entities_filtered{position={x,y}, radius=0.6, name=name}[1]; "
    "  if not e then return name..':missing' end; "
    "  local fi = e.get_fuel_inventory(); if not fi then return name..':no fi' end; "
    "  local have = ci.get_item_count('wood'); if have < 1 then return name..':no wood' end; "
    "  local m = fi.insert{name='wood', count=math.min(n, have)}; "
    "  if m > 0 then ci.remove{name='wood', count=m} end; "
    "  return name..' +'..m..' (st='..e.status..')' "
    "end; "
    "rcon.print(fuel('burner-mining-drill', 87, 42, 8)); "
    "rcon.print(fuel('burner-inserter', 87.5, 45.5, 4))"
))

# Wait + verify
time.sleep(25)
print("\n=== after 25s ===")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local d = s.find_entities_filtered{position={87, 42}, radius=0.5, name='burner-mining-drill'}[1]; "
    "local i = s.find_entities_filtered{position={87.5, 45.5}, radius=0.5, name='burner-inserter'}[1]; "
    "local ch = s.find_entities_filtered{position={87.5, 46.5}, radius=0.5, name='wooden-chest'}[1]; "
    "local chi = ch and ch.get_inventory(defines.inventory.chest); "
    "rcon.print(string.format('drill=%s ins=%s chest_copper=%d', "
    "  d and d.status or '?', i and i.status or '?', chi and chi.get_item_count('copper-ore') or 0))"
))
r.close()
