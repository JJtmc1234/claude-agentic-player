"""Properly mine wrecks — wait for each to finish before starting next."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

TARGETS = [
    # Start with the wrecks I can definitely path to (avoid the spaceship which had no_path)
    ('crash-site-spaceship-wreck-medium-1', -16.5, -2.9),
    ('crash-site-spaceship-wreck-big-2', -24.2, 1.5),
    ('crash-site-spaceship-wreck-medium-2', -19.5, -3.5),
    ('crash-site-spaceship-wreck-big-1', -33.0, 0.3),
    ('crash-site-spaceship-wreck-medium-3', -39.6, 4.4),
    ('crash-site-spaceship-wreck-small-1', -35.8, 1.3),
    ('crash-site-spaceship-wreck-small-2', -27.2, 3.0),
    ('crash-site-spaceship-wreck-small-3', -33.2, 5.3),
    ('crash-site-spaceship-wreck-small-4', -29.5, 2.3),
    ('crash-site-spaceship-wreck-small-5', -37.3, 6.2),
    ('crash-site-spaceship-wreck-small-6', -20.9, -1.1),
    # Try the spaceship last (different approach: from west)
    ('crash-site-spaceship', -5, -6),
]

inv_pre = call_mod(r, 'get_character_inventory', unum)
inv_pre_map = {it['name']: it['count'] for it in inv_pre['items']}
print(f"inv at start: {inv_pre_map}")

for name, tx, ty in TARGETS:
    print(f"\n--- {name} at ({tx},{ty}) ---")
    # Tight walk
    call_mod(r, 'walk_to', unum, tx, ty, 1.5)
    for _ in range(20):
        time.sleep(0.5)
        ws = call_mod(r, 'get_walk_status', unum)
        if ws.get('status') in ('completed', 'error', 'idle'): break
    if ws.get('error') == 'no path found':
        print(f"  no path — skip")
        continue
    res = call_mod(r, 'start_mining', unum, tx, ty)
    if not res.get('ok'):
        print(f"  mine fail: {res.get('error')} dist={res.get('distance')}")
        continue
    eta_s = (res.get('eta_ticks', 60) / 60)
    print(f"  mining... eta={eta_s:.1f}s")
    # WAIT FOR COMPLETION — poll until mining=false
    waited = 0
    while waited < eta_s + 6:
        time.sleep(0.5)
        waited += 0.5
        st = call_mod(r, 'get_mining_status', unum)
        if not st.get('mining'):
            break
    if st.get('mining'):
        print(f"  STILL MINING after {waited}s — give up")
        # cancel
        call_mod(r, 'stop_mining', unum)
        continue
    # Loot gained — diff with prev inv would tell us but easier: print snapshot now
    inv_now = call_mod(r, 'get_character_inventory', unum)
    new_map = {it['name']: it['count'] for it in inv_now['items']}
    diff = {n: c - inv_pre_map.get(n, 0) for n, c in new_map.items() if c != inv_pre_map.get(n, 0)}
    inv_pre_map = new_map
    print(f"  delta: {diff}")

# Final
inv_final = call_mod(r, 'get_character_inventory', unum)
print(f"\n=== final inventory ===")
for it in inv_final['items']:
    print(f"  {it['name']}: {it['count']}")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d', c.position.x, c.position.y, c.health))"
))
r.close()
