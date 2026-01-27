"""Comprehensive unit tests for blesk.protocol module."""

import pytest
from blesk.protocol import (
    Address,
    DeskType,
    Frame,
    HeightData,
    HeightIn,
    HeightMM,
    HostType,
    Units,
)


# =============================================================================
# HeightData Tests
# =============================================================================


def test_decode_as_mm_zero():
    """Decode 0x0000 as MM should return 0mm."""
    data = HeightData(b"\x00\x00")
    result = data.decode_as(Units.MM)
    assert isinstance(result, HeightMM)
    assert result.mm == 0


def test_decode_as_mm_typical():
    """Decode typical value (750mm = 0x02EE)."""
    # 750 = 2*256 + 238 = 0x02EE
    data = HeightData(b"\x02\xee")
    result = data.decode_as(Units.MM)
    assert isinstance(result, HeightMM)
    assert result.mm == 750


def test_decode_as_mm_maximum():
    """Decode maximum value (0xFFFF = 65535mm)."""
    data = HeightData(b"\xff\xff")
    result = data.decode_as(Units.MM)
    assert isinstance(result, HeightMM)
    assert result.mm == 65535


def test_decode_as_in_zero():
    """Decode 0x0000 as inches should return 0 inches."""
    data = HeightData(b"\x00\x00")
    result = data.decode_as(Units.IN)
    assert isinstance(result, HeightIn)
    assert result.inches == 0.0


def test_decode_as_in_typical():
    """Decode typical value (30.5 inches = 305 tenth-inches = 0x0131)."""
    # 305 = 1*256 + 49 = 0x0131
    data = HeightData(b"\x01\x31")
    result = data.decode_as(Units.IN)
    assert isinstance(result, HeightIn)
    assert result.inches == 30.5


def test_decode_as_in_maximum():
    """Decode maximum tenth-inch value."""
    # 0xFFFF = 65535 tenth-inches = 6553.5 inches
    data = HeightData(b"\xff\xff")
    result = data.decode_as(Units.IN)
    assert isinstance(result, HeightIn)
    assert result.inches == 6553.5


def test_decode_as_mm_property():
    """Test decode_as_mm property."""
    data = HeightData(b"\x02\xee")
    result = data.decode_as_mm
    assert isinstance(result, HeightMM)
    assert result.mm == 750


def test_decode_as_in_property():
    """Test decode_as_in property."""
    data = HeightData(b"\x01\x31")
    result = data.decode_as_in
    assert isinstance(result, HeightIn)
    assert result.inches == 30.5


def test_decode_with_different_units():
    """Same data interpreted as different units gives different values."""
    data = HeightData(b"\x02\xee")
    mm_result = data.decode_as(Units.MM)
    in_result = data.decode_as(Units.IN)

    assert mm_result.mm == 750
    assert in_result.inches == 75.0  # 750 tenth-inches / 10


# =============================================================================
# HeightMM Tests
# =============================================================================


def test_height_mm_as_float():
    """Verify as_float returns mm value."""
    height = HeightMM(750.0)
    assert height.as_float == 750.0


def test_height_mm_as_mm_identity():
    """Verify as_mm returns self."""
    height = HeightMM(750.0)
    assert height.as_mm is height


def test_height_mm_as_in_conversion():
    """Test MM to IN conversion using 0.0393701 factor."""
    height = HeightMM(750.0)
    result = height.as_in
    assert isinstance(result, HeightIn)
    # 750mm * 0.0393701 ≈ 29.527575 inches
    assert abs(result.inches - 29.527575) < 0.00001


def test_height_mm_encode_zero():
    """Encode 0mm to bytes."""
    height = HeightMM(0)
    data = height.encode
    assert isinstance(data, HeightData)
    assert data.data == b"\x00\x00"


def test_height_mm_encode_typical():
    """Encode 750mm to bytes [0x02, 0xEE]."""
    height = HeightMM(750)
    data = height.encode
    assert isinstance(data, HeightData)
    assert data.data == b"\x02\xee"


