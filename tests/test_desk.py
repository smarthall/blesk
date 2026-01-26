"""Unit tests for blesk.desk module.

This demonstrates how to test async BLE operations using mocks.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock, Mock, call, patch

import pytest
import pytest_asyncio
from bleak.backends.device import BLEDevice

from blesk.const import desk_attribute_read, desk_attribute_write
from blesk.desk import Blesk
from blesk.protocol import DeskType, Frame, HostType, Preset, Units


# =============================================================================
# Fixtures
# =============================================================================


@pytest.fixture
def mock_ble_device():
    """Create a mock BLEDevice."""
    device = Mock(spec=BLEDevice)
    device.name = "Desky Standing Desk"
    device.address = "AA:BB:CC:DD:EE:FF"
    device.details = {"path": "/org/bluez/hci0/dev_AA_BB_CC_DD_EE_FF"}
    return device


@pytest.fixture
def mock_bleak_client_class():
    """Create a mock BleakClient class."""
    with patch("blesk.desk.BleakClient") as MockClient:
        client_instance = MagicMock()
        client_instance.address = "AA:BB:CC:DD:EE:FF"
        client_instance.is_connected = False
        client_instance.connect = AsyncMock()
        client_instance.disconnect = AsyncMock()
        client_instance.start_notify = AsyncMock()
        client_instance.write_gatt_char = AsyncMock()
        MockClient.return_value = client_instance
        yield client_instance


@pytest.fixture
def desk(mock_ble_device, mock_bleak_client_class):
    """Create a Blesk instance with mocked BLE."""
    return Blesk(mock_ble_device)


@pytest_asyncio.fixture
async def connected_desk(desk, mock_bleak_client_class):
    """Create a connected Blesk instance."""
    mock_bleak_client_class.is_connected = True
    await desk.connect()
    return desk


# =============================================================================
# Initialization Tests
# =============================================================================


def test_init(mock_ble_device):
    """Test Blesk initialization."""
    desk = Blesk(mock_ble_device)

    assert desk.name == "Desky Standing Desk"
    assert desk._listeners == []
    assert desk._connection_cache == {}


def test_properties(desk):
    """Test Blesk properties."""
    assert desk.name == "Desky Standing Desk"
    assert desk.address == "AA:BB:CC:DD:EE:FF"
    assert desk.is_connected is False


def test_repr(desk):
    """Test Blesk string representation."""
    result = repr(desk)
    assert result == 'Blesk(name="Desky Standing Desk", address="AA:BB:CC:DD:EE:FF")'


# =============================================================================
# Connection Tests
# =============================================================================


@pytest.mark.asyncio
async def test_connect(desk, mock_bleak_client_class):
    """Test connecting to desk."""
    mock_bleak_client_class.is_connected = True

    await desk.connect()

    mock_bleak_client_class.connect.assert_awaited_once()
    mock_bleak_client_class.start_notify.assert_awaited_once()

    # Should send wake frame
    calls = mock_bleak_client_class.write_gatt_char.await_args_list
    assert len(calls) == 1
    # Verify it was a BLE_WAKE command
    wake_frame_bytes = calls[0][0][1]
    wake_frame = Frame.from_bytes(wake_frame_bytes)
    assert wake_frame.command == DeskType.BLE_WAKE


@pytest.mark.asyncio
async def test_disconnect(connected_desk, mock_bleak_client_class):
    """Test disconnecting from desk."""
    await connected_desk.disconnect()

    mock_bleak_client_class.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_context_manager(desk, mock_bleak_client_class):
    """Test using Blesk as async context manager."""
    mock_bleak_client_class.is_connected = True

    async with desk as d:
        assert d is desk
        mock_bleak_client_class.connect.assert_awaited_once()

    mock_bleak_client_class.disconnect.assert_awaited_once()


@pytest.mark.asyncio
async def test_disconnect_callback_clears_cache(desk):
    """Test that disconnect callback clears the cache."""
    # Populate cache
    frame = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    desk._connection_cache[HostType.HEIGHT] = frame

    # Trigger disconnect callback
    desk._disconnect_callback(desk._client)

    assert desk._connection_cache == {}


# =============================================================================
# Frame Sending Tests
# =============================================================================


@pytest.mark.asyncio
async def test_send_frame(connected_desk, mock_bleak_client_class):
    """Test sending a frame to the desk."""
    frame = Frame(command=DeskType.RAISE)

    await connected_desk.send_frame(frame)

    expected_bytes = frame.to_bytes()
    mock_bleak_client_class.write_gatt_char.assert_awaited_with(
        desk_attribute_write,
        expected_bytes
    )


@pytest.mark.asyncio
async def test_wake(connected_desk, mock_bleak_client_class):
    """Test sending wake command."""
    await connected_desk.wake()

    # Should have sent BLE_WAKE frame
    calls = mock_bleak_client_class.write_gatt_char.await_args_list
    assert len(calls) >= 1
    # Last call should be wake command
    last_call_data = calls[-1][0][1]
    frame = Frame.from_bytes(last_call_data)
    assert frame.command == DeskType.BLE_WAKE


# =============================================================================
# Frame Receiving and Callback Tests
# =============================================================================


@pytest.mark.asyncio
async def test_data_callback_valid_frame(desk):
    """Test receiving valid frame data."""
    # Create a valid HEIGHT response
    frame = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    frame_bytes = frame.to_bytes()

    # Mock the characteristic
    mock_char = Mock()
    mock_char.uuid = desk_attribute_read

    await desk._data_callback(mock_char, bytearray(frame_bytes))

    # Frame should be in cache
    assert HostType.HEIGHT in desk._connection_cache
    assert desk._connection_cache[HostType.HEIGHT].command == HostType.HEIGHT


@pytest.mark.asyncio
async def test_data_callback_invalid_frame(desk):
    """Test receiving invalid frame data doesn't crash."""
    mock_char = Mock()
    mock_char.uuid = "99fa0001-338a-1024-8a49-009c0215f78a"

    # Send invalid data (too short)
    await desk._data_callback(mock_char, bytearray(b'\xf1\xf1'))

    # Should not crash, cache should be empty
    assert len(desk._connection_cache) == 0


