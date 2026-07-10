"""Lua silent-command wrappers — escape pitfalls collected the hard way.

Don't use Python `--` inline comments inside multi-line Python strings
(causes "unterminated string literal" syntax errors). Use `#` Python
comments or move comments to dedicated lines outside the Lua string.

Don't use `e.name:find(...)` colon-call syntax with non-trivial conditions
inside a one-liner RCON command — the parser sometimes mishandles it.
Use `string.find(e.name, '...')` instead.

Use `table.concat({...}, '\\n')` AFTER all rcon.print calls — never
embed `\\n` literally inside a single rcon.print, it doesn't display
across lines in RCON output.

`get_contents()` returns an array of {name, count} in Factorio 2.0 —
iterate with `ipairs`, not `pairs`. `pairs` still works on the array but
`ipairs` is the canonical/correct pattern for a sequence.
"""
from __future__ import annotations


def silent(body: str) -> str:
    """Wrap a Lua body in /silent-command. body should be a single line."""
    return "/silent-command " + body.strip()


def with_char(unum: int, body: str) -> str:
    """Wrap a Lua body that needs `c` (character entity) and `s` (surface)."""
    prefix = (
        f"local c = game.get_entity_by_unit_number({unum}); "
        f"if not c or not c.valid then rcon.print('NO CHAR'); return end; "
        f"local s = c.surface; "
        f"local ci = c.get_main_inventory(); "
    )
    return silent(prefix + body)


def find_named_entity(name: str, x: float, y: float, radius: float = 0.6) -> str:
    """Returns a Lua snippet that binds `e` to the named entity at (x, y)."""
    return (
        f"local e = s.find_entities_filtered{{position={{{x}, {y}}}, "
        f"radius={radius}, name='{name}'}}[1]"
    )
