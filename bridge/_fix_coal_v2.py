"""Find coal-patch center (highest amount tile), build drill+inserter+chest there."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Inventory + clean up old inserter
inv = call_mod(r, 'get_character_inventory', unum)
print("inv:", {it['name']: it['count'] for it in inv['items'] if it['count'] > 0})

# Scout coal: find highest-amount tile within 30
print("\n=== coal-patch best tile ===")
out = r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local coals = s.find_entities_filtered{position={45, -41}, radius=30, name='coal'}; "
    "if #coals == 0 then rcon.print('NO COAL'); return end; "
    "local best, ba = nil, -1; "
    "for _, c in ipairs(coals) do "
    "  if c.amount > ba then ba = c.amount; best = c end "
    "end; "
    "rcon.print(string.format('%.1f,%.1f,%d', best.position.x, best.position.y, ba))"
).strip()
print(f"  best: {out}")
sx, sy, samount = out.split(',')
cx, cy = float(sx), float(sy)  # coal tile center, e.g. (44.5, -41.5)

# Drill 2x2 needs integer center. Pick the integer point closest to (cx, cy).
drill_cx, drill_cy = round(cx - 0.5), round(cy - 0.5)
# This makes drill bbox cover tile (drill_cx-1, drill_cy-1) ... (drill_cx, drill_cy)
# We want (cx-0.5, cy-0.5) = tile (cx-0.5, cy-0.5) inside drill bbox
# tile of (cx, cy) when cx=*.5 is tile (cx-0.5, cy-0.5)
# Need drill_cx - 1 <= cx-0.5 <= drill_cx → drill_cx ∈ [cx-0.5, cx+0.5]
# So drill_cx = round(cx) works
drill_cx, drill_cy = round(cx), round(cy)
print(f"  drill target: ({drill_cx}, {drill_cy})")

# Walk close to drill spot but not on it
print(f"\n=== walking close to drill spot ===")
call_mod(r, 'walk_to', unum, drill_cx, drill_cy + 4, 1.0)
for _ in range(30):
    time.sleep(0.5)
    st = call_mod(r, 'get_walk_status', unum)
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  {st}")

# Place drill
print(f"\nplacing drill at ({drill_cx}, {drill_cy})...")
drill = call_mod(r, 'place_entity', unum, 'burner-mining-drill', drill_cx, drill_cy, 8)
print(f"  {drill}")
if not drill.get('ok'):
    # Clear blockers, retry
    print(r.command(
        "/silent-command "
        f"local s = game.surfaces['nauvis']; "
        f"local b = s.find_entities_filtered{{area={{{{{drill_cx-1}, {drill_cy-1}}}, {{{drill_cx+1}, {drill_cy+1}}}}}}}; "
        "for _, e in ipairs(b) do "
        "  if e.valid and (e.type=='tree' or e.type=='simple-entity') then e.destroy(); rcon.print('cleared '..e.name) end "
        "end"
    ))
    drill = call_mod(r, 'place_entity', unum, 'burner-mining-drill', drill_cx, drill_cy, 8)
    print(f"  retry: {drill}")

if drill.get('ok'):
    dx, dy = drill['position']['x'], drill['position']['y']
    # ins at (dx+0.5, dy+2.5), chest at (dx+0.5, dy+3.5)
    print(f"\nplacing inserter at ({dx + 0.5}, {dy + 2.5})...")
    # Remove the existing misplaced inserter at (45.5, -39.5) if it's not in the new chain path
    if (dx + 0.5, dy + 2.5) != (45.5, -39.5):
        print(r.command(
            "/silent-command "
            f"local c = game.get_entity_by_unit_number({unum}); local ci = c.get_main_inventory(); local s = c.surface; "
            "local i = s.find_entities_filtered{position={45.5, -39.5}, radius=0.5, name='burner-inserter'}[1]; "
            "if i then local fi=i.get_fuel_inventory(); for _,st in ipairs(fi.get_contents()) do ci.insert{name=st.name,count=st.count} end; ci.insert{name='burner-inserter', count=1}; i.destroy(); rcon.print('took old inserter') end"
        ))
    ins = call_mod(r, 'place_entity', unum, 'burner-inserter', dx + 0.5, dy + 2.5, 0)
    print(f"  ins: {ins}")
    # Chest -- reuse existing if it's in the right place, else move
    print(f"\nrelocating chest to ({dx + 0.5}, {dy + 3.5}) if needed...")
    print(r.command(
        "/silent-command "
        f"local c = game.get_entity_by_unit_number({unum}); local ci = c.get_main_inventory(); local s = c.surface; "
        "local old = s.find_entities_filtered{position={45.5, -38.5}, radius=0.5, name='wooden-chest'}[1]; "
        "if old then local chinv=old.get_inventory(defines.inventory.chest); for _,st in ipairs(chinv.get_contents()) do ci.insert{name=st.name,count=st.count} end; ci.insert{name='wooden-chest', count=1}; old.destroy(); rcon.print('took old chest') end"
    ))
    chest = call_mod(r, 'place_entity', unum, 'wooden-chest', dx + 0.5, dy + 3.5, 0)
    print(f"  chest: {chest}")

    # Fuel drill + inserter
    print("\nfueling...")
    print(r.command(
        "/silent-command "
        f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
        "local function fuel(name, x, y, n) "
        "  local e = s.find_entities_filtered{position={x,y}, radius=0.6, name=name}[1]; "
        "  if not e then return name..':missing' end; "
        "  local fi = e.get_fuel_inventory(); if not fi then return name..':nofi' end; "
        "  local have = ci.get_item_count('wood'); if have < 1 then return name..':nowood' end; "
        "  local m = fi.insert{name='wood', count=math.min(n, have)}; "
        "  if m > 0 then ci.remove{name='wood', count=m} end; "
        "  return name..' +'..m..' st='..e.status "
        "end; "
        f"rcon.print(fuel('burner-mining-drill', {dx}, {dy}, 8)); "
        f"rcon.print(fuel('burner-inserter', {dx + 0.5}, {dy + 2.5}, 4))"
    ))

    time.sleep(25)
    print("\nafter 25s:")
    print(r.command(
        "/silent-command "
        "local s = game.surfaces['nauvis']; "
        f"local d = s.find_entities_filtered{{position={{{dx},{dy}}}, radius=0.5, name='burner-mining-drill'}}[1]; "
        f"local i = s.find_entities_filtered{{position={{{dx+0.5},{dy+2.5}}}, radius=0.5, name='burner-inserter'}}[1]; "
        f"local ch = s.find_entities_filtered{{position={{{dx+0.5},{dy+3.5}}}, radius=0.5, name='wooden-chest'}}[1]; "
        "local chi = ch and ch.get_inventory(defines.inventory.chest); "
        "rcon.print(string.format('drill=%d ins=%d chest_coal=%d', d and d.status or -1, i and i.status or -1, chi and chi.get_item_count('coal') or 0))"
    ))
r.close()
