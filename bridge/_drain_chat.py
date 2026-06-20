"""Drain the chat buffer."""
import sys
sys.path.insert(0, 'bridge')
from rcon_client import RconClient
from _claude import call_mod

r = RconClient(); r.connect()
res = call_mod(r, 'drain_chat')
print(f"messages: {res.get('count', 0)}")
for m in res.get('messages', []):
    print(f"  [{m.get('player', '?')}] tick={m.get('tick')}  '{m.get('message')}'")
r.close()
