"""Fix inserter fuel, then go hand-mine + drill coal at (44.5, -41.5).
JJ's 5-min autonomous window. Priorities:
1. Fix iron inserter so plates actually flow
2. Get coal — both hand-mined (immediate fuel) AND set up a coal drill
3. Return for next steps
"""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# 1. Refuel inserter (unum 39) by direct unum lookup
print("=== fixing iron inserter ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local ci = c.get_main_inventory(); "
    "local i = game.get_entity_by_unit_number(39); "
    "if not (i and i.valid) then "
    "  i = game.surfaces['nauvis'].find_entities_filtered{position={-13.5, 54.5}, radius=0.5, name='burner-inserter'}[1]; "
    "end; "
    "if not i then rcon.print('NO inserter found'); return end; "
    "local fi = i.get_fuel_inventory(); local have = ci.get_item_count('wood'); "
    "local moved = fi.insert{name='wood', count=math.min(3, have)}; "
    "ci.remove{name='wood', count=moved}; "
    "rcon.print(string.format('inserter at (%.1f,%.1f) dir=%d fueled +%d wood', "
    "  i.position.x, i.position.y, i.direction, moved))"
))

# 2. Walk to coal patch (44.5, -41.5)
print("\n=== walking to coal ===")
res = call_mod(r, 'walk_to', unum, 44.5, -41.5, 3.0)
print(f"  start: {res}")
for i in range(120):
    time.sleep(1)
    st = call_mod(r, 'get_walk_status', unum)
    if i % 10 == 0 or st.get('status') != 'walking':
        print(f"  t={i}s {st}")
    if st.get('status') in ('completed', 'error', 'idle'): break

# Position check
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d', c.position.x, c.position.y, c.health))"
))

# 3. Hand-mine 3 coal tiles (need a few coal to fuel the new drill)
print("\n=== hand-mining 3 coal tiles ===")
for tile_n in range(3):
    # Find nearest coal to us
    near = call_mod(r, 'find_nearest_resource', unum, 'coal', 10)
    if not near.get('ok'):
        print(f"  no coal near: {near.get('error')}")
        break
    p = near['position']
    print(f"  tile {tile_n+1}: starting mine on coal at ({p['x']}, {p['y']})...")
    res = call_mod(r, 'start_mining', unum, p['x'], p['y'])
    print(f"    {res}")
    if not res.get('ok'):
        break
    # Wait for completion (eta_ticks / 60 sec, with margin)
    eta_s = (res.get('eta_ticks', 60) // 60) + 2
    time.sleep(eta_s)
    st = call_mod(r, 'get_mining_status', unum)
    print(f"    done: {st}")

# 4. Inventory check
inv = call_mod(r, 'get_character_inventory', unum)
coal_have = next((it['count'] for it in inv['items'] if it['name'] == 'coal'), 0)
wood_have = next((it['count'] for it in inv['items'] if it['name'] == 'wood'), 0)
print(f"\ninventory: coal={coal_have} wood={wood_have}")

# 5. Place coal drill + chest at current coal position
print("\n=== placing coal drill + chest ===")
near = call_mod(r, 'find_nearest_resource', unum, 'coal', 10)
if near.get('ok'):
    cx, cy = near['position']['x'], near['position']['y']
    drill = call_mod(r, 'place_entity', unum, 'burner-mining-drill', cx, cy, 8)
    print(f"  drill: {drill}")
    if drill.get('ok'):
        dx, dy = drill['position']['x'], drill['position']['y']
        chest = call_mod(r, 'place_entity', unum, 'wooden-chest', dx, dy+2, 0)
        print(f"  chest: {chest}")
        # Fuel drill with coal (it'll self-sustain after this)
        print(r.command(
            "/silent-command "
            f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
            f"local d = s.find_entities_filtered{{position={{{dx},{dy}}}, radius=0.5, name='burner-mining-drill'}}[1]; "
            "if not d then rcon.print('drill missing'); return end; "
            "local fi = d.get_fuel_inventory(); local have = ci.get_item_count('coal'); "
            f"local moved = fi.insert{{name='coal', count=math.min(3, have)}}; "
            "ci.remove{name='coal', count=moved}; "
            "rcon.print('coal drill fueled +' .. moved .. ' coal')"
        ))

# 6. Final inventory
inv = call_mod(r, 'get_character_inventory', unum)
print("\nfinal inventory:")
for it in inv['items']:
    print(f"  {it['name']}: {it['count']}")
r.close()
