import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
cmd = ("/silent-command "
       "local s = game.surfaces['nauvis']; "
       "for _, l in pairs(s.find_entities_filtered{type={'loader','loader-1x1'}}) do "
       "  if l.valid then "
       "    rcon.print(l.name .. ' @ (' .. l.position.x .. ',' .. l.position.y .. ') dir=' .. l.direction .. ' type=' .. (l.loader_type or 'nil')) "
       "  end "
       "end")
print(r.command(cmd))
r.close()
