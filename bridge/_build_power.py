"""Build the power chain at the water edge.

In Factorio 2.0:
- offshore-pump (1x1) is placed on a WATER tile (in 2.0 it goes IN the water, not adjacent)
  Actually 2.0 changed this — needs verification. Will try place_entity and iterate.
- boiler 2x3, needs fuel + water input -> steam output
- steam-engine 2x5, needs steam input
- pipes connect them
- small-electric-pole for distribution

Easiest layout (land-based pump in 2.0 sits IN water):
  - pump on water at (px, py)
  - pipe → boiler at (px, py-3) ish
  - boiler → steam-engine
"""
import sys, time
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
unum = int(r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip())

# First show what's around — water tiles, land tiles
print("=== environment scan ===")
print(r.command(
    "/silent-command "
    f"local c = game.get_entity_by_unit_number({unum}); local s = c.surface; "
    "local water_count = #s.find_tiles_filtered{position=c.position, radius=10, name={'water','deepwater'}}; "
    "local can_pump = s.can_place_entity{name='offshore-pump', position={-41.5, 21.5}, force='player', direction=0}; "
    "rcon.print('water within 10: ' .. water_count .. ' can_place_pump at (-41.5, 21.5): ' .. tostring(can_pump))"
))

# Try placing offshore-pump at the water tile center (-41.5, 21.5)
# Direction matters — pump in 2.0 sits IN water, the direction is where it outputs water
# Try all 4 directions
for d in [0, 4, 8, 12]:
    print(f"\n--- try offshore-pump at (-41.5, 21.5) dir={d} ---")
    res = call_mod(r, 'place_entity', unum, 'offshore-pump', -41.5, 21.5, d)
    print(f"  {res}")
    if res.get('ok'):
        print(f"  *** PUMP PLACED at {res['position']} dir={d} ***")
        break
    # Also try nearby water tiles
    if d == 12:
        # Try a few water tiles
        for cx, cy in [(-41, 22), (-42, 21), (-41, 20), (-40, 21), (-42, 22)]:
            res = call_mod(r, 'place_entity', unum, 'offshore-pump', cx, cy, 0)
            print(f"  trying ({cx},{cy}): {res}")
            if res.get('ok'):
                print(f"  *** PUMP PLACED at {res['position']} ***")
                break
        break

inv = call_mod(r, 'get_character_inventory', unum)
pump_left = next((it['count'] for it in inv['items'] if it['name'] == 'offshore-pump'), 0)
print(f"\noffshore-pump in inv: {pump_left}")
r.close()
