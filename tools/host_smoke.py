#!/usr/bin/env python3
"""Run on a Linux PC connected to the Pi USB data port, NOT on the Pi.
Requires pyusb and libusb; tests transport, not PS3 gameplay.
No figure dumps are needed or modified.
"""
import time
import usb.core
import usb.util

dev=usb.core.find(idVendor=0x1430,idProduct=0x0150)
if dev is None: raise SystemExit('Portal not found')
if dev.is_kernel_driver_active(0): dev.detach_kernel_driver(0)
try:
    if dev.get_active_configuration().bConfigurationValue!=1:dev.set_configuration(1)
except usb.core.USBError:dev.set_configuration(1)
usb.util.claim_interface(dev,0)

def exchange(command,expected,control=True):
    if control:dev.ctrl_transfer(0x21,9,0x0200,0,command,timeout=2000)
    else:dev.write(0x02,command,timeout=2000)
    end=time.monotonic()+3
    while time.monotonic()<end:
        packet=bytes(dev.read(0x81,64,timeout=2000))
        if packet.startswith(expected):
            assert len(packet)==32
            print(('control' if control else 'interrupt')+' '+command[:1].decode()+' OK')
            return packet
    raise RuntimeError('Expected reply not received: '+expected.hex())

try:
    config=dev.get_active_configuration()
    interface=config[(0,0)]
    assert interface.bInterfaceClass==3 and interface.bNumEndpoints==2
    for address in (0x81,2):
        ep=usb.util.find_descriptor(interface,bEndpointAddress=address)
        assert ep and ep.wMaxPacketSize==64 and ep.bInterval==1
    report=bytes(dev.ctrl_transfer(0x81,6,0x2200,0,255,timeout=2000))
    assert len(report)==29
    exchange(b'R',b'R\x02\x18')
    exchange(b'A\x01',b'A\x01\xff\x77')
    exchange(b'J',b'J')
    exchange(b'S',b'S')
    exchange(b'Q\x1f\x3f',b'Q',control=False)
    exchange(b'M\x01',b'M\x01\x00\x19')
    print('USB smoke checks passed. PS3 gameplay remains unverified.')
finally:
    usb.util.release_interface(dev,0)
    usb.util.dispose_resources(dev)
