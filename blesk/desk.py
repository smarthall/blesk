import asyncio
import logging

from enum import Enum

from bleak import BleakClient, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from .const import desk_service_uuid, desk_attribute_read, desk_attribute_write
from .protocol import Frame, DeskType, HeightData, HostType, Units

logger = logging.getLogger(__name__)


class Blesk:
    def __init__(self, device:BLEDevice) -> None:
        self._device = device

        self._client = BleakClient(device, services=[desk_service_uuid], disconnected_callback=self._disconnect_callback)
        
        self._listeners:list[asyncio.Queue] = []

    async def _data_callback(self, sender: BleakGATTCharacteristic, data: bytearray) -> None:
        # Check the message is from where we expect
        if (sender.uuid != desk_attribute_read):
            logger.warning(f'Received unexpected data from service: {sender}')
            return

        logger.debug(f'Bytes received from {self.address}: {data.hex()}')

        try:
            frame = Frame.from_bytes(data)
            logger.debug(f'Frame received from {self.address}: {frame}')
        except Exception as e:
            logger.warning(f'Exception while parsing message "{data.hex()}" from {self.address}: {e}')
            return

        await self._frame_callback(frame)

    async def _frame_callback(self, frame: Frame) -> None:
        to_remove = []

        for l in self._listeners:
            try:
                await l.put(frame)
            except asyncio.QueueShutDown as e:
                to_remove.append(l)

        # Remove all the shut down queues
        for r in to_remove:
            self._listeners.remove(r)

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()

        self._listeners.append(q)

        return q

    def _disconnect_callback(self, client: BleakClient):
        logger.debug(f'Disconnected from {self.address}')

    @property
    def name(self) -> str:
        return self._device.name
    
    @property
    def address(self) -> str:
        return self._device.address

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    def __repr__(self) -> str:
        return f'Blesk(name="{self.name}", address="{self.address}")'

    async def send_bytes(self, data: bytes):
        logger.debug(f'Bytes sent to {self.address}: {data.hex()}')
        await self._client.write_gatt_char(desk_attribute_write, data)

    async def send_frame(self, frame: Frame):
        logger.debug(f'Frame sent to {self.address}: {frame}')
        await self.send_bytes(frame.to_bytes())

    async def get_frame(self, kind: HostType) -> Frame:
        q = self.subscribe()

        while True:
            frame:Frame = await q.get()

            if (frame.command == kind):
                q.shutdown()
                return frame

    async def wake(self):
        await self.send_frame(Frame(command=DeskType.BLE_WAKE))

    async def connect(self):
        await self._client.connect()
        await self._client.start_notify(char_specifier=desk_attribute_read, callback=self._data_callback)

    async def disconnect(self):
        await self._client.disconnect()

    async def move_one(self):
        await self.send_frame(Frame(command=DeskType.MOVE_1))

    async def settings(self):
        await self.send_frame(Frame(command=DeskType.SETTINGS))

    async def get_units(self) -> Units:
        task = asyncio.create_task(self.get_frame(kind=HostType.UNITS))

        await self.settings()

        frame = await task

        u = Units(frame.params[0])

        return u

    async def get_height_mm(self) -> int:
        units_task = asyncio.create_task(self.get_units())
        height_task = asyncio.create_task(self.get_frame(kind=HostType.HEIGHT))

        # Wake makes the desk start sending height updates
        await self.wake()

        units = await units_task
        frame = await height_task

        return HeightData(frame.params[0:2]).decode_as(units).as_mm.as_float
