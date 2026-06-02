import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
print('valves:', r.command("/silent-command local n=0; for _, v in pairs(game.surfaces['nauvis'].find_entities_filtered{type='valve'}) do n=n+1; rcon.print(v.position.x .. ',' .. v.position.y) end; rcon.print('total ' .. n)"))
print()
print('loaders:', r.command("/silent-command local n=0; for _, v in pairs(game.surfaces['nauvis'].find_entities_filtered{type={'loader','loader-1x1'}}) do n=n+1; rcon.print(v.position.x .. ',' .. v.position.y .. ' dir=' .. v.direction) end; rcon.print('total ' .. n)"))
print()
print('chests:', r.command("/silent-command local n=0; for _, v in pairs(game.surfaces['nauvis'].find_entities_filtered{type='container'}) do n=n+1; rcon.print(v.position.x .. ',' .. v.position.y) end; rcon.print('total ' .. n)"))
print()
print('walls (bbox):', r.command("/silent-command local xmin, xmax, ymin, ymax = math.huge, -math.huge, math.huge, -math.huge; local n=0; for _, v in pairs(game.surfaces['nauvis'].find_entities_filtered{name='stone-wall'}) do n=n+1; if v.position.x<xmin then xmin=v.position.x end; if v.position.x>xmax then xmax=v.position.x end; if v.position.y<ymin then ymin=v.position.y end; if v.position.y>ymax then ymax=v.position.y end end; rcon.print('count='..n..' bbox=' .. xmin .. ',' .. ymin .. ' to ' .. xmax .. ',' .. ymax)"))
r.close()