def test_height_mm_encode_maximum():
    """Encode max representable value (65535mm)."""
    height = HeightMM(65535)
    data = height.encode
    assert isinstance(data, HeightData)
    assert data.data == b"\xff\xff"


def test_height_mm_encode_decode_roundtrip():
    """Encode then decode should equal original."""
    original = HeightMM(1100)
    encoded = original.encode
    decoded = encoded.decode_as_mm
    assert decoded.mm == original.mm


def test_height_mm_conversion_precision():
    """Test floating point precision in conversions."""
    height = HeightMM(1000.0)
    in_height = height.as_in
    back_to_mm = in_height.as_mm
    # Should be close but may have floating point error
    assert abs(back_to_mm.mm - 1000.0) < 0.01


def test_height_mm_to_in_to_mm_roundtrip():
    """Convert MM→IN→MM should preserve value within tolerance."""
    original = HeightMM(800.0)
    converted = original.as_in.as_mm
    assert abs(converted.mm - original.mm) < 0.01


def test_height_mm_encode_with_fractional():
    """Encoding fractional mm values gets truncated to int."""
    height = HeightMM(750.7)
    data = height.encode
    # int(750.7 / 256) = 2, int(750.7 % 256) = 238
    assert data.data == b"\x02\xee"


# =============================================================================
# HeightIn Tests
# =============================================================================


def test_height_in_as_float():
    """Verify as_float returns in value"""
    height = HeightIn(30.0)
    assert height.as_float == 30.0  # This will fail due to bug


def test_height_in_as_in_identity():
    """Verify as_in returns self."""
    height = HeightIn(30.0)
    assert height.as_in is height


def test_height_in_as_mm_conversion():
    """Test IN to MM conversion (1 / 0.0393701 factor)."""
    height = HeightIn(30.0)
    result = height.as_mm
    assert isinstance(result, HeightMM)
    # 30 inches / 0.0393701 ≈ 762mm
    assert abs(result.mm - 762.0) < 0.1


def test_height_in_encode_zero():
    """Encode 0 inches to bytes."""
    height = HeightIn(0)
    data = height.encode
    assert isinstance(data, HeightData)
    assert data.data == b"\x00\x00"


def test_height_in_encode_typical():
    """Encode 30.5 inches to tenth-inches format."""
    height = HeightIn(30.5)
    data = height.encode
    # 30.5 * 10 = 305 = 0x0131
    assert isinstance(data, HeightData)
    assert data.data == b"\x01\x31"


def test_height_in_encode_maximum():
    """Encode max value that fits in 2 bytes."""
    # Max: 6553.5 inches (65535 tenth-inches)
    height = HeightIn(6553.5)
    data = height.encode
    assert isinstance(data, HeightData)
    assert data.data == b"\xff\xff"


def test_height_in_encode_decode_roundtrip():
    """Encode then decode should equal original."""
    original = HeightIn(43.3)
    encoded = original.encode
    decoded = encoded.decode_as_in
    assert abs(decoded.inches - original.inches) < 0.01


def test_height_in_tenth_inch_precision():
    """Verify tenth-inch encoding (multiply by 10)."""
    height = HeightIn(29.7)
    data = height.encode
    # 29.7 * 10 = 297 = 0x0129
    assert data.data == b"\x01\x29"


def test_height_in_to_mm_to_in_roundtrip():
    """Convert IN→MM→IN should preserve value within tolerance."""
    original = HeightIn(35.0)
    converted = original.as_mm.as_in
    assert abs(converted.inches - original.inches) < 0.01


def test_height_in_conversion_factor():
    """Verify the conversion factor 1/0.0393701."""
    height_in = HeightIn(1.0)
    height_mm = height_in.as_mm
    # 1 inch = 25.4mm (approximately 1/0.0393701)
    assert abs(height_mm.mm - 25.4) < 0.01


def test_height_in_encode_with_fractional_tenth():
    """Encoding values with fractional tenths gets truncated."""
    height = HeightIn(30.57)  # 305.7 tenth-inches
    data = height.encode
    # int(305.7 / 256) = 1, int(305.7 % 256) = 49
    assert data.data == b"\x01\x31"


