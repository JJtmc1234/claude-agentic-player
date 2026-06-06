import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
print(r.command("/silent-command "
                "local s = game.surfaces['nauvis']; "
                "local l = s.find_entities_filtered{position={-4, 77.5}, radius=0.5, type={'loader','loader-1x1'}}[1]; "
                "if l and l.valid then "
                "  l.direction = 4; "
                "  rcon.print('dir=' .. l.direction .. ' loader_type=' .. l.loader_type) "
                "end"))
r.close()
