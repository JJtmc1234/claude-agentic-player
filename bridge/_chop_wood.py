"""Walk to nearest tree, chop it, repeat for ~10 trees."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

def find_nearest_tree():
    """Return (name, x, y) of nearest tree within 100 tiles, or None."""
    out = r.command(
        "/silent-command "
        f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; "
        "local trees = s.find_entities_filtered{position=c.position, radius=100, type='tree'}; "
        "if #trees == 0 then rcon.print('NONE'); return end; "
        "local best, bestd = nil, 1e9; "
        "for _, t in ipairs(trees) do "
        "  local dx = t.position.x - c.position.x; "
        "  local dy = t.position.y - c.position.y; "
        "  local d = dx*dx + dy*dy; "
        "  if d < bestd then bestd = d; best = t end "
        "end; "
        "rcon.print(string.format('%s,%.1f,%.1f', best.name, best.position.x, best.position.y))"
    ).strip()
    if out == 'NONE' or not out: return None
    name, sx, sy = out.split(',')
    return name, float(sx), float(sy)

for i in range(10):
    t = find_nearest_tree()
    if not t:
        print(f"\nno trees within 30, stopping at chop #{i}")
        break
    name, tx, ty = t
    print(f"\nchop #{i+1}: {name} at ({tx:.1f}, {ty:.1f})")
    # Walk in
    call_mod(r, 'walk_to', unum, tx, ty, 1.2)
    for _ in range(20):
        time.sleep(0.5)
        ws = call_mod(r, 'get_walk_status', unum)
        if ws.get('status') in ('completed', 'error', 'idle'): break
    # Mine
    res = call_mod(r, 'start_mining', unum, tx, ty)
    if not res.get('ok'):
        print(f"  fail: {res.get('error')}")
        continue
    eta = res.get('eta_ticks', 60) / 60
    waited = 0
    while waited < eta + 4:
        time.sleep(0.5)
        waited += 0.5
        st = call_mod(r, 'get_mining_status', unum)
        if not st.get('mining'): break

inv = call_mod(r, 'get_character_inventory', unum)
wood = next((it['count'] for it in inv['items'] if it['name'] == 'wood'), 0)
print(f"\n=== final: wood = {wood} ===")
r.close()