# =============================================================================
# Frame.from_bytes() Tests
# =============================================================================


def test_from_bytes_valid_minimal():
    """Parse a valid 6-byte minimal message."""
    # Minimal frame: DESK address, RAISE command, 0 params
    # Structure: [f1 f1] [01] [00] [checksum] [7e]
    # Checksum = (01 + 00) % 0x100 = 0x01
    message = b"\xf1\xf1\x01\x00\x01\x7e"
    frame = Frame.from_bytes(message)

    assert frame.command == DeskType.RAISE
    assert frame.params == b""
    assert frame.address == Address.DESK


def test_from_bytes_valid_maximal():
    """Parse a valid 12-byte maximum message."""
    # Max params = 6 bytes
    # Structure: [f1 f1] [07] [06] [aa bb cc dd ee ff] [checksum] [7e]
    # Checksum = (07 + 06 + aa + bb + cc + dd + ee + ff) % 0x100
    checksum = (0x07 + 0x06 + 0xAA + 0xBB + 0xCC + 0xDD + 0xEE + 0xFF) % 0x100
    message = b"\xf1\xf1\x07\x06\xaa\xbb\xcc\xdd\xee\xff" + bytes([checksum]) + b"\x7e"

    frame = Frame.from_bytes(message)
    assert frame.command == DeskType.SETTINGS
    assert frame.params == b"\xaa\xbb\xcc\xdd\xee\xff"


def test_from_bytes_with_params():
    """Parse message with parameters."""
    # GOTO_HEIGHT with 2-byte height param
    # Structure: [f1 f1] [1b] [02] [02 ee] [checksum] [7e]
    # Checksum = (1b + 02 + 02 + ee) % 0x100 = 0x0d (27+2+2+238=269, 269%256=13)
    message = b"\xf1\xf1\x1b\x02\x02\xee\x0d\x7e"

    frame = Frame.from_bytes(message)
    assert frame.command == DeskType.GOTO_HEIGHT
    assert frame.params == b"\x02\xee"


def test_from_bytes_desk_address():
    """Verify Address.DESK parsed correctly."""
    message = b"\xf1\xf1\x01\x00\x01\x7e"
    frame = Frame.from_bytes(message)
    assert frame.address == Address.DESK


def test_from_bytes_host_address():
    """Verify Address.HOST parsed correctly."""
    # HEIGHT response from desk to host
    # Structure: [f2 f2] [01] [02] [02 ee] [checksum] [7e]
    # Checksum = (01 + 02 + 02 + ee) % 0x100 = 0xf3 (1+2+2+238=243)
    message = b"\xf2\xf2\x01\x02\x02\xee\xf3\x7e"

    frame = Frame.from_bytes(message)
    assert frame.command == HostType.HEIGHT
    assert frame.address == Address.HOST


def test_from_bytes_too_short():
    """Raise exception on message shorter than 6 bytes."""
    with pytest.raises(Exception, match="Message too short"):
        Frame.from_bytes(b"\xf1\xf1\x01\x00\x01")


def test_from_bytes_too_long():
    """Raise exception on message longer than 12 bytes."""
    message = b"\xf1\xf1\x01\x07\xaa\xbb\xcc\xdd\xee\xff\x00\x00\x7e"
    with pytest.raises(Exception, match="Message too long"):
        Frame.from_bytes(message)


def test_from_bytes_length_mismatch():
    """Raise exception when length byte doesn't match actual length."""
    # Says length=5 but only has 2 param bytes
    # Structure: [f1 f1] [01] [05] [aa bb] [checksum] [7e]
    message = b"\xf1\xf1\x01\x05\xaa\xbb\x00\x7e"
    with pytest.raises(Exception, match="Incorrect message length"):
        Frame.from_bytes(message)


def test_from_bytes_bad_termination():
    """Raise exception when last byte is not 0x7e."""
    message = b"\xf1\xf1\x01\x00\x01\xff"  # Last byte is 0xff not 0x7e
    with pytest.raises(Exception, match="Message not terminated correctly"):
        Frame.from_bytes(message)


