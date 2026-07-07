"""Pure-assert tests for power_plan (no RCON, no I/O).

Run: python bridge/agent/test_power_plan.py  (prints OK on success)
Also importable/discoverable by pytest (test_* functions).
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import power_plan as pp  # noqa: E402


def test_constants_are_consistent():
    # Ratios derived from base constants must be the classic 2.0 chain.
    assert pp.ENGINES_PER_BOILER == 2
    assert pp.BOILERS_PER_PUMP == 20
    # 1.8 MJ/s over 4 MJ/coal * 60 s = 27 coal/min per boiler.
    assert abs(pp.COAL_PER_BOILER_PER_MIN - 27.0) < 1e-9


def test_electric_load():
    assert pp.electric_load(0) == 0
    assert pp.electric_load(1) == 90
    assert pp.electric_load(10) == 900
    assert pp.electric_load(10, other_kw=100) == 1000
    # negative inputs are rejected
    for bad in ((-1, 0), (1, -5)):
        try:
            pp.electric_load(*bad)
            assert False, "expected ValueError"
        except ValueError:
            pass


def test_engines_needed():
    assert pp.engines_needed(0) == 0
    assert pp.engines_needed(1) == 1          # ceil, any positive load -> >=1
    assert pp.engines_needed(900) == 1
    assert pp.engines_needed(901) == 2
    assert pp.engines_needed(1800) == 2
    assert pp.engines_needed(1801) == 3


def test_boilers_needed():
    assert pp.boilers_needed(0) == 0
    assert pp.boilers_needed(900) == 1        # 1 engine -> 1 boiler
    assert pp.boilers_needed(1800) == 1       # 2 engines -> 1 boiler
    assert pp.boilers_needed(1801) == 2       # 3 engines -> 2 boilers
    assert pp.boilers_needed(3600) == 2       # 4 engines -> 2 boilers


def test_water_pumps_needed():
    assert pp.water_pumps_needed(0) == 0
    assert pp.water_pumps_needed(900) == 1
    # 40 engines -> 20 boilers -> exactly 1 pump
    assert pp.water_pumps_needed(40 * pp.STEAM_ENGINE_KW) == 1
    # 41 engines -> 21 boilers -> 2 pumps
    assert pp.water_pumps_needed(41 * pp.STEAM_ENGINE_KW) == 2


def test_coal_per_min():
    assert pp.coal_per_min(0) == 0
    assert pp.coal_per_min(900) == 27.0       # 1 boiler
    assert pp.coal_per_min(1801) == 54.0      # 2 boilers


def test_plan_power_small():
    p = pp.plan_power(10)                      # 10 drills = 900 kW
    assert p["load_kw"] == 900
    assert p["engines"] == 1
    assert p["boilers"] == 1
    assert p["pumps"] == 1
    assert p["coal_per_min"] == 27.0
    assert p["capacity_kw"] == 900
    assert p["spare_kw"] == 0


def test_plan_power_zero():
    p = pp.plan_power(0)
    assert p["engines"] == 0 and p["boilers"] == 0 and p["pumps"] == 0
    assert p["coal_per_min"] == 0
    assert p["spare_kw"] == 0


def test_plan_power_full_pump():
    # 400 drills = 36000 kW = 40 engines = 20 boilers = 1 pump.
    p = pp.plan_power(400)
    assert p["load_kw"] == 36000
    assert p["engines"] == 40
    assert p["boilers"] == 20
    assert p["pumps"] == 1
    assert p["coal_per_min"] == 540.0


def test_plan_power_rounds_up_capacity():
    # 11 drills = 990 kW -> 2 engines (1800 kW capacity) -> spare 810.
    p = pp.plan_power(11)
    assert p["engines"] == 2
    assert p["capacity_kw"] == 1800
    assert p["spare_kw"] == 810


def _run_all():
    fns = [v for k, v in sorted(globals().items())
           if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
    print(f"OK - {len(fns)} power_plan tests passed")


if __name__ == "__main__":
    _run_all()
