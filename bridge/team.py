"""Multi-character team scaffolding for the Claude Agentic Player.

This is the Python side of the multi-character (agent-team) plan: once the mod
exposes `spawn_named_char` / `list_chars` / `remove_char` (mod 0.10.6+, tracked
by Employee-2), several helper characters can exist on the server at once, each
driven by its own `Agent` (see `agent.core.Agent.connect_named`).

STATUS: scaffolding. `bootstrap()` currently spawns helpers via the mod's remote
interface when it is available and otherwise degrades to a no-op with a clear
message; `assign_task` is a thin, synchronous dispatcher. Neither performs any
work at import time — importing this module has NO side effects (no RCON
connection, no server calls), so it is safe to import from tests / tooling.

Contract notes:
- The mod's `list_chars` returns a mapping { name -> unit_number }.
- The mod's `spawn_named_char(name, x, y)` is expected to create a character and
  register it under `name`. It is NOT yet deployed at time of writing, so
  `bootstrap()` guards every remote call and reports gracefully.
"""
from __future__ import annotations

import sys
from typing import Callable, Dict, List, Optional

from agent.core import Agent

# Default helper roster + rough spawn anchor near the asm/lab cluster.
# These are conservative placeholders; real spawn positions should come from a
# layout plan once multi-char is live.
DEFAULT_HELPERS: List[str] = ["helper-1", "helper-2", "helper-3"]
_SPAWN_ANCHOR = (-40.0, 45.0)


def bootstrap(
    names: Optional[List[str]] = None,
    password: Optional[str] = None,
    anchor: Optional[tuple] = None,
) -> Dict[str, Optional[int]]:
    """Spawn N helper characters via the mod and return { name -> unum or None }.

    For each requested name that does not already exist (per `list_chars`), this
    calls the mod's `spawn_named_char(name, x, y)` remote. If the mod does not
    yet expose the multi-char interface, it logs and returns the names mapped to
    None rather than raising — bootstrapping is best-effort scaffolding.

    This DOES open an RCON connection (that is its job); it is never invoked at
    import time. Returns the resolved roster so callers can `connect_named` each.
    """
    names = list(names if names is not None else DEFAULT_HELPERS)
    ax, ay = anchor if anchor is not None else _SPAWN_ANCHOR

    roster: Dict[str, Optional[int]] = {name: None for name in names}

    r = Agent._open_rcon(password)
    from _claude import call_mod  # local import: avoids side effects on module import

    try:
        existing = call_mod(r, "list_chars")  # contract: { name -> unum }
        if not isinstance(existing, dict):
            existing = {}
    except Exception as e:
        print(
            f"[team.bootstrap] list_chars unavailable ({e}); mod multi-char "
            f"interface not deployed yet — returning stub roster",
            file=sys.stderr,
        )
        return roster

    for i, name in enumerate(names):
        if name in existing:
            roster[name] = Agent._resolve_named_unit(existing, name)
            continue
        # Fan the spawn points out along x so helpers don't stack on one tile.
        sx, sy = ax + i * 2.0, ay
        try:
            res = call_mod(r, "spawn_named_char", name, sx, sy)
            # Expected shapes: {"unum": N} or {"unit_number": N} or bare int-ish.
            unum = None
            if isinstance(res, dict):
                unum = res.get("unum", res.get("unit_number"))
            roster[name] = int(unum) if unum is not None else None
        except Exception as e:
            print(
                f"[team.bootstrap] spawn_named_char({name!r}) failed ({e}); "
                f"leaving {name!r} unspawned",
                file=sys.stderr,
            )
            roster[name] = None

    return roster


def assign_task(
    char_name: str,
    task_fn: Callable[[Agent], object],
    password: Optional[str] = None,
) -> object:
    """Connect to `char_name` and run `task_fn(agent)` against it.

    `task_fn` is any callable taking a connected `Agent` and returning whatever
    it likes (its return value is passed through). Connection uses
    `Agent.connect_named`, which itself falls back to the single-character path
    if the mod's `list_chars` is unavailable — so this works today against the
    single live character and will scale to real helpers once multi-char ships.

    Synchronous for now: it blocks until `task_fn` returns. A future version can
    dispatch onto threads/processes so helpers act in parallel.
    """
    agent = Agent.connect_named(char_name, password=password)
    with agent:
        return task_fn(agent)
