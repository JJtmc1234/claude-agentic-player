"""Walk east, hand-mine 8 stone + 8 copper, return north toward base."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())


def walk(x, y, radius=2.0, label=''):
    print(f"  -> walking to ({x},{y}) {label}")
    call_mod(r, 'walk_to', unum, x, y, radius)
    for i in range(60):
        time.sleep(1)
        st = call_mod(r, 'get_walk_status', unum)
        if i % 5 == 0:
            print(f"    t={i}s {st.get('status')} wp={st.get('current_index')}/{st.get('total_waypoints')}")
        if st.get('status') in ('completed', 'error', 'idle'):
            return st
    return st


def mine_n(resource, count):
    print(f"\n=== hand-mining {count} {resource} ===")
    got = 0
    for n in range(count):
        near = call_mod(r, 'find_nearest_resource', unum, resource, 8)
        if not near.get('ok'):
            print(f"  no more {resource}: {near.get('error')}")
            break
        p = near['position']
        res = call_mod(r, 'start_mining', unum, p['x'], p['y'])
        if not res.get('ok'):
            print(f"  mine fail: {res}")
            break
        eta_s = (res.get('eta_ticks', 60) / 60) + 0.5
        time.sleep(eta_s)
        st = call_mod(r, 'get_mining_status', unum)
        got = n + 1
    return got

# Go to stone
print("=== walking to stone (82.5, 22.5) ===")
walk(82.5, 22.5, 3.0, '(stone patch)')
mine_n('stone', 8)

# Copper is 17 tiles SE of stone
print("\n=== walking to copper (87.5, 37.5) ===")
walk(87.5, 37.5, 3.0, '(copper patch)')
mine_n('copper-ore', 8)

# Status + inv
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d', c.position.x, c.position.y, c.health))"
))
inv = call_mod(r, 'get_character_inventory', unum)
print("\nfinal inventory:")
for it in inv['items']:
    print(f"  {it['name']}: {it['count']}")
r.close()
