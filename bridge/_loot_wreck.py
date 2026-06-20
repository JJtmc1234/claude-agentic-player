"""Walk to spaceship, mine it (200 firearm-magazines), then mine adjacent wrecks.
Watch for crash-site-fire-flame damage zones along the way."""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# Walk to the spaceship at (-5, -6). Approach from south (current pos ~-9, 49)
# Try to land 2 tiles south of it (to avoid fires concentrated at center)
print("=== walk to spaceship region ===")
call_mod(r, 'walk_to', unum, -5, -3, 1.0)
for _ in range(60):
    time.sleep(1)
    st = call_mod(r, 'get_walk_status', unum)
    if st.get('status') in ('completed', 'error', 'idle'): break
print(f"  {st}")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d', c.position.x, c.position.y, c.health))"
))

# Mine the spaceship first (biggest prize)
TARGETS = [
    ('crash-site-spaceship', -5, -6),
    ('crash-site-spaceship-wreck-medium-1', -16.5, -2.9),  # has 4 iron
    ('crash-site-spaceship-wreck-big-2', -24.2, 1.5),       # has 2 iron + big wreck materials
    ('crash-site-spaceship-wreck-medium-2', -19.5, -3.5),
    ('crash-site-spaceship-wreck-big-1', -33.0, 0.3),
    ('crash-site-spaceship-wreck-medium-3', -39.6, 4.4),
]

for name, tx, ty in TARGETS:
    print(f"\n--- targeting {name} at ({tx}, {ty}) ---")
    # Walk in tight
    call_mod(r, 'walk_to', unum, tx, ty, 1.5)
    for _ in range(30):
        time.sleep(0.5)
        ws = call_mod(r, 'get_walk_status', unum)
        if ws.get('status') in ('completed', 'error', 'idle'): break
    # Try mine
    res = call_mod(r, 'start_mining', unum, tx, ty)
    if not res.get('ok'):
        print(f"  mine fail: {res.get('error')} dist={res.get('distance')}")
        continue
    eta = (res.get('eta_ticks', 60) / 60) + 1
    print(f"  mining... eta={eta:.1f}s")
    time.sleep(eta)
    st = call_mod(r, 'get_mining_status', unum)
    if st.get('mining'):
        # still going, wait more
        time.sleep(2)
    # Show what we got via inventory delta — print full inv at end is easier
    print(f"  done")

# Final inventory
inv = call_mod(r, 'get_character_inventory', unum)
print("\n=== final inventory ===")
for it in inv['items']:
    print(f"  {it['name']}: {it['count']}")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); "
    "rcon.print(string.format('claude at (%.1f, %.1f) hp=%d/%d', "
    "  c.position.x, c.position.y, c.health, c.prototype.max_health))"
))
r.close()
