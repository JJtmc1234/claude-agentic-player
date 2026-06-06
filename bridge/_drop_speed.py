"""Drop game.speed back to 1.0 and stop any in-progress simulate."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient

r = RconClient(); r.connect()
print(r.command("/silent-command "
                "if storage.arena then storage.arena.simulating = false end; "
                "game.tick_paused = false; "
                "game.speed = 1.0; "
                "rcon.print('speed=' .. game.speed .. ' sim=' .. tostring(storage.arena and storage.arena.simulating))"))
r.close()
