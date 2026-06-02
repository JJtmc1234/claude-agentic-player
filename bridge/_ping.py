import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
print("ping:", call_mod(r, 'ping', interface='claude'))
print("consts:", call_mod(r, 'arena_get_constants', interface='claude_rl'))
r.close()
