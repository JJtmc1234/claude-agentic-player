"""Walk in tighter, mine stone + copper."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

def mine_at(x, y, label='', n_tiles=8):
    # Walk in tight (radius 1.0) to one ore tile
    print(f"\n=== {label}: walking tight to ({x},{y}) ===")
    call_mod(r, 'walk_to', unum, x, y, 1.0)
    for i in range(30):
        time.sleep(1)
        st = call_mod(r, 'get_walk_status', unum)
        if st.get('status') in ('completed', 'error', 'idle'):
            print(f"  arrived: {st}")
            break
    # Hand-mine
    got = 0
    for k in range(n_tiles):
        near = call_mod(r, 'find_nearest_resource', unum, label.replace(' ', '-'), 5)
        if not near.get('ok'):
            print(f"  {label} ran out")
            break
        p = near['position']
        res = call_mod(r, 'start_mining', unum, p['x'], p['y'])
        if not res.get('ok'):
            print(f"  fail: {res.get('error')} dist={res.get('distance')}")
            # walk one tile closer to the ore + retry
            call_mod(r, 'walk_to', unum, p['x'], p['y'], 0.6)
            for _ in range(10):
                time.sleep(0.5)
                ws = call_mod(r, 'get_walk_status', unum)
                if ws.get('status') in ('completed', 'error', 'idle'): break
            res = call_mod(r, 'start_mining', unum, p['x'], p['y'])
            if not res.get('ok'):
                print(f"  still fail: {res}")
                continue
        eta_s = (res.get('eta_ticks', 60) / 60) + 0.5
        time.sleep(eta_s)
        got += 1
    return got

# I'm at ~(86, 35) — go directly to copper (closer)
mine_at(87.5, 37.5, 'copper-ore', n_tiles=8)
# Then go to stone (82.5, 22.5)
mine_at(82.5, 22.5, 'stone', n_tiles=8)

inv = call_mod(r, 'get_character_inventory', unum)
print("\nfinal:")
for it in inv['items']:
    print(f"  {it['name']}: {it['count']}")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d', c.position.x, c.position.y, c.health))"
))
r.close()
