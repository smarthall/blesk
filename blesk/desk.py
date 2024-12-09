import logging

from bleak import BleakClient, BleakGATTCharacteristic
from bleak.backends.device import BLEDevice

from .const import desk_service_uuid, desk_attribute_read, desk_attribute_write
from .protocol import Frame, DeskType

logger = logging.getLogger(__name__)

class Blesk:


    def __init__(self, device:BLEDevice) -> None:
        self._device = device

        self._client = BleakClient(device, services=[desk_service_uuid], disconnected_callback=self._disconnect_callback)

    def _data_callback(self, sender: BleakGATTCharacteristic, data: bytearray):
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

    async def wake(self):
        await self.send_frame(Frame(command=DeskType.WAKE, params=b''))

    async def connect(self):
        await self._client.connect()
        await self._client.start_notify(char_specifier=desk_attribute_read, callback=self._data_callback)
        await self.wake()

    async def disconnect(self):
        await self._client.disconnect()

    async def move_one(self):
        await self.send_frame(Frame(command=DeskType.MOVE_1, params=b''))

    async def settings(self):
        await self.send_frame(Frame(command=DeskType.SETTINGS, params=b''))
