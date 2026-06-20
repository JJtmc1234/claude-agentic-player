"""Walk Claude to the iron patch, then poll status until arrived."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
out = r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))")
unum = int(out.strip())

GOAL = (-24.5, 89.5)
print(f"walking unum={unum} to {GOAL} ...")
res = call_mod(r, 'walk_to', unum, GOAL[0], GOAL[1], 2.0)
print(f"  initial: {res}")

for i in range(60):
    time.sleep(1.0)
    st = call_mod(r, 'get_walk_status', unum)
    print(f"  t={i:>2d}s  {st}")
    if st.get('status') in ('completed', 'error', 'idle'):
        break

# Print position
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('arrived at (%.1f, %.1f)', c.position.x, c.position.y))"
))
r.close()
