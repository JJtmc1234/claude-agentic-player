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


def call_mod(r, fn: str, *args) -> dict:
    """Call remote.call('claude', fn, *args) via RCON; parse JSON response."""
    arg_str = ",".join(lua_repr(a) for a in args)
    sep = "," if arg_str else ""
    cmd = (
        f"/silent-command rcon.print(helpers.table_to_json("
        f"remote.call('claude','{fn}'{sep}{arg_str})))"
    )
    out = r.command(cmd).strip()
    if not out:
        raise RuntimeError(f"empty response from mod call {fn}")
    if out.startswith("Cannot execute"):
        raise RuntimeError(f"mod call {fn} failed: {out}")
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
