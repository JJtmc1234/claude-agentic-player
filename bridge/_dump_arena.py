import sys, json
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
res = call_mod(r, 'arena_debug_state', interface='claude_rl')
print(json.dumps(res, indent=2))
r.close()
