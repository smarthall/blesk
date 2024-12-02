import asyncio

from bleak import BleakScanner, BleakClient, BleakGATTCharacteristic

from messages import parse

desk_service_uuid = '0000fe60-0000-1000-8000-00805f9b34fb'
desk_attribute_write = '0000fe61-0000-1000-8000-00805f9b34fb'
desk_attribute_read = '0000fe62-0000-1000-8000-00805f9b34fb'

def callback(sender: BleakGATTCharacteristic, data: bytearray):
    if (sender.uuid == desk_attribute_read):
        print(f"Desk: {parse(data)}")
    else:
        print(f"{sender}: {data}")

async def main():
    devices = await BleakScanner.discover(0.5, return_adv=True, service_uuids=[desk_service_uuid])

    # Find the device
    myDevice = None
    for d in devices:
        if (devices[d][1].local_name == "Daniel's Desk"):
            print("Device Found!")
            myDevice = d

    # Exit if there is none
    if (myDevice is None):
        print("No device found, exiting...")
        return
    
    # Connect to the device
    async with BleakClient(myDevice, services=[desk_service_uuid]) as client:
        print('Listening...')
        await client.start_notify(char_specifier=desk_attribute_read, callback=callback)

        print('Setting up...')
        await client.write_gatt_char(desk_attribute_write, b'\xf1\xf1\xb2\x00\xb2\x7e')
        print('Sent!')

        # print('Settings')
        # await client.write_gatt_char(desk_attribute_write, b'\xf1\xf1\x07\x00\x07\x7e')
        # print('Sent!')

        # print('Move up...')
        # await client.write_gatt_char(desk_attribute_write, b'\xf1\xf1\x01\x00\x01\x7e')
        # print('Sent!')

        print('Position 1')
        await client.write_gatt_char(desk_attribute_write, b'\xf1\xf1\x05\x00\x05\x7e')
        print('Sent!')

        # print('?')
        # await client.write_gatt_char(desk_attribute_write, b'\xf1\xf1\xaa\x00\xaa\x7e')
        # print('Sent!')

        # print('Go to 1000')
        # await client.write_gatt_char(desk_attribute_write, b'\xf1\xf1\x1b\x03\x03\xe8\x00\x09\x7e')
        # print('Sent!')

        while True:
            await asyncio.sleep(1)

asyncio.run(main())
