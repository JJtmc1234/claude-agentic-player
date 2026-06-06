import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
cmd = ("/silent-command "
       "local s = game.surfaces['nauvis']; "
       "local l = s.find_entities_filtered{position={-4, 77.5}, radius=0.5, type={'loader','loader-1x1'}}[1]; "
       "if l and l.valid then "
       "  rcon.print('name=' .. l.name .. ' loader_type=' .. l.loader_type .. ' dir=' .. l.direction .. ' active=' .. tostring(l.active)) "
       "end")
print(r.command(cmd))
# Also try setting filter and ensuring direction is right
cmd2 = ("/silent-command "
        "local s = game.surfaces['nauvis']; "
        "local l = s.find_entities_filtered{position={-4, 77.5}, radius=0.5, type={'loader','loader-1x1'}}[1]; "
        "if l and l.valid then "
        "  l.loader_type = 'input'; "
        "  rcon.print('after: loader_type=' .. l.loader_type .. ' dir=' .. l.direction) "
        "end")
print(r.command(cmd2))
r.close()
