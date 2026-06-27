"""Mega-run: walk to copper, hand-mine ore, walk back, smelt, craft lab,
place + queue research, verify."""
import sys, time
sys.path.insert(0, 'bridge')
from agent import Agent

with Agent.connect() as a:
    # Stage 1: walk to copper patch
    print('=== walk to copper patch (87, 42) ===')
    a.movement.walk_chunked(87, 42, chunk_size=30, radius_final=2)
    print(f'  at {a.position()}')

    # Stage 2: hand-mine 12 copper-ore
    print('\n=== hand-mine 12 copper-ore ===')
    got = a.mining.mine_nearest('copper-ore', max_radius=10, n=12)
    print(f'  mined {got}')
    inv = a.inventory.list()
    print(f'  copper-ore in inv: {inv.get("copper-ore", 0)}')

    # Stage 3: walk back to base (copper furnace at -11, 52)
    print('\n=== walk back to base ===')
    a.movement.walk_chunked(-11, 53, chunk_size=30, radius_final=2)
    print(f'  at {a.position()}')

    # Stage 4: load copper furnace with ore + coal
    print('\n=== load copper furnace ===')
    body = (
        f"local c=game.get_entity_by_unit_number({a.unit}); "
        "local s=c.surface; local ci=c.get_main_inventory(); "
        "local f=s.find_entities_filtered{position={-11, 52}, radius=0.6, name='stone-furnace'}[1]; "
        "if not f then rcon.print('NO furnace'); return end; "
        "local src=f.get_inventory(defines.inventory.furnace_source); "
        "local have_ore = ci.get_item_count('copper-ore'); "
        "local moved_ore = src.insert{name='copper-ore', count=have_ore}; "
        "ci.remove{name='copper-ore', count=moved_ore}; "
        "local fi = f.get_fuel_inventory(); "
        "local have_coal = ci.get_item_count('coal'); "
        "local moved_coal = fi.insert{name='coal', count=math.min(3, have_coal)}; "
        "ci.remove{name='coal', count=moved_coal}; "
        "rcon.print('+' .. moved_ore .. ' ore +' .. moved_coal .. ' coal (st=' .. f.status .. ')')"
    )
    print('  ' + a.rcon.command('/silent-command ' + body).strip())

    # Stage 5: wait for smelt + take plates
    print('\n=== wait 25s for smelt ===')
    time.sleep(25)
    take_body = (
        f"local c=game.get_entity_by_unit_number({a.unit}); "
        "local s=c.surface; local ci=c.get_main_inventory(); "
        "local f=s.find_entities_filtered{position={-11, 52}, radius=0.6, name='stone-furnace'}[1]; "
        "local res = f.get_inventory(defines.inventory.furnace_result); "
        "local have = res.get_item_count('copper-plate'); "
        "local moved = ci.insert{name='copper-plate', count=have}; "
        "res.remove{name='copper-plate', count=moved}; "
        "rcon.print('took ' .. moved .. ' copper-plate from furnace')"
    )
    print('  ' + a.rcon.command('/silent-command ' + take_body).strip())

    inv = a.inventory.list()
    print(f'  copper-plate: {inv.get("copper-plate", 0)}  iron-plate: {inv.get("iron-plate", 0)}')

    # Stage 6: craft lab + packs
    print('\n=== craft chain ===')
    chain = [
        ('iron-gear-wheel', 15),
        ('copper-cable', 6),     # 6 batches × 2 = 12 cables, need 6 copper plates
        ('electronic-circuit', 4),
        ('transport-belt', 5),   # 5 batches × 2 = 10 belts
        ('lab', 1),
        ('automation-science-pack', 5),
    ]
    for recipe, count in chain:
        print(f'  craft {recipe} x{count}...')
        st = a.inventory.craft(recipe, count, timeout_s=120)
        print(f'    {st.get("status")}')
        if st.get('status') == 'error':
            print(f'    error: {st.get("error")}')

    inv = a.inventory.list()
    print(f'\n  lab: {inv.get("lab", 0)}  science packs: {inv.get("automation-science-pack", 0)}')

    # Stage 7: walk to power area, place lab near pole
    print('\n=== walk to pole (-44.5, 37.5) ===')
    a.movement.walk_chunked(-43, 38, chunk_size=30, radius_final=2)
    print(f'  at {a.position()}')

    # Place lab 2-3 tiles from pole
    print('\n=== place lab ===')
    lab = a.placement.place('lab', -41, 39, 0, clear_blockers=True, step_aside=True)
    print(f'  {lab}')

    # Insert science packs into lab + queue research
    if lab.get('ok'):
        lx, ly = lab['position']['x'], lab['position']['y']
        print('\n=== insert science packs + force research ===')
        body = (
            f"local c=game.get_entity_by_unit_number({a.unit}); "
            "local s=c.surface; local ci=c.get_main_inventory(); "
            f"local lab = s.find_entities_filtered{{position={{{lx},{ly}}}, radius=1, name='lab'}}[1]; "
            "if not lab then rcon.print('NO LAB'); return end; "
            "local labinv = lab.get_inventory(defines.inventory.lab_input); "
            "local have = ci.get_item_count('automation-science-pack'); "
            "local moved = labinv.insert{name='automation-science-pack', count=have}; "
            "ci.remove{name='automation-science-pack', count=moved}; "
            "rcon.print('inserted ' .. moved .. ' science-pack into lab'); "
            # Force-add a research if none is queued
            "local force = lab.force; "
            "if not force.current_research then "
            "  force.add_research('automation') "
            "end; "
            "rcon.print('current research: ' .. tostring(force.current_research and force.current_research.name or 'none')); "
            "rcon.print('lab status=' .. lab.status .. ' active=' .. tostring(lab.active))"
        )
        print('  ' + a.rcon.command('/silent-command ' + body).strip())

        # Wait + verify
        time.sleep(20)
        body2 = (
            f"local s = game.surfaces['nauvis']; "
            f"local lab = s.find_entities_filtered{{position={{{lx},{ly}}}, radius=1, name='lab'}}[1]; "
            "local research = lab.force.current_research; "
            "rcon.print(string.format('lab status=%d research=%s progress=%.2f', "
            "  lab.status, "
            "  research and research.name or 'none', "
            "  research and lab.force.research_progress or 0))"
        )
        print('\n=== after 20s ===')
        print('  ' + a.rcon.command('/silent-command ' + body2).strip())
