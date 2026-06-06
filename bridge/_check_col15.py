import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
# col 15 = x=-5 + 0.5 = -4.5. Probe at and around that tile.
cmd = ("/silent-command "
       "local s = game.surfaces['nauvis']; "
       "for _, p in ipairs({{-4.5, 77.5}, {-4, 77.5}, {-3.5, 77.5}}) do "
       "  local ents = s.find_entities_filtered{position={p[1], p[2]}, radius=0.5}; "
       "  rcon.print('@(' .. p[1] .. ',' .. p[2] .. '):'); "
       "  for _, e in ipairs(ents) do "
       "    if e.valid then "
       "      rcon.print('  ' .. e.name .. ' pos=(' .. e.position.x .. ',' .. e.position.y .. ') dir=' .. e.direction) "
       "    end "
       "  end "
       "end")
print(r.command(cmd))
r.close()