@pytest.mark.asyncio
async def test_data_callback_wrong_uuid(desk):
    """Test receiving data from wrong UUID is ignored."""
    mock_char = Mock()
    mock_char.uuid = "wrong-uuid"

    frame = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    await desk._data_callback(mock_char, bytearray(frame.to_bytes()))

    # Should be ignored
    assert len(desk._connection_cache) == 0


@pytest.mark.asyncio
async def test_valid_frame_callback_updates_cache(desk):
    """Test that valid frame callback updates cache."""
    frame = Frame(command=HostType.HEIGHT, params=b'\x02\xee')

    await desk._valid_frame_callback(frame)

    assert HostType.HEIGHT in desk._connection_cache
    assert desk._connection_cache[HostType.HEIGHT] == frame


@pytest.mark.asyncio
async def test_valid_frame_callback_notifies_subscribers(desk):
    """Test that valid frame callback notifies subscribers."""
    # Subscribe to frames
    queue = desk._subscribe()

    frame = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    await desk._valid_frame_callback(frame)

    # Give tasks a chance to run
    await asyncio.sleep(0.01)

    # Queue should have received the frame
    assert queue.qsize() == 1
    received_frame = await queue.get()
    assert received_frame == frame


# =============================================================================
# Subscription Tests
# =============================================================================


def test_subscribe_creates_queue(desk):
    """Test subscribing creates a queue."""
    queue = desk._subscribe()

    assert queue in desk._listeners
    assert isinstance(queue, asyncio.Queue)


def test_unsubscribe_removes_queue(desk):
    """Test unsubscribing removes queue."""
    queue = desk._subscribe()

    desk._unsubscribe(queue)

    assert queue not in desk._listeners


@pytest.mark.asyncio
async def test_get_frame_waits_for_specific_type(desk):
    """Test get_frame waits for specific frame type."""
    # Create a task to wait for HEIGHT frame
    get_task = asyncio.create_task(desk.get_frame(HostType.HEIGHT))

    # Give it time to subscribe
    await asyncio.sleep(0.01)

    # Send a different frame type first
    await desk._valid_frame_callback(Frame(command=HostType.UNITS, params=b'\x00'))
    await asyncio.sleep(0.01)

    # Task should still be waiting
    assert not get_task.done()

    # Send the correct frame type
    expected_frame = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    await desk._valid_frame_callback(expected_frame)
    await asyncio.sleep(0.01)

    # Now task should complete
    result = await get_task
    assert result.command == HostType.HEIGHT
    assert result.params == b'\x02\xee'


# =============================================================================
# Query Tests
# =============================================================================


@pytest.mark.asyncio
async def test_query_uses_cache(connected_desk, mock_bleak_client_class):
    """Test query uses cached response when available."""
    # Pre-populate cache
    cached_frame = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    connected_desk._connection_cache[HostType.HEIGHT] = cached_frame

    result = await connected_desk.query(
        send=Frame(command=DeskType.BLE_WAKE),
        receive=HostType.HEIGHT,
        from_cache=True
    )

    # Should return cached frame without sending
    assert result == cached_frame
    # No additional write should happen beyond connection/wake
    assert mock_bleak_client_class.write_gatt_char.await_count <= 2  # connect + wake


