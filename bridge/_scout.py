"""Look around Claude's character: inventory, nearest resources, hostiles."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()

# Get the stored unit_number
out = r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))")
unum = int(out.strip())
print(f"claude unum: {unum}")

# Inventory
inv = call_mod(r, 'get_character_inventory', unum)
print("\n=== inventory ===")
for it in inv.get('items', []):
    print(f"  {it['name']}: {it['count']}")

# Nearest resources
for res in ['iron-ore', 'copper-ore', 'coal', 'stone']:
    near = call_mod(r, 'find_nearest_resource', unum, res, 300)
    if near.get('ok'):
        p = near['position']
        print(f"\n{res:>12s}: ({p['x']:>6.1f}, {p['y']:>6.1f})  dist={near['distance']:.1f}  "
              f"patch_count={near['patch_count']}  amount={near['amount']}")
    else:
        print(f"\n{res:>12s}: {near.get('error', '?')}")

# Hostile scan
print("\n=== hostiles within 200 tiles ===")
print(r.command(
    "/silent-command "
    "local c = game.get_entity_by_unit_number(" + str(unum) + "); "
    "local s = c.surface; "
    "local enemies = s.find_entities_filtered{"
    "  position=c.position, radius=200, force='enemy'}; "
    "local biters, spawners, worms = 0, 0, 0; "
    "for _, e in ipairs(enemies) do "
    "  if e.type == 'unit' then biters = biters + 1 "
    "  elseif e.type == 'unit-spawner' then spawners = spawners + 1 "
    "  elseif e.type == 'turret' then worms = worms + 1 end "
    "end; "
    "rcon.print(string.format('biters=%d spawners=%d worms=%d', biters, spawners, worms))"
))

# Trees + water within 50
print("\n=== trees + water within 50 ===")
print(r.command(
    "/silent-command "
    "local c = game.get_entity_by_unit_number(" + str(unum) + "); "
    "local s = c.surface; "
    "local trees = s.count_entities_filtered{position=c.position, radius=50, type='tree'}; "
    "local water_tiles = s.count_tiles_filtered{position=c.position, radius=50, name={'water', 'deepwater'}}; "
    "rcon.print('trees=' .. trees .. ' water_tiles=' .. water_tiles)"
))

r.close()
