"""Agent core — the connection + character context."""
from __future__ import annotations
import os
import sys
import time
from pathlib import Path
from typing import Optional

# Make sibling bridge modules importable
_HERE = Path(__file__).resolve().parent
_BRIDGE = _HERE.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from rcon_client import RconClient  # noqa: E402
from _claude import call_mod  # noqa: E402


class Agent:
    """Driver for a Claude-controlled character. Resolves character unit
    number from storage.claude_char_unum on connect."""

    def __init__(self, rcon: RconClient, unit: int):
        self.rcon = rcon
        self.unit = unit
        # Sub-modules attach themselves on demand (avoid circular imports).
        self._movement = None
        self._placement = None
        self._mining = None
        self._fuel = None
        self._inventory = None

    @classmethod
    def connect(cls, password: Optional[str] = None) -> 'Agent':
        if password is None:
            password = os.environ.get('FACTORIO_RCON_PASSWORD')
            if not password:
                raise RuntimeError(
                    "FACTORIO_RCON_PASSWORD not set — export it before calling Agent.connect()"
                )
        os.environ['FACTORIO_RCON_PASSWORD'] = password
        r = RconClient()
        r.connect()
        out = r.command("/silent-command rcon.print(tostring(storage.claude_char_unum))").strip()
        if out in ('nil', '', 'NO CHAR'):
            raise RuntimeError(
                "storage.claude_char_unum not set — spawn a character first with _spawn_claude.py"
            )
        try:
            unit = int(out)
        except ValueError:
            raise RuntimeError(f"could not parse char unum from: {out!r}")
        return cls(r, unit)

    # Context manager support
    def __enter__(self): return self
    def __exit__(self, *a):
        try:
            if self.rcon and self.rcon.sock:
                self.rcon.close()
        except Exception:
            pass

    # ---- shared low-level helpers ----

    def call(self, fn: str, *args, interface: str = 'claude') -> dict:
        """Call mod remote interface (claude or claude_rl) with retries."""
        return call_mod(self.rcon, fn, *args, interface=interface)

    def silent(self, body: str) -> str:
        """Run a /silent-command and return raw output."""
        return self.rcon.command("/silent-command " + body).strip()

    def position(self) -> tuple:
        out = self.silent(
            f"local c = game.get_entity_by_unit_number({self.unit}); "
            "rcon.print(string.format('%.2f,%.2f', c.position.x, c.position.y))"
        )
        x, y = out.split(',')
        return (float(x), float(y))

    def health(self) -> int:
        out = self.silent(
            f"local c = game.get_entity_by_unit_number({self.unit}); rcon.print(c.health)"
        )
        return int(float(out))

    # ---- lazy submodule attachment ----

    @property
    def movement(self):
        if self._movement is None:
            from agent.movement import Movement
            self._movement = Movement(self)
        return self._movement

    @property
    def placement(self):
        if self._placement is None:
            from agent.placement import Placement
            self._placement = Placement(self)
        return self._placement

    @property
    def mining(self):
        if self._mining is None:
            from agent.mining import Mining
            self._mining = Mining(self)
        return self._mining

    @property
    def fuel(self):
        if self._fuel is None:
            from agent.fuel import FuelManager
            self._fuel = FuelManager(self)
        return self._fuel

    @property
    def inventory(self):
        if self._inventory is None:
            from agent.inventory import Inventory
            self._inventory = Inventory(self)
        return self._inventory

    # Convenience pass-throughs (so a.walk_to() works without a.movement.walk_to)
    def walk_to(self, x, y, radius=1.5, timeout_s=120):
        return self.movement.walk_to(x, y, radius, timeout_s)

    def place(self, item_name, target_x, target_y, direction=0):
        return self.placement.place(item_name, target_x, target_y, direction)