def test_from_bytes_checksum_fail_off_by_one():
    """Raise exception when checksum is off by one."""
    # Correct checksum is 0x01, provide 0x02
    message = b"\xf1\xf1\x01\x00\x02\x7e"
    with pytest.raises(Exception, match="Checksum does not match"):
        Frame.from_bytes(message)


def test_from_bytes_checksum_fail_zero():
    """Raise exception when checksum is 0x00 but should be non-zero."""
    # Checksum should be 0x01
    message = b"\xf1\xf1\x01\x00\x00\x7e"
    with pytest.raises(Exception, match="Checksum does not match"):
        Frame.from_bytes(message)


def test_from_bytes_invalid_desk_command():
    """Raise exception for unknown DeskType value."""
    # 0xff is not a valid DeskType
    # Structure: [f1 f1] [ff] [00] [checksum] [7e]
    checksum = (0xFF + 0x00) % 0x100
    message = b"\xf1\xf1\xff\x00" + bytes([checksum]) + b"\x7e"

    with pytest.raises(ValueError, match="0xff is not a valid DeskType"):
        Frame.from_bytes(message)


def test_from_bytes_invalid_host_command():
    """Raise exception for unknown HostType value."""
    # 0xaa is not a valid HostType
    # Structure: [f2 f2] [aa] [00] [checksum] [7e]
    checksum = (0xAA + 0x00) % 0x100
    message = b"\xf2\xf2\xaa\x00" + bytes([checksum]) + b"\x7e"

    with pytest.raises(ValueError, match="0xaa is not a valid HostType"):
        Frame.from_bytes(message)


def test_from_bytes_invalid_address():
    """Raise exception for unknown address value."""
    # 0xf3f3 is not a valid Address
    message = b"\xf3\xf3\x01\x00\x01\x7e"
    with pytest.raises(ValueError):
        Frame.from_bytes(message)


def test_from_bytes_extract_params():
    """Verify params are extracted correctly."""
    # Message with 4 bytes of params
    # Structure: [f1 f1] [07] [04] [11 22 33 44] [checksum] [7e]
    checksum = (0x07 + 0x04 + 0x11 + 0x22 + 0x33 + 0x44) % 0x100
    message = b"\xf1\xf1\x07\x04\x11\x22\x33\x44" + bytes([checksum]) + b"\x7e"

    frame = Frame.from_bytes(message)
    assert frame.params == b"\x11\x22\x33\x44"
    assert len(frame.params) == 4


def test_from_bytes_checksum_calculation():
    """Verify checksum is sum(bytes[2:-2]) % 0x100."""
    # Create a message where we know the checksum
    # Structure: [f1 f1] [01] [02] [aa bb] [checksum] [7e]
    # Checksum = (01 + 02 + aa + bb) % 0x100 = 0x68 (1+2+170+187=360, 360%256=104)
    message = b"\xf1\xf1\x01\x02\xaa\xbb\x68\x7e"

    frame = Frame.from_bytes(message)
    assert frame.command == DeskType.RAISE
    assert frame.params == b"\xaa\xbb"


# =============================================================================
# Frame.to_bytes() Tests
# =============================================================================


def test_to_bytes_minimal_desk_frame():
    """Serialize minimal DeskType frame."""
    frame = Frame(command=DeskType.RAISE)
    result = frame.to_bytes()

    # Expected: [f1 f1] [01] [00] [01] [7e]
    assert result == b"\xf1\xf1\x01\x00\x01\x7e"
    assert len(result) == 6


def test_to_bytes_minimal_host_frame():
    """Serialize minimal HostType frame."""
    frame = Frame(command=HostType.HEIGHT)
    result = frame.to_bytes()

    # Expected: [f2 f2] [01] [00] [01] [7e]
    assert result == b"\xf2\xf2\x01\x00\x01\x7e"
    assert len(result) == 6


def test_to_bytes_with_params():
    """Serialize frame with parameters."""
    frame = Frame(command=DeskType.GOTO_HEIGHT, params=b"\x02\xee")
    result = frame.to_bytes()

    # Expected: [f1 f1] [1b] [02] [02 ee] [checksum] [7e]
    # Checksum = (1b + 02 + 02 + ee) % 0x100 = 0x0d
    assert result == b"\xf1\xf1\x1b\x02\x02\xee\x0d\x7e"


