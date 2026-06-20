"""Fuel coal drill with wood, walk in closer for hand-mining, get coal flowing."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Fuel coal drill at (45, -41) with wood
print("=== fuel coal drill with wood ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; local ci = c.get_main_inventory(); "
    "local d = s.find_entities_filtered{position={45, -41}, radius=0.5, name='burner-mining-drill'}[1]; "
    "if not d then rcon.print('drill missing'); return end; "
    "local fi = d.get_fuel_inventory(); local have = ci.get_item_count('wood'); "
    "if have <= 0 then rcon.print('NO WOOD to fuel'); return end; "
    "local moved = fi.insert{name='wood', count=math.min(5, have)}; "
    "ci.remove{name='wood', count=moved}; "
    "rcon.print('coal drill fueled +' .. moved .. ' wood')"
))

# Walk 1 tile closer to the coal patch
print("\n=== walk closer for hand mining ===")
res = call_mod(r, 'walk_to', unum, 44, -42, 1.0)
for _ in range(15):
    time.sleep(0.5)
    st = call_mod(r, 'get_walk_status', unum)
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  {st}")
print(r.command(f"/silent-command local c=game.get_entity_by_unit_number({unum}); rcon.print(string.format('claude at (%.1f, %.1f)', c.position.x, c.position.y))"))

# Hand-mine 5 coal tiles for inventory stash
print("\n=== hand-mine 5 coal tiles ===")
for n in range(5):
    near = call_mod(r, 'find_nearest_resource', unum, 'coal', 5)
    if not near.get('ok'):
        print(f"  no coal: {near.get('error')}")
        break
    p = near['position']
    res = call_mod(r, 'start_mining', unum, p['x'], p['y'])
    if not res.get('ok'):
        print(f"  mine fail: {res}")
        break
    print(f"  tile {n+1}: mining coal at ({p['x']:.1f},{p['y']:.1f}) eta_ticks={res.get('eta_ticks')}")
    time.sleep((res.get('eta_ticks', 60) / 60) + 0.5)
    st = call_mod(r, 'get_mining_status', unum)
    # Status returns mining=false when done
    if st.get('mining', False):
        print(f"  still mining... {st}")
        time.sleep(2)

inv = call_mod(r, 'get_character_inventory', unum)
print("\nfinal:")
for it in inv['items']:
    print(f"  {it['name']}: {it['count']}")
r.close()
