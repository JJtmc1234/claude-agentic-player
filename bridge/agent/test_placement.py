"""Pure-Python unit tests for placement + core (no RCON / no server needed).

Covers:
  - Placement._mine_resources generates the decrement-safe Lua (does NOT
    unconditionally destroy a resource tile — the ore-tile bug fix).
  - Agent._resolve_named_unit contract ({ name -> unum } -> int | None) that
    backs Agent.connect_named.

Run with: python bridge/agent/test_placement.py
"""
from __future__ import annotations
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_BRIDGE = _HERE.parent
if str(_BRIDGE) not in sys.path:
    sys.path.insert(0, str(_BRIDGE))

from agent.placement import Placement
from agent.core import Agent


_PASS = 0
_FAIL = 0


def check(name, cond):
    global _PASS, _FAIL
    if cond:
        _PASS += 1
        print(f"  PASS  {name}")
    else:
        _FAIL += 1
        print(f"  FAIL  {name}")


# ---- test doubles ----

class FakeRcon:
    def __init__(self):
        self.commands = []

    def command(self, cmd):
        self.commands.append(cmd)
        return ""


class FakeAgent:
    """Minimal stand-in exposing what Placement._mine_resources touches."""
    def __init__(self):
        self.unit = 454
        self.rcon = FakeRcon()


def last_mine_body(kind="2x2"):
    a = FakeAgent()
    p = Placement(a)
    p._mine_resources(10.0, 20.0, kind=kind)
    return a.rcon.commands[-1]


def main():
    print("Placement._mine_resources decrement-safety:")
    body = last_mine_body("2x2")

    # The command must actually have been issued.
    check("emits a /silent-command", body.startswith("/silent-command "))
    # Decrement path present.
    check("decrements amount (e.amount = e.amount - 1)",
          "e.amount = e.amount - 1" in body)
    # Guard on amount > 1 present.
    check("guards on e.amount > 1", "e.amount > 1" in body)
    # Still destroys when depleted.
    check("destroys when depleted (else e.destroy())", "e.destroy()" in body)
    # The guard must come BEFORE the destroy (destroy is the else branch),
    # i.e. destroy is no longer unconditional.
    check("guard precedes destroy (destroy is conditional)",
          body.index("e.amount > 1") < body.index("e.destroy()"))
    # Regression: the pre-fix code ended the resource loop with an
    # unconditional "end; e.destroy()". Ensure that exact shape is gone.
    check("no unconditional destroy after products loop",
          "end; e.destroy()" not in body)
    # Products are still inserted into the character inventory.
    check("still inserts mined products", "ci.insert{name=p.name" in body)

    print("Placement._mine_resources bbox half-extent by kind:")
    body_1x1 = last_mine_body("1x1")
    body_3x3 = last_mine_body("3x3")
    # 1x1 -> half 0.5 => area corner 9.5 ; 3x3 -> half 1.5 => corner 8.5
    check("1x1 uses 0.5 half-extent", "9.5" in body_1x1)
    check("3x3 uses 1.5 half-extent", "8.5" in body_3x3)

    print("Agent._resolve_named_unit contract ({name -> unum}):")
    check("resolves an existing name",
          Agent._resolve_named_unit({"main": 454, "helper-1": 777}, "helper-1") == 777)
    check("int-coerces a string unum",
          Agent._resolve_named_unit({"main": "454"}, "main") == 454)
    check("missing name -> None",
          Agent._resolve_named_unit({"main": 454}, "ghost") is None)
    check("non-dict input -> None",
          Agent._resolve_named_unit([454], "main") is None)
    check("empty mapping -> None",
          Agent._resolve_named_unit({}, "main") is None)
    check("non-int-coercible value -> None",
          Agent._resolve_named_unit({"main": "not-a-number"}, "main") is None)

    print()
    print(f"TOTAL: {_PASS} passed, {_FAIL} failed")
    if _FAIL:
        sys.exit(1)


if __name__ == "__main__":
    main()
