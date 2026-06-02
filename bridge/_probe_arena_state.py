"""Probe what JJ placed in the arena area: valves, walls, chests, loaders."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
cmd = ("/silent-command "
       "local s = game.surfaces['nauvis']; "
       "local valves = s.find_entities_filtered{ type='valve' }; "
       "rcon.print('valves: ' .. #valves); "
       "for _, v in ipairs(valves) do rcon.print('  ' .. v.name .. ' @ ' .. v.position.x .. ',' .. v.position.y) end; "
       "local loaders = s.find_entities_filtered{ type={'loader', 'loader-1x1'} }; "
       "rcon.print('loaders: ' .. #loaders); "
       "for _, l in ipairs(loaders) do rcon.print('  @ ' .. l.position.x .. ',' .. l.position.y .. ' dir=' .. l.direction) end; "
       "local chests = s.find_entities_filtered{ type='container' }; "
       "rcon.print('chests: ' .. #chests); "
       "for _, c in ipairs(chests) do rcon.print('  ' .. c.name .. ' @ ' .. c.position.x .. ',' .. c.position.y) end; "
       "local walls = s.find_entities_filtered{ name='stone-wall' }; "
       "rcon.print('walls: ' .. #walls .. ' (showing y-bounds only)'); "
       "local wymin, wymax, wxmin, wxmax = math.huge, -math.huge, math.huge, -math.huge; "
       "for _, w in ipairs(walls) do "
       "  if w.position.y < wymin then wymin = w.position.y end; "
       "  if w.position.y > wymax then wymax = w.position.y end; "
       "  if w.position.x < wxmin then wxmin = w.position.x end; "
       "  if w.position.x > wxmax then wxmax = w.position.x end; "
       "end; "
       "rcon.print('  walls span x=' .. wxmin .. '..' .. wxmax .. '  y=' .. wymin .. '..' .. wymax)")
print(r.command(cmd))
r.close()
