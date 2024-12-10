import asyncio
import functools
import click

from .discover import discover
from .protocol import Preset

async def get_desk():
    devices = await discover(timeout=1)
    
    if (len(devices) == 0):
        return None
    
    return devices[0]

def make_sync(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging, ignores --verbose')
@click.option('--verbose', is_flag=True, help='Enable verbose logging')
@make_sync
async def cli(debug: bool, verbose: bool):
    if debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    elif verbose:
        import logging
        logging.basicConfig(level=logging.INFO)

@cli.group()
@make_sync
async def go():
    pass

@go.command(name='preset')
@click.argument('preset', type=int)
@make_sync
async def go_preset(preset: int):
    try:
        p = Preset(preset)
    except ValueError:
        print(f'{preset} is not a valid preset')

    dev = await get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        await dev.goto_preset(p)

@go.command()
@click.argument('millimeters', type=int)
@make_sync
async def height(millimeters: int):
    h = int(millimeters)

    dev = await get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

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
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        height = await dev.get_height_mm()
        
    print(f"Current height is {height}mm")

@get.command(name='preset')
@click.argument('preset')
@make_sync
async def get_preset(preset: str):
    """Get the PRESET height.

    PRESET is the number of the preset, or 'all' to get all presets.
    """
    get_list = []

    if preset == 'all':
        for p in Preset:
            get_list.append(p)
    else:
        try:
            get_list.append(Preset(int(preset)))
        except ValueError:
            print(f'{preset} is not a valid preset')
            return

    dev = await get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        # Getting one will get all, so the later iterations will be instantly served from cache
        # for this reason we don't do it concurrently
        for p in get_list:
            height = await dev.get_preset_mm(p)

            print(f"Preset {p.name.lower()} height is {height}mm")
