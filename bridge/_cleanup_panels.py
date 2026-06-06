import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
print(call_mod(r, '_cleanup_panels', interface='claude_rl'))
r.close()
