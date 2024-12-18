import asyncio
import functools
import configparser
import logging
from bleak import BleakScanner
import click
import os

from blesk.desk import Blesk
from bleak.backends.device import BLEDevice

from .discover import discover
from .protocol import Preset

from platformdirs import PlatformDirs
dirs = PlatformDirs("blesk", "smarthall", ensure_exists=True)

logger = logging.getLogger(__name__)

class DeskConfig:
    def __init__(self, configfile=None, profile='default'):
        self._profile = profile
        if configfile is None:
            configfile = os.path.join(dirs.user_config_dir, 'config.ini')

        self._configfile = configfile

        config = configparser.ConfigParser()
        config.read(configfile)

        self._config = config

        if not self._config.has_section(self._profile):
            self._config.add_section(self._profile)
            self._dirty = True

    def save(self):
        with open(self._configfile, 'w') as configfile:
            self._config.write(configfile)

    @property
    def desk_address(self):
        return self._config.get(self._profile, 'address', fallback=None)
    
    @desk_address.setter
    def desk_address(self, addr):
        self._config.set(self._profile, 'address', addr)

    async def get_desk(self):
        if self.desk_address:
            bledev = await BleakScanner.find_device_by_address(self.desk_address, timeout=5)
            if bledev is None:
                logger.error(f'Configured desk "{self.desk_address}", not found.')

            return Blesk(bledev)
        
        devices = await discover(timeout=5)
        if self.desk_address is None and len(devices) == 1:
            logger.warning('No configured desk, use "blesk set desk [ADDRESS]" to set one. Using only found device.')
            return Blesk(devices[0])
        
        logger.error(f'No desk configured, and {len(devices)} found')
        return None

pass_config = click.make_pass_decorator(DeskConfig)

def make_sync(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))
    return wrapper

@click.group()
@click.option('--debug', is_flag=True, help='Enable debug logging, ignores --verbose')
@click.option('--verbose', is_flag=True, help='Enable verbose logging')
@click.option('--profile', help='The profile from the config file to use', default='default', type=str)
@click.option('--config', help='The config file to use', type=str)
@make_sync
@click.pass_context
async def cli(ctx, debug: bool, verbose: bool, config: str, profile: str):
    if debug:
        import logging
        logging.basicConfig(level=logging.DEBUG)
    elif verbose:
        import logging
        logging.basicConfig(level=logging.INFO)
    
    ctx.obj = DeskConfig(config, profile)

@cli.group()
@make_sync
async def go():
    pass

@go.command(name='preset')
@click.argument('preset', type=int)
@make_sync
@pass_config
async def go_preset(config: DeskConfig, preset: int):
    try:
        p = Preset(preset)
    except ValueError:
        print(f'{preset} is not a valid preset')

    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        await dev.goto_preset(p)

@go.command()
@click.argument('millimeters', type=int)
@make_sync
@pass_config
async def height(config: DeskConfig, millimeters: int):
    h = int(millimeters)

    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        await dev.goto_mm(mm=h)

@cli.group()
@make_sync
async def list():
    pass

@list.command()
@make_sync
async def desks():
    devices = await discover(timeout=1)

    print('|-----------------------------------------------------|')
    print('| Address                  | Name                     |')
    print('|-----------------------------------------------------|')

    for d in devices:
        print(f'| {d.address.ljust(24)} | {d.name.ljust(24)} |')
    
    print('|-----------------------------------------------------|')

@cli.group()
@make_sync
async def get():
    pass

@get.command()
@make_sync
@pass_config
async def current(config: DeskConfig):
    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        height = await dev.get_height_mm()
        
    print(f"Current height is {height}mm")

@get.command(name='preset')
@click.argument('preset')
@make_sync
@pass_config
async def get_preset(config: DeskConfig, preset: str):
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

    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        # Getting one will get all, so the later iterations will be instantly served from cache
        # for this reason we don't do it concurrently
        for p in get_list:
            height = await dev.get_preset_mm(p)

            print(f"Preset {p.name.lower()} height is {height}mm")

@cli.group()
@make_sync
async def set():
    pass

@set.command()
@make_sync
@click.argument('address')
@pass_config
async def desk(config: DeskConfig, address: str):
    # TODO Check validity of the address
    # TODO Warn the user if the desk is not present

    config.desk_address = address
    config.save()