def test_to_bytes_max_params():
    """Serialize frame with 6 bytes of params (maximum)."""
    frame = Frame(command=DeskType.SETTINGS, params=b"\xaa\xbb\xcc\xdd\xee\xff")
    result = frame.to_bytes()

    # Verify length and structure
    assert len(result) == 12
    assert result[0:2] == b"\xf1\xf1"  # DESK address
    assert result[2] == 0x07  # SETTINGS command
    assert result[3] == 0x06  # param length
    assert result[4:10] == b"\xaa\xbb\xcc\xdd\xee\xff"  # params
    assert result[-1] == 0x7E  # terminator


def test_to_bytes_params_too_long():
    """Raise exception when params exceed 6 bytes."""
    frame = Frame(command=DeskType.SETTINGS, params=b"\xaa\xbb\xcc\xdd\xee\xff\x00")

    with pytest.raises(
        ValueError, match="Parameter length of 7 longer than maximum of 6"
    ):
        frame.to_bytes()


def test_to_bytes_checksum_correctness():
    """Verify checksum is calculated correctly."""
    frame = Frame(command=DeskType.RAISE, params=b"\xaa\xbb")
    result = frame.to_bytes()

    # Checksum should be sum of bytes[2:-2] % 0x100
    # bytes[2:-2] = [01, 02, aa, bb]
    expected_checksum = (0x01 + 0x02 + 0xAA + 0xBB) % 0x100
    assert result[-2] == expected_checksum


def test_to_bytes_structure():
    """Verify byte structure is correct (address, cmd, len, params, chk, term)."""
    frame = Frame(command=DeskType.GOTO_HEIGHT, params=b"\x04\x56")
    result = frame.to_bytes()

    assert result[0:2] == b"\xf1\xf1"  # Address (DESK)
    assert result[2] == 0x1B  # Command (GOTO_HEIGHT)
    assert result[3] == 0x02  # Length (2 param bytes)
    assert result[4:6] == b"\x04\x56"  # Params
    # result[6] is checksum
    assert result[7] == 0x7E  # Terminator


def test_to_bytes_encode_decode_roundtrip():
    """to_bytes followed by from_bytes should equal original."""
    original = Frame(command=DeskType.GOTO_HEIGHT, params=b"\x02\xee")
    encoded = original.to_bytes()
    decoded = Frame.from_bytes(encoded)

    assert decoded.command == original.command
    assert decoded.params == original.params
    assert decoded.address == original.address


def test_to_bytes_empty_params():
    """Serialize frame with explicitly empty params."""
    frame = Frame(command=DeskType.RAISE, params=b"")
    result = frame.to_bytes()

    assert result[3] == 0x00  # Length should be 0
    assert len(result) == 6  # Minimal size


# =============================================================================
# Frame.address Property Tests
# =============================================================================


def test_address_property_desk():
    """DeskType command should return Address.DESK."""
    frame = Frame(command=DeskType.RAISE)
    assert frame.address == Address.DESK


def test_address_property_host():
    """HostType command should return Address.HOST."""
    frame = Frame(command=HostType.HEIGHT)
    assert frame.address == Address.HOST


def test_address_property_all_desk_types():
    """Verify all DeskType values return Address.DESK."""
    desk_types = [
        DeskType.RAISE,
        DeskType.LOWER,
        DeskType.MOVE_1,
        DeskType.GOTO_HEIGHT,
        DeskType.BLE_WAKE,
    ]

    for desk_type in desk_types:
        frame = Frame(command=desk_type)
        assert frame.address == Address.DESK


def test_address_property_all_host_types():
    """Verify all HostType values return Address.HOST."""
    host_types = [
        HostType.HEIGHT,
        HostType.UNITS,
        HostType.POSITION_1,
        HostType.BLE_WAKE_RESP,
    ]

    for host_type in host_types:
        frame = Frame(command=host_type)
        assert frame.address == Address.HOST


# =============================================================================
# Integration/Edge Case Tests
# =============================================================================


