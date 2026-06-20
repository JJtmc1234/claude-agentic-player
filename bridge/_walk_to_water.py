"""Chunk the walk to water, find nearest water along the way."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

def walk(x, y, radius=2.0):
    print(f"  -> ({x},{y}) r={radius}")
    call_mod(r, 'walk_to', unum, x, y, radius)
    for _ in range(60):
        time.sleep(1)
        st = call_mod(r, 'get_walk_status', unum)
        if st.get('status') in ('completed', 'error', 'idle'):
            print(f"    {st.get('status')}: dist={st.get('final_distance')}")
            return st
    return st

def pos():
    out = r.command(
        "/silent-command "
        f"local c = game.get_entity_by_unit_number({unum}); "
        "rcon.print(string.format('%.1f,%.1f', c.position.x, c.position.y))"
    ).strip()
    return tuple(float(s) for s in out.split(','))

# Walk in chunks toward (-42, 22)
for tgt in [(20, -20), (-10, 0), (-30, 15), (-42, 22)]:
    walk(*tgt, radius=3.0)
    p = pos()
    print(f"  now at {p}")

# Once near water, search
print("\n=== search water ===")
out = r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; "
    "local water = s.find_tiles_filtered{position=c.position, radius=60, name={'water','deepwater'}}; "
    "if #water == 0 then rcon.print('NONE'); return end; "
    "local best, bd = nil, 1e9; "
    "for _, t in ipairs(water) do "
    "  local dx = t.position.x - c.position.x; local dy = t.position.y - c.position.y; "
    "  local d = dx*dx + dy*dy; "
    "  if d < bd then bd = d; best = t end "
    "end; "
    "rcon.print(string.format('%.1f,%.1f', best.position.x, best.position.y))"
).strip()
print(f"  nearest water: {out}")
r.close()
