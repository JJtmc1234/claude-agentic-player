"""Steam-power planner for the Claude Agentic Player (pure, RCON-free).

Given a target electric load (typically driven by a count of electric mining
drills), compute how many steam-engines, boilers, and offshore-pumps are needed
to sustain it, plus the coal burn rate. All functions are pure — no RCON, no
I/O, no side effects — so they are safe to unit-test and to call from planners.

Constants are Factorio 2.0 (Space Age) base values, verified against the wiki
2026-07-05 (wiki.factorio.com):
  - steam-engine:  900 kW output, consumes 30 steam/s
  - boiler:        1.8 MW, converts 60 water/s -> 60 steam/s  (=> feeds 2 engines)
  - offshore-pump: 1200 water/s                               (=> feeds 20 boilers)
  - electric-mining-drill: 90 kW draw while operating
  - coal fuel value: 4 MJ/item

Chain ratio at full load: 1 pump : 20 boilers : 40 engines = 36 MW.

Author: employee-3 (builder). This is the CODE-side of the POWER role while the
in-game pane is gated; the live build reuses these numbers for sizing.
"""
from __future__ import annotations

import math
from typing import Dict

# ---- Factorio 2.0 base constants (see module docstring for sources) ----
STEAM_ENGINE_KW = 900          # max electric output of one steam-engine
STEAM_ENGINE_STEAM_PER_S = 30  # steam consumed by one engine at full output
BOILER_STEAM_PER_S = 60        # steam produced by one boiler (=> 2 engines)
BOILER_WATER_PER_S = 60        # water consumed by one boiler (1:1 with steam)
BOILER_ENERGY_MW = 1.8         # boiler fuel-energy draw
OFFSHORE_PUMP_WATER_PER_S = 1200  # water produced by one offshore-pump
ELECTRIC_DRILL_KW = 90         # draw of one electric-mining-drill while running
COAL_FUEL_MJ = 4.0             # energy per coal item

# Derived integer ratios (kept explicit for readability of the plan)
ENGINES_PER_BOILER = BOILER_STEAM_PER_S // STEAM_ENGINE_STEAM_PER_S      # 2
BOILERS_PER_PUMP = OFFSHORE_PUMP_WATER_PER_S // BOILER_WATER_PER_S       # 20
# Coal per boiler per minute: 1.8 MJ/s / 4 MJ = 0.45 coal/s -> 27 coal/min
COAL_PER_BOILER_PER_MIN = (BOILER_ENERGY_MW / COAL_FUEL_MJ) * 60.0       # 27.0


def electric_load(n_electric_drills: int, other_kw: float = 0.0) -> float:
    """Total electric load in kW for `n_electric_drills` plus any `other_kw`.

    Only electric-mining-drills draw here; burner drills and furnaces consume
    fuel, not power, so they are not counted (pass their equivalents, if any,
    via `other_kw`).
    """
    if n_electric_drills < 0:
        raise ValueError("n_electric_drills must be >= 0")
    if other_kw < 0:
        raise ValueError("other_kw must be >= 0")
    return n_electric_drills * ELECTRIC_DRILL_KW + other_kw


def engines_needed(load_kw: float) -> int:
    """Steam-engines required to supply `load_kw` (ceil of load / 900 kW)."""
    if load_kw <= 0:
        return 0
    return math.ceil(load_kw / STEAM_ENGINE_KW)


def boilers_needed(load_kw: float) -> int:
    """Boilers required for `load_kw` (each boiler feeds 2 engines)."""
    eng = engines_needed(load_kw)
    if eng <= 0:
        return 0
    return math.ceil(eng / ENGINES_PER_BOILER)


def water_pumps_needed(load_kw: float) -> int:
    """Offshore-pumps required for `load_kw` (each pump feeds 20 boilers)."""
    boilers = boilers_needed(load_kw)
    if boilers <= 0:
        return 0
    return math.ceil(boilers / BOILERS_PER_PUMP)


def coal_per_min(load_kw: float) -> float:
    """Coal items per minute burned by the boilers sustaining `load_kw`."""
    return round(boilers_needed(load_kw) * COAL_PER_BOILER_PER_MIN, 2)


def plan_power(n_drills: int, other_kw: float = 0.0) -> Dict[str, float]:
    """Full power plan to run `n_drills` electric drills (+ optional other_kw).

    Returns a dict with the load and the counts of each generation component,
    plus the coal burn rate and the spare capacity the plan leaves (because the
    counts are rounded up, the installed engines usually exceed the exact load).
    """
    load = electric_load(n_drills, other_kw)
    engines = engines_needed(load)
    boilers = boilers_needed(load)
    pumps = water_pumps_needed(load)
    capacity_kw = engines * STEAM_ENGINE_KW
    return {
        "n_drills": n_drills,
        "load_kw": load,
        "engines": engines,
        "boilers": boilers,
        "pumps": pumps,
        "coal_per_min": round(boilers * COAL_PER_BOILER_PER_MIN, 2),
        "capacity_kw": capacity_kw,
        "spare_kw": capacity_kw - load,
    }