def test_real_height_query_response():
    """Parse a realistic HEIGHT response from desk (750mm)."""
    # Desk responds with current height in HOST frame
    # Structure: [f2 f2] [01] [02] [02 ee] [checksum] [7e]
    # Checksum = (01 + 02 + 02 + ee) % 0x100 = 0xf3
    message = b"\xf2\xf2\x01\x02\x02\xee\xf3\x7e"

    frame = Frame.from_bytes(message)
    assert frame.command == HostType.HEIGHT
    assert frame.params == b"\x02\xee"

    # Decode height
    height_data = HeightData(frame.params)
    height_mm = height_data.decode_as_mm
    assert height_mm.mm == 750


def test_real_preset_get_response():
    """Parse a realistic POSITION_1 response."""
    # Preset 1 stored at 750mm
    # Structure: [f2 f2] [25] [02] [02 ee] [checksum] [7e]
    # Checksum = (25 + 02 + 02 + ee) % 0x100 = 0x17 (37+2+2+238=279, 279%256=23)
    message = b"\xf2\xf2\x25\x02\x02\xee\x17\x7e"

    frame = Frame.from_bytes(message)
    assert frame.command == HostType.POSITION_1

    height_data = HeightData(frame.params)
    height_mm = height_data.decode_as_mm
    assert height_mm.mm == 750


def test_real_goto_command():
    """Encode a realistic GOTO_HEIGHT command for 1100mm."""
    # 1100mm = 0x044C
    height = HeightMM(1100)
    height_data = height.encode

    frame = Frame(command=DeskType.GOTO_HEIGHT, params=height_data.data)
    result = frame.to_bytes()

    # Verify structure
    assert result[0:2] == b"\xf1\xf1"  # DESK address
    assert result[2] == 0x1B  # GOTO_HEIGHT
    assert result[3] == 0x02  # 2 param bytes
    assert result[4:6] == b"\x04\x4c"  # 1100 = 4*256 + 76


def test_height_boundary_values():
    """Test boundary values: 0, 1, 255, 256, 65535."""
    test_values = [0, 1, 255, 256, 65535]

    for value in test_values:
        height = HeightMM(value)
        encoded = height.encode
        decoded = encoded.decode_as_mm
        assert decoded.mm == value


def test_unit_conversion_accuracy():
    """Verify MM↔IN conversions are within tolerance."""
    # Test standard desk heights
    test_heights_mm = [750, 1000, 1100, 1200]

    for mm in test_heights_mm:
        height_mm = HeightMM(mm)
        height_in = height_mm.as_in
        back_to_mm = height_in.as_mm

        # Should be within 0.1mm tolerance
        assert abs(back_to_mm.mm - mm) < 0.1


def test_checksum_rollover():
    """Test checksum calculation when sum exceeds 255."""
    # Create params that sum to > 255
    # Structure: [f1 f1] [07] [04] [80 80 80 80] [checksum] [7e]
    # Sum = 07 + 04 + 80 + 80 + 80 + 80 = 0x20B
    # Checksum = 0x20B % 0x100 = 0x0B
    frame = Frame(command=DeskType.SETTINGS, params=b"\x80\x80\x80\x80")
    result = frame.to_bytes()

    assert result[-2] == 0x0B


def test_params_empty_vs_zero_length():
    """Distinguish between empty params and zero-length params field."""
    frame1 = Frame(command=DeskType.RAISE)
    frame2 = Frame(command=DeskType.RAISE, params=b"")

    result1 = frame1.to_bytes()
    result2 = frame2.to_bytes()

    # Both should produce identical output
    assert result1 == result2
    assert result1[3] == 0x00  # Length field is 0


def test_frame_roundtrip_with_all_param_lengths():
    """Test roundtrip encoding/decoding with param lengths 0-6."""
    for param_length in range(7):
        params = bytes(range(param_length))
        original = Frame(command=DeskType.SETTINGS, params=params)
        encoded = original.to_bytes()
        decoded = Frame.from_bytes(encoded)

        assert decoded.command == original.command
        assert decoded.params == original.params
