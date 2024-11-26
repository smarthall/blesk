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

        await asyncio.sleep(30)

asyncio.run(main())
