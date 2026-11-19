import asyncio
import logging

from bleak import BleakClient, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from .const import desk_service_uuid, desk_attribute_notify, desk_attribute_write
from .protocol import (
    Frame,
    DeskType,
    HeightData,
    HostType,
    LightColor,
    Preset,
    Units,
    PresetDict,
    HeightMM,
)

logger = logging.getLogger(__name__)


class Blesk:
    def __init__(self, device: BLEDevice | BleakClient) -> None:
        # Check if we received a BleakClient instance
        # We need to check the type name since BleakClient might be mocked in tests
        if hasattr(device, "write_gatt_char") and hasattr(device, "start_notify"):
            # Use the provided BleakClient directly
            self._client = device
            # Extract name from client if available, otherwise use address
            self._name = getattr(device, "name", None) or device.address
        else:
            # Create a new BleakClient from BLEDevice
            self._name = device.name
            self._client = BleakClient(
                device,
                services=[desk_service_uuid],
                disconnected_callback=self._disconnect_callback,
            )

        self._listeners: list[asyncio.Queue] = []
        self._connection_cache: dict[HostType, Frame] = {}

    @property
    def name(self) -> str:
        return self._name

    @property
    def address(self) -> str:
        return self._client.address

    @property
    def is_connected(self) -> bool:
        return self._client.is_connected

    async def _data_callback(
        self, sender: BleakGATTCharacteristic, data: bytearray
    ) -> None:
        # Check the message is from where we expect
        if sender.uuid != desk_attribute_notify:
            logger.warning(f"Received unexpected data from service: {sender}")
            return

        logger.debug(f"Bytes received from {self.address}: {data.hex()}")

        try:
            frame = Frame.from_bytes(data)
            logger.debug(f"Frame received from {self.address}: {frame}")
        except Exception as e:
            logger.warning(
                f'Exception while parsing message "{data.hex()}" from {self.address}: {e}'
            )
            return

        await self._valid_frame_callback(frame)

    def _disconnect_callback(self, client: BleakClient):
        logger.debug(f"Disconnected from {self.address}")

        self._connection_cache = {}

    async def _valid_frame_callback(self, frame: Frame) -> None:
        # Store in the cache
        self._connection_cache[frame.command] = frame

        # Call any subscribers
        to_remove = []

        for queue in self._listeners:
            try:
                queue.put_nowait(frame)
            except asyncio.QueueShutDown:
                logger.warning("Listener queue was closed")
                to_remove.append(queue)

        # Remove all the shut down queues
        for r in to_remove:
            self._unsubscribe(r)

    def _subscribe(self) -> asyncio.Queue:
        q = asyncio.Queue()

        self._listeners.append(q)

        return q

    def _unsubscribe(self, queue: asyncio.Queue) -> None:
        self._listeners.remove(queue)
        queue.shutdown(immediate=True)

    def __repr__(self) -> str:
        return f'Blesk(name="{self.name}", address="{self.address}")'

    async def send_frame(self, frame: Frame):
        logger.debug(f"Sending frame to {self.address}: {frame}")

        data = frame.to_bytes()
        logger.debug(f"Sending bytes to {self.address}: {data.hex()}")

        await self._client.write_gatt_char(desk_attribute_write, data)

    async def get_frame(self, kind: HostType, from_cache=True) -> Frame:
        # If not wait for the message
        logger.debug(f"Waiting for message of type {kind}")
        q = self._subscribe()

        while True:
            frame: Frame = await q.get()

            if frame.command == kind:
                logger.debug(f"Message wait for {kind} complete")
                self._unsubscribe(q)
                return frame

            q.task_done()

    async def query(self, send: Frame, receive: HostType, from_cache=True):
        if from_cache and receive in self._connection_cache.keys():
            logger.debug(f"Message type {receive} retrived from cache")
            return self._connection_cache[receive]

        query_task = asyncio.create_task(self.get_frame(kind=receive))
        await self.send_frame(send)

        return await query_task

    async def wake(self):
        await self.send_frame(Frame(command=DeskType.BLE_WAKE))

    async def stop(self):
        """Stop desk movement.

        The desk does not stop instantly: the height stream runs at ~5 Hz and
        the desk coasts briefly after this command, so a controller should
        allow for a few centimetres of overshoot.
        """
        await self.send_frame(Frame(command=DeskType.STOP))

    async def get_lock(self) -> bool:
        """Return the child-lock state (True = locked).

        ``0xB2`` is overloaded on the desk: with no payload it queries the
        child lock (and doubles as the wake that starts the height stream).
        The reply is already captured during ``connect`` (the wake doubles as
        a lock query), so this normally returns from the cache.
        """
        frame = await self.query(
            send=Frame(command=DeskType.BLE_WAKE), receive=HostType.BLE_WAKE_RESP
        )
        return bool(frame.params[0])

    async def set_lock(self, locked: bool) -> None:
        """Set the child lock (``locked=True``) or clear it (``locked=False``).

        The desk echoes the new state as a notification immediately, which
        updates the cache for subsequent ``get_lock`` calls. Note that the
        lock only guards the physical panel and the reference app's UI; it does
        not block BLE movement frames.
        """
        await self.send_frame(
            Frame(command=DeskType.BLE_WAKE, params=bytes([int(locked)]))
        )

    async def get_lighting(self) -> bool:
        """Return the light state (True = on)."""
        frame = await self.query(
            send=Frame(command=DeskType.SET_LIGHTING), receive=HostType.LIGHTING
        )
        return bool(frame.params[0])

    async def set_lighting(self, on: bool) -> None:
        """Turn the light on (``on=True``) or off (``on=False``)."""
        await self.send_frame(
            Frame(command=DeskType.SET_LIGHTING, params=bytes([int(on)]))
        )

    async def get_brightness(self) -> int:
        """Return the light brightness (0-100)."""
        frame = await self.query(
            send=Frame(command=DeskType.SET_BRIGHTNESS), receive=HostType.BRIGHTNESS
        )
        return int(frame.params[0])

    async def set_brightness(self, percent: int) -> None:
        """Set the light brightness to ``percent`` (0-100)."""
        if not 0 <= percent <= 100:
            raise ValueError("brightness must be 0-100")
        await self.send_frame(
            Frame(command=DeskType.SET_BRIGHTNESS, params=bytes([percent]))
        )

    async def get_light_color(self) -> LightColor:
        """Return the current light colour."""
        frame = await self.query(
            send=Frame(command=DeskType.SET_LIGHT_COLOR), receive=HostType.LIGHT_COLOR
        )
        value = int(frame.params[0])
        if value == 0x07:  # the reference app's parser also reports off as 0x07
            return LightColor.OFF
        return LightColor(value)

    async def set_light_color(self, color: LightColor) -> None:
        """Set the light colour to ``color``."""
        await self.send_frame(
            Frame(command=DeskType.SET_LIGHT_COLOR, params=bytes([color.value]))
        )

    async def connect(self):
        await self._client.connect()
        await self._client.start_notify(
            char_specifier=desk_attribute_notify, callback=self._data_callback
        )
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
        frame = await self.query(
            send=Frame(command=DeskType.SETTINGS), receive=HostType.UNITS
        )

        u = Units(frame.params[0])

        return u

    async def get_height_mm(self) -> int:
        units_task = asyncio.create_task(self.get_units())
        height_task = asyncio.create_task(
            self.query(send=Frame(command=DeskType.BLE_WAKE), receive=HostType.HEIGHT)
        )

        units = await units_task
        frame = await height_task

        return HeightData(frame.params[0:2]).decode_as(units).as_mm.as_float

    async def goto_mm(self, mm: int):
        # The desk keeps moving until told to stop, so issue a stop first to
        # interrupt any in-progress move (matches the reference app's recipe).
        await self.stop()

        units = await self.get_units()

        if units == Units.MM:
            await self.send_frame(
                Frame(command=DeskType.GOTO_HEIGHT, params=HeightMM(mm).encode.data)
            )
        else:
            await self.send_frame(
                Frame(
                    command=DeskType.GOTO_HEIGHT, params=HeightMM(mm).as_in.encode.data
                )
            )

    async def goto_preset(self, preset: Preset):
        preset_info = PresetDict[preset]

        # Stop first so an in-progress move is interrupted before the new
        # target is applied (matches the reference app's recipe).
        await self.stop()
        await self.send_frame(Frame(command=preset_info.goto))

    async def get_preset_mm(self, preset: Preset):
        preset_info = PresetDict[preset]

        units_task = asyncio.create_task(self.get_units())
        frame = await self.query(
            send=Frame(command=DeskType.SETTINGS), receive=preset_info.get
        )
        units = await units_task

        return HeightData(frame.params[0:2]).decode_as(units).as_mm.as_float
