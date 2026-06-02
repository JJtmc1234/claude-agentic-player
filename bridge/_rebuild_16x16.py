"""Rebuild arena as a 16x16 grid with a single wall ring.

Target bounds: x_min=-20, x_max=-5, y_min=70, y_max=85 (16 cols x 16 rows).

Plan:
  1. Wipe all stone-walls and valves on nauvis
  2. Move east output chest + loader from current x=-11 to x=-4
  3. Place 2 fresh top-up-valves at corners (-19.5, 70.5) and (-4.5, 85.5)
  4. Place a single perimeter wall ring just OUTSIDE bounds (gaps at chest/loader spots)
  5. Re-run arena_setup so the mod re-binds with new bounds + chests
"""

import sys, json
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()

# Step 1: wipe walls + valves
print('[16x16] wiping walls + valves ...')
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local w = s.find_entities_filtered{name='stone-wall'}; "
    "local v = s.find_entities_filtered{type='valve'}; "
    "for _, e in pairs(w) do if e.valid then e.destroy() end end; "
    "for _, e in pairs(v) do if e.valid then e.destroy() end end; "
    "rcon.print('wiped walls=' .. #w .. ' valves=' .. #v)"
))

# Step 2: move east output chest + loader from x=-11 to x=-4 (out past new x_max=-5)
print('[16x16] moving east output to x=-4 ...')
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local force = game.forces.player; "
    # Destroy old east loader + chest
    "for _, e in pairs(s.find_entities_filtered{area={{-12,77},{-9,79}}, type={'loader','loader-1x1','container'}}) do "
    "  if e.valid then e.destroy() end "
    "end; "
    # Create new ones to the east of x_max=-5
    "local l = s.create_entity{name='loader', position={-4, 77.5}, force=force, direction=4, raise_built=true}; "
    "local c = s.create_entity{name='steel-chest', position={-2.5, 77.5}, force=force, raise_built=true}; "
    "rcon.print('east_loader=' .. tostring(l and l.valid) .. ' east_chest=' .. tostring(c and c.valid))"
))

# Step 3: place valves at new 16x16 corners
print('[16x16] placing valves at corners ...')
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local force = game.forces.player; "
    # Clear any leftovers at those positions
    "for _, e in pairs(s.find_entities_filtered{area={{-21,70},{-19,71}}}) do if e.valid then e.destroy() end end; "
    "for _, e in pairs(s.find_entities_filtered{area={{-6,85},{-4,86}}}) do if e.valid then e.destroy() end end; "
    "local v1 = s.create_entity{name='top-up-valve', position={-19.5, 70.5}, force=force}; "
    "local v2 = s.create_entity{name='top-up-valve', position={-4.5, 85.5}, force=force}; "
    "rcon.print('v1=' .. tostring(v1 and v1.valid) .. ' v2=' .. tostring(v2 and v2.valid))"
))

# Step 4: place single perimeter wall ring just OUTSIDE bounds.
# Skip the tiles where chest/loader sit (so items can flow through).
print('[16x16] placing single perimeter wall ring ...')
print(r.command(
    "/silent-command "
    "local s = game.surfaces['nauvis']; "
    "local force = game.forces.player; "
    # Define the outer boundary positions: x=-21 to x=-4 (one tile outside),
    # y=69 to y=86. Skip x=-21 at y=77,78 (input loaders) and x=-4 at y=77 (output loader).
    "local placed = 0; "
    "local skip = { ['-21,77']=1, ['-21,78']=1, ['-4,77']=1 }; "
    # North wall (y=69)
    "for x = -21, -4 do "
    "  if not skip[x .. ',69'] then "
    "    local w = s.create_entity{name='stone-wall', position={x+0.5, 69.5}, force=force}; "
    "    if w then placed = placed + 1 end "
    "  end "
    "end; "
    # South wall (y=86)
    "for x = -21, -4 do "
    "  if not skip[x .. ',86'] then "
    "    local w = s.create_entity{name='stone-wall', position={x+0.5, 86.5}, force=force}; "
    "    if w then placed = placed + 1 end "
    "  end "
    "end; "
    # West wall (x=-21), skip loader rows
    "for y = 70, 85 do "
    "  if not skip['-21,' .. y] then "
    "    local w = s.create_entity{name='stone-wall', position={-20.5, y+0.5}, force=force}; "
    "    if w then placed = placed + 1 end "
    "  end "
    "end; "
    # East wall (x=-4), skip loader row
    "for y = 70, 85 do "
    "  if not skip['-4,' .. y] then "
    "    local w = s.create_entity{name='stone-wall', position={-3.5, y+0.5}, force=force}; "
    "    if w then placed = placed + 1 end "
    "  end "
    "end; "
    "rcon.print('walls_placed=' .. placed)"
))

# Step 5: re-run arena_setup
print('[16x16] re-running arena_setup ...')
print(json.dumps(call_mod(r, 'arena_setup', interface='claude_rl'), indent=2)[:1500])

# Confirm
print()
print('[16x16] verifying state ...')
state = call_mod(r, 'arena_debug_state', interface='claude_rl')
print('bounds:', state.get('bounds'))
print('input_loaders:', state.get('input_loaders'))
print('output_loader:', state.get('output_loader'))
r.close()
