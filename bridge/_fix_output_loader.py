"""Fix the output loader's loader_type from 'output' to 'input' so it
takes items from the arena belt INTO the output chest."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
cmd = ("/silent-command "
       "local s = game.surfaces['nauvis']; "
       "for _, l in pairs(s.find_entities_filtered{type={'loader','loader-1x1'}, position={-4, 77.5}, radius=0.5}) do "
       "  if l.valid then "
       "    rcon.print('before: type=' .. l.loader_type .. ' dir=' .. l.direction); "
       "    l.loader_type = 'input'; "
       "    rcon.print('after: type=' .. l.loader_type .. ' dir=' .. l.direction) "
       "  end "
       "end")
print(r.command(cmd))
r.close()
