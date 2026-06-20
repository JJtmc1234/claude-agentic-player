"""Agent library for driving a free-standing Claude character.

Use as:
    from agent import Agent
    with Agent.connect() as a:
        a.walk_to(-14, 51)
        layout = a.place_drill_chain('iron-ore', -14.5, 50.5)  # auto-snap
        a.fuel(layout['drill'], 'wood', 5)

Each submodule is kept under 150 lines per project convention.
"""
from agent.core import Agent
from agent.geometry import (
    snap_2x2_center,
    snap_1x1_center,
    drill_drop_position,
    inserter_pickup_for_drill,
    inserter_pickup_for_furnace,
)
from agent.layouts import (
    LineSpec,
    plan_iron_smelt_line,
    plan_drill_to_chest,
    plan_power_chain,
)
from agent.power import build_power_chain

__all__ = [
    'Agent',
    'snap_2x2_center', 'snap_1x1_center',
    'drill_drop_position',
    'inserter_pickup_for_drill', 'inserter_pickup_for_furnace',
    'LineSpec',
    'plan_iron_smelt_line', 'plan_drill_to_chest', 'plan_power_chain',
    'build_power_chain',
]
