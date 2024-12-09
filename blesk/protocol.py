import logging

from collections import namedtuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

end_of_message = 0x7e
header_length = 6
minimum_length = 6
maximum_length = 12
maximum_param_length = maximum_length - header_length

class Address(Enum):
    DESK = b'\xf1\xf1'
    HOST = b'\xf2\xf2'

class Preset(Enum):
    ONE = 0x01
    TWO = 0x02
    THREE = 0x03
    FOUR = 0x04

class Units(Enum):
    MM = 0x00
    IN = 0x01

class HostType(Enum):
    """
    Messages types for messages _to_ the Host
    """
    HEIGHT = 0x01

    UNITS = 0x0e

    UNKNOWN_17 = 0x17

    MEM_MODE = 0x19

    COLL_SENS = 0x1d

    POSITION_1 = 0x25
    POSITION_2 = 0x26
    POSITION_3 = 0x27
    POSITION_4 = 0x28

    BLE_WAKE_RESP = 0xb2

class DeskType(Enum):
    """
    Messages types for messages _to_ the Desk
    """
    RAISE = 0x01
    LOWER = 0x02
    PROGMEM_1 = 0x03
    PROGMEM_2 = 0x04
    MOVE_1 = 0x05
    MOVE_2 = 0x06
    SETTINGS = 0x07

    UNITS = 0x0e

    GOTO_HEIGHT = 0x1b

    PROGMEM_3 = 0x25
    PROGMEM_4 = 0x26
    MOVE_3 = 0x27
    MOVE_4 = 0x28

    BLE_WAKE = 0xb2

PresetInfo = namedtuple('PositionInfo', ['goto', 'set_current', 'get'])

PresetDict = {
    Preset.ONE: PresetInfo(DeskType.MOVE_1, DeskType.PROGMEM_1, HostType.POSITION_1),
    Preset.TWO: PresetInfo(DeskType.MOVE_2, DeskType.PROGMEM_2, HostType.POSITION_2),
    Preset.THREE: PresetInfo(DeskType.MOVE_3, DeskType.PROGMEM_3, HostType.POSITION_3),
    Preset.FOUR: PresetInfo(DeskType.MOVE_4, DeskType.PROGMEM_4, HostType.POSITION_4),
}

@dataclass
class HeightData:
    data: bytes

    def decode_as(self, unit: Units) -> 'HeightMM | HeightIn':
        if (unit == Units.MM):
            return HeightMM((self.data[0] * 0x100) + self.data[1])
        
        tenth_inches = (self.data[0] * 0x100) + self.data[1]
        return HeightIn(tenth_inches / 10)

    @property
    def decode_as_mm(self) -> 'HeightMM':
        return self.decode_as(Units.MM)

    @property
    def decode_as_in(self) -> 'HeightIn':
        return self.decode_as(Units.IN)

@dataclass
class HeightMM:
    mm: float

    @property
    def as_float(self) -> float:
        return self.mm

    @property
    def as_mm(self) -> 'HeightMM':
        return self

    @property
    def as_in(self) -> 'HeightIn':
        return HeightIn(self.mm * 0.0393701)
    
    @property
    def encode(self) -> HeightData:
        data = bytearray(2)

        data[0] = int(self.mm / 0x100)
        data[1] = int(self.mm % 0x100)

        return HeightData(data)

@dataclass
class HeightIn:
    inches: float

    @property
    def as_float(self) -> float:
        return self.mm
    
    @property
    def as_mm(self) -> 'HeightMM':
        return HeightMM(self.inches / 0.0393701)
    
    @property
    def as_in(self) -> 'HeightIn':
        return self
    
    @property
    def encode(self) -> HeightData:
        data = bytearray(2)

        data[0] = int(self.inches * 10 / 0x100)
        data[1] = int(self.inches * 10 % 0x100)

        return HeightData(data)

@dataclass
class Frame:
    command: HostType | DeskType
    params: bytes = b''

    @property
    def address(self):
        if isinstance(self.command, DeskType):
            return Address.DESK
        
        return Address.HOST

    @classmethod
    def from_bytes(cls, message_bytes: bytes):
        # Length test
        if (len(message_bytes) < 6):
            raise Exception('Message too short')
        
        if (len(message_bytes) > 12):
            raise Exception('Message too long')
        
        length = message_bytes[3]
        if (len(message_bytes) != length + 6):
            raise Exception('Incorrect message length')

        # Message end
        if (message_bytes[-1] != end_of_message):
            raise Exception('Message not terminated correctly')

        # Checksum
        msg_chk = message_bytes[-2]
        clc_chk = sum(message_bytes[2:-2]) % 0x100
        if (msg_chk != clc_chk):
            raise Exception(f'Checksum does not match, expected 0x{clc_chk:02x} but got 0x{msg_chk:02x}.')

        # Pull out all the values we need
        address = Address(bytes(message_bytes[0:2]))

        # To the Desk
        message_type = message_bytes[2]

        if (address == Address.DESK):
            try:
                command = DeskType(message_type)
            except ValueError as e:
                raise ValueError(f'0x{message_type:02x} is not a valid DeskType')
        else:
            try:
                command = HostType(message_type)
            except ValueError as e:
                raise ValueError(f'0x{message_type:02x} is not a valid HostType')

        params = message_bytes[4:-2]
        
        return cls(command=command, params=params)

    def to_bytes(self) -> bytes:
        msg = bytearray()

        length = len(self.params)
        if (length > maximum_param_length):
            raise ValueError(f'Parameter length of {length} longer than maximum of {maximum_param_length}')

        # Address
        msg += self.address.value
        msg += self.command.value.to_bytes(length=1)
        msg += length.to_bytes(length=1)
        msg += self.params
        msg += (sum(msg[2:]) % 0x100).to_bytes(1)
        msg += end_of_message.to_bytes(1)

        return bytes(msg)
