import asyncio
import configparser
import functools
import logging
import os

import click
from bleak import BleakScanner
from platformdirs import PlatformDirs

from blesk.desk import Blesk

from .discover import discover
from .protocol import LightColor, Preset

dirs = PlatformDirs("blesk", "smarthall", ensure_exists=True)

logger = logging.getLogger(__name__)


class DeskConfig:
    def __init__(self, configfile=None, profile="default"):
        self._profile = profile
        if configfile is None:
            configfile = os.path.join(dirs.user_config_dir, "config.ini")

        self._configfile = configfile

        config = configparser.ConfigParser()
        config.read(configfile)

        self._config = config

        if not self._config.has_section(self._profile):
            self._config.add_section(self._profile)
            self._dirty = True

    def save(self):
        with open(self._configfile, "w") as configfile:
            self._config.write(configfile)

    @property
    def desk_address(self):
        return self._config.get(self._profile, "address", fallback=None)

    @desk_address.setter
    def desk_address(self, addr):
        self._config.set(self._profile, "address", addr)

    async def get_desk(self):
        if self.desk_address:
            bledev = await BleakScanner.find_device_by_address(
                self.desk_address, timeout=5
            )
            if bledev is None:
                logger.error(f'Configured desk "{self.desk_address}", not found.')

            return Blesk(bledev)

        devices = await discover(timeout=5)
        if self.desk_address is None and len(devices) == 1:
            logger.warning(
                'No configured desk, use "blesk set desk [ADDRESS]" to set one. Using only found device.'
            )
            return Blesk(devices[0])

        logger.error(f"No desk configured, and {len(devices)} found")
        return None


pass_config = click.make_pass_decorator(DeskConfig)


def make_sync(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        return asyncio.run(func(*args, **kwargs))

    return wrapper


@click.group()
@click.option("--debug", is_flag=True, help="Enable debug logging, ignores --verbose")
@click.option("--verbose", is_flag=True, help="Enable verbose logging")
@click.option(
    "--profile",
    help="The profile from the config file to use",
    default="default",
    type=str,
)
@click.option("--config", help="The config file to use", type=str)
@make_sync
@click.pass_context
async def cli(ctx, debug: bool, verbose: bool, config: str, profile: str):
    if debug:
        logging.basicConfig(level=logging.DEBUG)
    elif verbose:
        logging.basicConfig(level=logging.INFO)

    ctx.obj = DeskConfig(config, profile)


@cli.group()
@make_sync
async def go():
    pass


@go.command(name="preset")
@click.argument("preset", type=int)
@make_sync
@pass_config
async def go_preset(config: DeskConfig, preset: int):
    try:
        p = Preset(preset)
    except ValueError:
        print(f"{preset} is not a valid preset")

    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        await dev.goto_preset(p)


@go.command()
@click.argument("millimeters", type=int)
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

    print("|-----------------------------------------------------|")
    print("| Address                  | Name                     |")
    print("|-----------------------------------------------------|")

    for d in devices:
        print(f"| {d.address.ljust(24)} | {d.name.ljust(24)} |")

    print("|-----------------------------------------------------|")


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


@get.command(name="preset")
@click.argument("preset")
@make_sync
@pass_config
async def get_preset(config: DeskConfig, preset: str):
    """Get the PRESET height.

    PRESET is the number of the preset, or 'all' to get all presets.
    """
    if preset == "all":
        get_list = [p for p in Preset]
    else:
        try:
            get_list = [Preset(int(preset))]
        except ValueError:
            print(f"{preset} is not a valid preset")
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


@get.command(name="lock")
@make_sync
@pass_config
async def get_lock(config: DeskConfig):
    """Get the child-lock state."""
    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        locked = await dev.get_lock()

    print(f"Lock is {'on' if locked else 'off'}")


@get.command(name="light")
@make_sync
@pass_config
async def get_light(config: DeskConfig):
    """Get the light state."""
    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        on = await dev.get_lighting()

    print(f"Light is {'on' if on else 'off'}")


@get.command(name="brightness")
@make_sync
@pass_config
async def get_brightness(config: DeskConfig):
    """Get the light brightness."""
    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        percent = await dev.get_brightness()

    print(f"Brightness is {percent}")


@get.command(name="color")
@make_sync
@pass_config
async def get_color(config: DeskConfig):
    """Get the light colour."""
    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        color = await dev.get_light_color()

    print(f"Light colour is {color.name.lower()}")


@cli.group()
@make_sync
async def set():
    pass


@set.command()
@make_sync
@click.argument("address")
@pass_config
async def desk(config: DeskConfig, address: str):
    # TODO Check validity of the address
    # TODO Warn the user if the desk is not present

    config.desk_address = address
    config.save()


@set.command(name="lock")
@click.argument("state", type=click.Choice(["on", "off"]))
@make_sync
@pass_config
async def set_lock(config: DeskConfig, state: str):
    """Set the child lock on or off."""
    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        await dev.set_lock(state == "on")

    print(f"Lock set to {state}")


@set.command(name="light")
@click.argument("state", type=click.Choice(["on", "off"]))
@make_sync
@pass_config
async def set_light(config: DeskConfig, state: str):
    """Set the light on or off."""
    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        await dev.set_lighting(state == "on")

    print(f"Light set to {state}")


@set.command(name="brightness")
@click.argument("percent", type=click.IntRange(0, 100))
@make_sync
@pass_config
async def set_brightness(config: DeskConfig, percent: int):
    """Set the light brightness (0-100)."""
    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        await dev.set_brightness(percent)

    print(f"Brightness set to {percent}")


@set.command(name="color")
@click.argument(
    "colour",
    type=click.Choice(["off", "white", "red", "green", "blue", "yellow", "party"]),
)
@make_sync
@pass_config
async def set_color(config: DeskConfig, colour: str):
    """Set the light colour."""
    dev = await config.get_desk()
    if dev is None:
        print("Could not find any devices...")
        return

    async with dev:
        await dev.set_light_color(LightColor[colour.upper()])

    print(f"Light colour set to {colour}")
