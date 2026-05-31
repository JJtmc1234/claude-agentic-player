"""
Shared identity + helper for calling the claude-companion mod's remote interface.

Why a separate file: the unit_number (engine ID), human-facing name, and the
remote.call wrapper are needed by every bridge script. Centralizing means
renaming the character or tweaking the call signature is a one-line edit.
"""

from __future__ import annotations

import json

UNIT = 454
NAME = "The Embodiment of Claude"
NAME_SHORT = "TEoC"


def lua_repr(v: object) -> str:
    """Serialize a Python value as a Lua expression."""
    if isinstance(v, bool):
        return "true" if v else "false"
    if isinstance(v, (int, float)):
        return str(v)
    if isinstance(v, str):
        return "'" + v.replace("\\", "\\\\").replace("'", "\\'") + "'"
    if v is None:
        return "nil"
    raise TypeError(f"lua_repr: unsupported {type(v).__name__}")


def call_mod(r, fn: str, *args, interface: str = "claude", retries: int = 2) -> dict:
    """Call remote.call(interface, fn, *args) via RCON; parse JSON response.
    Default interface is 'claude'; pass interface='claude_rl' for arena_* fns.

    Retries on empty responses (which Factorio returns when an internal Lua
    function errors silently — usually a transient race during heavy load).
    """
    import time as _time
    arg_str = ",".join(lua_repr(a) for a in args)
    sep = "," if arg_str else ""
    cmd = (
        f"/silent-command rcon.print(helpers.table_to_json("
        f"remote.call('{interface}','{fn}'{sep}{arg_str})))"
    )
    last_err = None
    for attempt in range(retries + 1):
        try:
            out = r.command(cmd).strip()
        except Exception as e:
            last_err = f"RCON exception: {e}"
            if attempt < retries:
                _time.sleep(0.5 * (attempt + 1))
                continue
            raise RuntimeError(f"mod call {interface}.{fn} {last_err}")
        if out.startswith("Cannot execute"):
            raise RuntimeError(f"mod call {interface}.{fn} failed: {out}")
        if not out:
            last_err = "empty response"
            if attempt < retries:
                _time.sleep(0.5 * (attempt + 1))
                continue
            raise RuntimeError(f"empty response from mod call {interface}.{fn} after {retries+1} attempts")
        return json.loads(out)


def get_inventory_count(r, item_name: str) -> int:
    """Quick read of how many of item_name TEoC has in main inventory."""
    item_lua = lua_repr(item_name)
    cmd = (
        f"/silent-command local c=game.get_entity_by_unit_number({UNIT}) "
        f"local inv=c and c.valid and c.get_main_inventory() "
        f"rcon.print((inv and inv.get_item_count({item_lua})) or 0)"
    )
    out = r.command(cmd).strip()
    try:
        return int(out)
    except ValueError:
        return 0
