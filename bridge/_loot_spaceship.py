"""Try one more time for the spaceship: walk in, mine, get 200 firearm-magazines."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Show current state of fires
print("=== fires near spaceship ===")
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local fires = s.find_entities_filtered{position={-5,-6}, radius=15, name='crash-site-fire-flame'}; "
    "rcon.print('fires remaining: ' .. #fires)"
))

# Approach from north (less fires there based on earlier scout)
for approach in [(-5, -10), (-5, -8), (-5, -7), (0, -6), (-3, -8)]:
    print(f"\n=== try approach via {approach} ===")
    call_mod(r, 'walk_to', unum, approach[0], approach[1], 1.5)
    for _ in range(60):
        time.sleep(1)
        ws = call_mod(r, 'get_walk_status', unum)
        if ws.get('status') in ('completed', 'error', 'idle'): break
    print(f"  {ws}")
    if ws.get('status') == 'completed':
        # Try mining the spaceship
        res = call_mod(r, 'start_mining', unum, -5, -6)
        print(f"  mine: {res}")
        if res.get('ok'):
            eta_s = (res.get('eta_ticks', 60) / 60)
            waited = 0
            while waited < eta_s + 8:
                time.sleep(0.5)
                waited += 0.5
                st = call_mod(r, 'get_mining_status', unum)
                if not st.get('mining'):
                    break
            print(f"  mining result after {waited}s: {st}")
            inv = call_mod(r, 'get_character_inventory', unum)
            mags = next((it['count'] for it in inv['items'] if it['name'] == 'firearm-magazine'), 0)
            print(f"  firearm-magazines now: {mags}")
            if mags > 0:
                print("  *** SUCCESS ***")
                break
r.close()
