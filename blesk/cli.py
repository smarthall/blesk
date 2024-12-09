import asyncio
import functools
import click

from .discover import discover
from .protocol import Preset

async def get_desk():
    devices = await discover(timeout=1)
    
    if (len(devices) == 0):
        print("Could not find any devices...")
        return None
    
    return devices[0]

def make_sync(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

@click.group()
@make_sync
async def cli():
    pass

@cli.group()
@make_sync
async def go():
    pass

@go.command()
@click.argument('preset')
@make_sync
async def preset(preset: int):
    try:
        p = Preset(int(preset))
    except ValueError:
        print(f'{preset} is not a valid preset')

    dev = await get_desk()
    async with dev:
        await dev.goto_preset(p)

@go.command()
@click.argument('millimeters')
@make_sync
async def height(millimeters: int):
    try:
        h = int(millimeters)
    except ValueError:
        print(f'{millimeters} is not a valid height')

    dev = await get_desk()
    async with dev:
        await dev.goto_mm(mm=h)

@cli.group()
@make_sync
async def get():
    pass

@get.command()
@make_sync
async def current():
    dev = await get_desk()
    async with dev:
        height = await dev.get_height_mm()
        
    print(f"Height is {height}mm")

async def preset_all():
    task = {}

    dev = await get_desk()

    async with asyncio.TaskGroup() as tg:
        async with dev:
            for p in Preset:
                task[p] = tg.create_task(dev.get_preset_mm(p))

    for p in Preset:
        print(f"Preset {p.name} height is {task[p].result()}mm")

@get.command()
@click.argument('preset')
@make_sync
async def preset(preset: str):
    if preset == 'all':
        return await preset_all()

    try:
        p = Preset(int(preset))
    except ValueError:
        print(f'{preset} is not a valid preset')

    dev = await get_desk()
    async with dev:
        height = await dev.get_preset_mm(p)

    print(f"Preset {p.name} height is {height}mm")
