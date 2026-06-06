"""Force a server save via RCON."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
print(r.command("/silent-command game.server_save('latest_autosave')"))
print(r.command("/silent-command rcon.print('saved at tick ' .. game.tick)"))
r.close()