@pytest.mark.asyncio
async def test_query_bypasses_cache(connected_desk, mock_bleak_client_class):
    """Test query with from_cache=False bypasses cache."""
    # Pre-populate cache
    cached_frame = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    connected_desk._connection_cache[HostType.HEIGHT] = cached_frame

    # Start query that will wait for response
    query_task = asyncio.create_task(
        connected_desk.query(
            send=Frame(command=DeskType.BLE_WAKE),
            receive=HostType.HEIGHT,
            from_cache=False
        )
    )

    await asyncio.sleep(0.01)

    # Simulate receiving a response
    new_frame = Frame(command=HostType.HEIGHT, params=b'\x04\x4c')
    await connected_desk._valid_frame_callback(new_frame)

    result = await query_task
    # Should get new frame, not cached
    assert result.params == b'\x04\x4c'


@pytest.mark.asyncio
async def test_query_sends_and_receives(connected_desk):
    """Test query sends frame and waits for response."""
    # Start query
    query_task = asyncio.create_task(
        connected_desk.query(
            send=Frame(command=DeskType.BLE_WAKE),
            receive=HostType.HEIGHT,
            from_cache=False
        )
    )

    await asyncio.sleep(0.01)

    # Simulate response
    response = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    await connected_desk._valid_frame_callback(response)

    result = await query_task
    assert result.command == HostType.HEIGHT


# =============================================================================
# High-Level Method Tests
# =============================================================================


@pytest.mark.asyncio
async def test_get_units(connected_desk):
    """Test getting desk units."""
    # Start get_units
    units_task = asyncio.create_task(connected_desk.get_units())

    await asyncio.sleep(0.01)

    # Simulate UNITS response (MM mode)
    response = Frame(command=HostType.UNITS, params=b'\x00')
    await connected_desk._valid_frame_callback(response)

    result = await units_task
    assert result == Units.MM


@pytest.mark.asyncio
async def test_get_units_inches(connected_desk):
    """Test getting desk units when in inches mode."""
    units_task = asyncio.create_task(connected_desk.get_units())

    await asyncio.sleep(0.01)

    response = Frame(command=HostType.UNITS, params=b'\x01')
    await connected_desk._valid_frame_callback(response)

    result = await units_task
    assert result == Units.IN


@pytest.mark.asyncio
async def test_get_height_mm(connected_desk):
    """Test getting current desk height in mm."""
    # Start get_height_mm
    height_task = asyncio.create_task(connected_desk.get_height_mm())

    await asyncio.sleep(0.01)

    # Simulate UNITS response (MM mode)
    await connected_desk._valid_frame_callback(
        Frame(command=HostType.UNITS, params=b'\x00')
    )

    # Simulate HEIGHT response (750mm = 0x02EE)
    await connected_desk._valid_frame_callback(
        Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    )

    result = await height_task
    assert result == 750


@pytest.mark.asyncio
async def test_get_height_mm_from_inches(connected_desk):
    """Test getting height when desk is in inches mode."""
    height_task = asyncio.create_task(connected_desk.get_height_mm())

    await asyncio.sleep(0.01)

    # Desk in inches mode
    await connected_desk._valid_frame_callback(
        Frame(command=HostType.UNITS, params=b'\x01')
    )

    # Height is 30.5 inches = 305 tenth-inches = 0x0131
    await connected_desk._valid_frame_callback(
        Frame(command=HostType.HEIGHT, params=b'\x01\x31')
    )

    result = await height_task
    # Should convert to mm: ~774.7mm
    assert 774 <= result <= 775


@pytest.mark.asyncio
async def test_goto_mm_in_mm_mode(connected_desk, mock_bleak_client_class):
    """Test moving to specific height in MM mode."""
    # Pre-cache units as MM
    connected_desk._connection_cache[HostType.UNITS] = Frame(
        command=HostType.UNITS, params=b'\x00'
    )

    await connected_desk.goto_mm(1100)

    # Should send GOTO_HEIGHT command with 1100mm encoded
    # 1100 = 0x044C
    calls = mock_bleak_client_class.write_gatt_char.await_args_list
    last_call_data = calls[-1][0][1]
    frame = Frame.from_bytes(last_call_data)

    assert frame.command == DeskType.GOTO_HEIGHT
    assert frame.params == b'\x04\x4c'


