"""Agent library for driving a free-standing Claude character.

Use as:
    from agent import Agent
    with Agent.connect() as a:
        a.walk_to(-14, 51)
        a.place('burner-mining-drill', -14.5, 50.5)   # auto-snaps to 2x2 center
        a.fuel.fuel('burner-mining-drill', -14.5, 50.5,
                    fuel_item='wood', want_amount=5)

To connect to a specific named character instead of the default one, use
`Agent.connect_named(name)` (a classmethod on Agent).

Each submodule is kept under 150 lines per project convention.
"""
from agent.core import Agent
from agent.geometry import (
    DIR_NORTH, DIR_EAST, DIR_SOUTH, DIR_WEST,
    snap_2x2_center,
    snap_1x1_center,
    snap_3x3_center,
    drill_drop_position,
    inserter_pickup_for_drill,
    inserter_pickup_for_furnace,
    opposite_direction,
    direction_toward,
    electric_drill_drop_position,
    electric_drill_output_tile,
)
from agent.layouts import (
    LineSpec,
    ArrayBOM,
    plan_iron_smelt_line,
    plan_drill_to_chest,
    plan_power_chain,
    plan_multi_drill_line,
    plan_steel_smelt,
    plan_wall_turret_segment,
    plan_belt_run,
    plan_electric_drill_array,
    electric_drill_array_bom,
)
from agent.power import build_power_chain

__all__ = [
    'Agent',
    # direction constants
    'DIR_NORTH', 'DIR_EAST', 'DIR_SOUTH', 'DIR_WEST',
    # geometry helpers
    'snap_2x2_center', 'snap_1x1_center', 'snap_3x3_center',
    'drill_drop_position',
    'inserter_pickup_for_drill', 'inserter_pickup_for_furnace',
    'opposite_direction', 'direction_toward',
    'electric_drill_drop_position', 'electric_drill_output_tile',
    # layouts / planners
    'LineSpec', 'ArrayBOM',
    'plan_iron_smelt_line', 'plan_drill_to_chest', 'plan_power_chain',
    'plan_multi_drill_line', 'plan_steel_smelt', 'plan_wall_turret_segment',
    'plan_belt_run', 'plan_electric_drill_array', 'electric_drill_array_bom',
    # power
    'build_power_chain',
]
