"""Craft drill+furnace+inserter, walk to copper patch, build automated copper mine.

Lessons applied:
- Use inserter between drill and chest (drill drop is integer-aligned, chest is *.5)
- For 1x1 inserter south of 2x2 drill: target Y = drill_Y + 2 (drop is at drill_Y + 2, inserter pickup there)
- Inserter dir = side it picks from (dir=0 = picks north, drops south)
"""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# 1. Craft what we need
def wait_craft():
    while True:
        time.sleep(1)
        st = call_mod(r, 'get_craft_status', unum)
        if st.get('status') != 'crafting':
            print(f"  {st.get('status')}: {st.get('error', '')}")
            return st

print("=== crafting ===")
# 2 furnaces (10 stone) - one ingredient, one for the copper mine area
print("2 stone-furnace..."); call_mod(r, 'craft', unum, 'stone-furnace', 2); wait_craft()
# 6 gears (12 iron) - need 3 for drill, extras buffered
print("6 iron-gear-wheel..."); call_mod(r, 'craft', unum, 'iron-gear-wheel', 6); wait_craft()
# 1 burner drill (3 iron + 3 gear + 1 furnace)
print("1 burner-mining-drill..."); call_mod(r, 'craft', unum, 'burner-mining-drill', 1); wait_craft()
# 1 inserter
print("1 burner-inserter..."); call_mod(r, 'craft', unum, 'burner-inserter', 1); wait_craft()

# 2. Walk to copper patch (87.5, 37.5)
print("\n=== walking to copper ===")
call_mod(r, 'walk_to', unum, 87, 37, 1.5)
for i in range(120):
    time.sleep(1)
    st = call_mod(r, 'get_walk_status', unum)
    if i % 10 == 0 or st.get('status') != 'walking':
        print(f"  t={i}s {st.get('status')}")
    if st.get('status') in ('completed', 'error', 'idle'): break

pos_out = r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('%.1f,%.1f', c.position.x, c.position.y))"
).strip()
print(f"  arrived at {pos_out}")

# 3. Find a copper tile near me and snap drill there (2x2 wants integer center)
near = call_mod(r, 'find_nearest_resource', unum, 'copper-ore', 10)
if not near.get('ok'):
    print(f"  no copper near: {near}"); sys.exit(1)
cx, cy = near['position']['x'], near['position']['y']
# Drill 2x2 center to integer; chest at center.5; both within ~3 tiles of me
drill_x = round(cx) - 0.5 + 0.5  # nudge to integer
drill_y = round(cy) - 0.5 + 0.5
drill_x, drill_y = round(cx + 0.5) - 0.5, round(cy + 0.5) - 0.5
# Simpler: just use the ore tile center as the drill target
print(f"\n=== placing drill at copper tile ({drill_x}, {drill_y}) facing south ===")
drill = call_mod(r, 'place_entity', unum, 'burner-mining-drill', cx, cy, 8)
print(f"  drill: {drill}")
if not drill.get('ok'):
    print("  trying nearby tile...");
    # Try a half-tile shift
    drill = call_mod(r, 'place_entity', unum, 'burner-mining-drill', cx + 0.5, cy, 8)
    print(f"  retry: {drill}")
if not drill.get('ok'):
    print("  GIVING UP"); sys.exit(1)

dx, dy = drill['position']['x'], drill['position']['y']

# 4. Inserter south of drill (pickup at drop tile)
# Drill drops at (dx, dy+2). Inserter pickup with dir=0 at inserter.y-1 = dy+2 means inserter.y = dy+3.
# 1x1 inserter snaps to *.5, so target Y = dy+2 gives snapped Y = dy+2.5; pickup = dy+1.5 (WRONG, that's inside drill).
# target Y = dy+3 → snap = dy+3.5? Hmm let me think:
# place(y=dy+2) snaps to closest *.5 = dy+2.5 if dy is integer (which it is for 2x2 drill).
# Pickup of inserter at (x.5, dy+2.5) dir=0 = (x.5, dy+1.5). That's INSIDE drill (which spans dy-1 to dy+1).
# place(y=dy+3) snaps to dy+2.5? No, dy+3 - 0.5 = dy+2.5 down, dy+3 + 0.5 = dy+3.5 up. Round to nearest = depends.
# Actually place_entity for 1x1 lands at exact float input I give if it ends in .5, else snaps.
# So place(y=dy+2.5) → exact (.5). Pickup = dy+1.5. That's tile y=dy+1 → drill row (drill spans tiles dy-1 and dy).
# Drop position with dir=0: (x.5, dy+2.5 + 1) = (x.5, dy+3.5). Chest at (x.5, dy+3.5) catches it.
# So: ins at (dx, dy+2.5), chest at (dx, dy+3.5).
print(f"\n=== placing inserter at ({dx}, {dy + 2.5}) facing N (pickup from drill drop) ===")
ins = call_mod(r, 'place_entity', unum, 'burner-inserter', dx, dy + 2.5, 0)
print(f"  ins: {ins}")
print(f"\n=== placing chest at ({dx}, {dy + 3.5}) ===")
chest = call_mod(r, 'place_entity', unum, 'wooden-chest', dx, dy + 3.5, 0)
print(f"  chest: {chest}")

# 5. Fuel drill + inserter with wood
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
    f"rcon.print(fuel('burner-mining-drill', {dx}, {dy}, 8)); "
    f"rcon.print(fuel('burner-inserter', {dx}, {dy + 2.5}, 4))"
))

# 6. Wait + verify
time.sleep(20)
print("\n=== after 20s ===")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    f"local d = s.find_entities_filtered{{position={{{dx},{dy}}}, radius=0.5, name='burner-mining-drill'}}[1]; "
    f"local i = s.find_entities_filtered{{position={{{dx},{dy+2.5}}}, radius=0.5, name='burner-inserter'}}[1]; "
    f"local ch = s.find_entities_filtered{{position={{{dx},{dy+3.5}}}, radius=0.5, name='wooden-chest'}}[1]; "
    "local chi = ch and ch.get_inventory(defines.inventory.chest); "
    "rcon.print(string.format('drill_st=%s ins_st=%s chest_copper=%d', "
    "  d and d.status or '?', i and i.status or '?', chi and chi.get_item_count('copper-ore') or 0))"
))
r.close()
