import asyncio
import logging

from blesk import discover, Preset

async def main() -> None:
    # Setup Logger
    logging.basicConfig(level=logging.INFO)
    logging.getLogger('blesk').setLevel(logging.DEBUG)

    # Find devices
    print("Scanning...")
    devices = await discover(1)
    print(devices)

    if (len(devices) == 0):
        print("Could not find any devices...")
        return

    dev = devices[0]
    print(f"Connecting to {dev.address}")
    await dev.connect()

    await asyncio.sleep(1)

    await dev.goto_mm(722)

    print("Disconnecting...")
    await dev.disconnect()

asyncio.run(main())
