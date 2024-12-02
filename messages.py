from dataclasses import dataclass

address_from_desk = b'\xf2\xf2'
address_from_host = b'\xf1\xf1'
end_of_message = 0x7e

valid_addresses = [
    address_from_desk,
    address_from_host
]

command_height = 0x01

@dataclass
class BaseMessage(): # TODO: Rename this to 'Frame'
    from_desk: bool
    command: int
    params: bytes

    def as_bytes(self) -> bytes:
        raw = bytearray()

        if (self.from_desk):
            raw += b'\xf2\xf2'
        else:
            raw += b'\xf1\xf1'

        raw += self.command.to_bytes()

        raw += len(self.params).to_bytes()

        raw += self.params

        raw += sum(raw[2:]) % 0x100

        raw += end_of_message.to_bytes()

@dataclass
class HeightMessage():
    height_mm: int
    height_in: float
    unknown: int

    def __init__(self, base):
        height = base.params[0] * 0xff + base.params[1]
        self.unknown = base.params[2]

        # Height in mm
        if (height > 550):
            self.height_mm = height
            self.height_in = height / 25.4
        # Height in tenths of an in
        else:
            self.height_in = (height / 10)
            self.height_mm = (height / 10) * 25.4

def parse(message_bytes):
    base = parse_base(message_bytes)

    if (base.from_desk and base.command == command_height):
        return HeightMessage(base)

    return base

def parse_base(message_bytes): # TODO: Parse Frame
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
        raise Exception(f'Checksum does not match, expected 0x{clc_chk:02x} but got 0x{msg_chk:02x}. Raw: {message_bytes}')

    # Address
    address = message_bytes[0:2]
    if (address not in valid_addresses):
        raise Exception('Invalid address')
    
    # Gather Data
    from_desk = False
    if (address == address_from_desk):
        from_desk = True
    
    command = message_bytes[2]
    params = message_bytes[4:-2]

    return BaseMessage(from_desk, command, params)