@pytest.mark.asyncio
async def test_goto_mm_in_inches_mode(connected_desk, mock_bleak_client_class):
    """Test moving to specific height when desk is in inches mode."""
    # Pre-cache units as IN
    connected_desk._connection_cache[HostType.UNITS] = Frame(
        command=HostType.UNITS, params=b'\x01'
    )

    await connected_desk.goto_mm(750)

    # Should convert 750mm to inches and encode
    calls = mock_bleak_client_class.write_gatt_char.await_args_list
    last_call_data = calls[-1][0][1]
    frame = Frame.from_bytes(last_call_data)

    assert frame.command == DeskType.GOTO_HEIGHT
    # Should be ~29.5 inches = 295 tenth-inches = 0x0127
    assert len(frame.params) == 2


@pytest.mark.asyncio
async def test_goto_preset(connected_desk, mock_bleak_client_class):
    """Test moving to preset position."""
    await connected_desk.goto_preset(Preset.ONE)

    calls = mock_bleak_client_class.write_gatt_char.await_args_list
    last_call_data = calls[-1][0][1]
    frame = Frame.from_bytes(last_call_data)

    assert frame.command == DeskType.MOVE_1


@pytest.mark.asyncio
async def test_get_preset_mm(connected_desk):
    """Test getting preset position."""
    # Start get_preset_mm
    preset_task = asyncio.create_task(connected_desk.get_preset_mm(Preset.ONE))

    await asyncio.sleep(0.01)

    # Simulate UNITS response
    await connected_desk._valid_frame_callback(
        Frame(command=HostType.UNITS, params=b'\x00')
    )

    # Simulate POSITION_1 response (750mm)
    await connected_desk._valid_frame_callback(
        Frame(command=HostType.POSITION_1, params=b'\x02\xee')
    )

    result = await preset_task
    assert result == 750


@pytest.mark.asyncio
async def test_get_preset_mm_all_presets(connected_desk):
    """Test getting all four preset positions."""
    presets_map = {
        Preset.ONE: HostType.POSITION_1,
        Preset.TWO: HostType.POSITION_2,
        Preset.THREE: HostType.POSITION_3,
        Preset.FOUR: HostType.POSITION_4,
    }

    for preset, host_type in presets_map.items():
        # Clear cache between tests
        connected_desk._connection_cache.clear()

        preset_task = asyncio.create_task(connected_desk.get_preset_mm(preset))
        await asyncio.sleep(0.01)

        # Send units response
        await connected_desk._valid_frame_callback(
            Frame(command=HostType.UNITS, params=b'\x00')
        )

        # Send preset position response (different height for each)
        height_value = 700 + (preset.value * 100)  # 800, 900, 1000, 1100
        height_bytes = height_value.to_bytes(2, byteorder='big')
        await connected_desk._valid_frame_callback(
            Frame(command=host_type, params=height_bytes)
        )

        result = await preset_task
        assert result == height_value


# =============================================================================
# Edge Cases and Error Handling
# =============================================================================


@pytest.mark.asyncio
async def test_multiple_subscribers(desk):
    """Test multiple subscribers all receive frames."""
    queue1 = desk._subscribe()
    queue2 = desk._subscribe()

    frame = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    await desk._valid_frame_callback(frame)

    await asyncio.sleep(0.01)

    # Both queues should receive the frame
    assert queue1.qsize() == 1
    assert queue2.qsize() == 1


@pytest.mark.asyncio
async def test_cache_persistence(desk):
    """Test that cache persists across queries."""
    frame1 = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    frame2 = Frame(command=HostType.UNITS, params=b'\x00')

    await desk._valid_frame_callback(frame1)
    await desk._valid_frame_callback(frame2)

    # Both should be in cache
    assert HostType.HEIGHT in desk._connection_cache
    assert HostType.UNITS in desk._connection_cache
    assert desk._connection_cache[HostType.HEIGHT] == frame1
    assert desk._connection_cache[HostType.UNITS] == frame2


@pytest.mark.asyncio
async def test_cache_update_on_new_frame(desk):
    """Test that cache updates when new frame of same type received."""
    old_frame = Frame(command=HostType.HEIGHT, params=b'\x02\xee')
    new_frame = Frame(command=HostType.HEIGHT, params=b'\x04\x4c')

    await desk._valid_frame_callback(old_frame)
    assert desk._connection_cache[HostType.HEIGHT].params == b'\x02\xee'

    await desk._valid_frame_callback(new_frame)
    assert desk._connection_cache[HostType.HEIGHT].params == b'\x04\x4c'
