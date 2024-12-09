import asyncio
import logging

from bleak import BleakClient, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from .const import desk_service_uuid, desk_attribute_read, desk_attribute_write
from .protocol import Frame, DeskType, HeightData, HostType, Preset, Units, PresetDict, HeightMM

logger = logging.getLogger(__name__)


class Blesk:
    def __init__(self, device: BLEDevice) -> None:
        self._device = device

        self._client = BleakClient(device, services=[desk_service_uuid], disconnected_callback=self._disconnect_callback)
        
        self._listeners: list[asyncio.Queue] = []
        self._connection_cache: dict[HostType, Frame] = {}

    @property
    def name(self) -> str:
        return self._device.name
    
    @property
    def address(self) -> str:
        return self._device.address

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

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

        await self._valid_frame_callback(frame)

    def _disconnect_callback(self, client: BleakClient):
        logger.debug(f'Disconnected from {self.address}')

        self._connection_cache = {}

    async def _valid_frame_callback(self, frame: Frame) -> None:
        # Store in the cache
        self._connection_cache[frame.command] = frame

        # Call any subscribers
        to_remove = []

        async with asyncio.TaskGroup() as tg:
            for l in self._listeners:
                try:
                    tg.create_task(l.put(frame))
                except asyncio.QueueShutDown as e:
                    logger.warning(f'Listener queue was closed')
                    to_remove.append(l)

            # Remove all the shut down queues
            for r in to_remove:
                self.unsubscribe(r)

    def subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()

        self._listeners.append(q)

        return q
    
    def unsubscribe(self, queue) -> None:
        self._listeners.remove(queue)

    def __repr__(self) -> str:
        return f'Blesk(name="{self.name}", address="{self.address}")'

    async def send_frame(self, frame: Frame):
        logger.debug(f'Sending frame to {self.address}: {frame}')

        data = frame.to_bytes()
        logger.debug(f'Sending bytes to {self.address}: {data.hex()}')

        await self._client.write_gatt_char(desk_attribute_write, data)

    async def get_frame(self, kind: HostType, from_cache=True) -> Frame:
        # If not wait for the message
        logger.debug(f'Waiting for message of type {kind}')
        q = self.subscribe()

        while True:
            frame:Frame = await q.get()

            if frame.command == kind:
                logger.debug(f'Message wait for {kind} complete')
                self.unsubscribe(q)
                q.shutdown(immediate=True)
                return frame
            
            q.task_done()

    async def query(self, send: Frame, receive: HostType, from_cache=True):
        if from_cache and receive in self._connection_cache.keys():
            logger.debug(f'Message type {receive} retrived from cache')
            return self._connection_cache[receive]
        
        query_task = asyncio.create_task(self.get_frame(kind=receive))
        await self.send_frame(send)

        return await query_task

    async def wake(self):
        await self.send_frame(Frame(command=DeskType.BLE_WAKE))

    async def connect(self):
        await self._client.connect()
        await self._client.start_notify(char_specifier=desk_attribute_read, callback=self._data_callback)
        await self.wake()

    async def disconnect(self):
        await self._client.disconnect()

    async def __aenter__(self):
        await self.connect()
        return self

    async def __aexit__(self, exc_type, exc, tb):
        await self.disconnect()
        return False

    async def get_units(self) -> Units:
        frame = await self.query(send=Frame(command=DeskType.SETTINGS), receive=HostType.UNITS)

        u = Units(frame.params[0])

        return u

    async def get_height_mm(self) -> int:
        units_task = asyncio.create_task(self.get_units())
        height_task = asyncio.create_task(self.query(send=Frame(command=DeskType.BLE_WAKE), receive=HostType.HEIGHT))

        units = await units_task
        frame = await height_task

        return HeightData(frame.params[0:2]).decode_as(units).as_mm.as_float

    async def goto_mm(self, mm: int):
        units = await self.get_units()

        if units == Units.MM:
            await self.send_frame(Frame(command=DeskType.GOTO_HEIGHT, params=HeightMM(mm).encode.data))
        else:
            await self.send_frame(Frame(command=DeskType.GOTO_HEIGHT, params=HeightMM(mm).as_in.encode.data))

    async def goto_preset(self, preset: Preset):
        preset_info = PresetDict[preset]

        await self.send_frame(Frame(command=preset_info.goto))
