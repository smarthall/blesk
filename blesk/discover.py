from bleak import BleakScanner

from .const import desk_service_uuid
from .desk import Blesk


async def discover(timeout: float, scanner: BleakScanner | None = None) -> list[Blesk]:
    if scanner is None:
        scanner = BleakScanner()

    devices = await scanner.discover(
        timeout, return_adv=False, service_uuids=[desk_service_uuid]
    )
    return [Blesk(d) for d in devices]
