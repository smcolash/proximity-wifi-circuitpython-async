#!/usr/bin/env python

import binascii
import gc
import microcontroller
import sys
import time
import traceback
import wifi

from beacon import Beacon
from output import Output
import secrets

def raw_to_hex (macid):
    output = binascii.hexlify (macid, ':')
    return output.decode ('utf-8')

def main ():
    gc.enable ()

    print ('-' * 35)
    channel = Output.channel (secrets)

    while True:
        print ('-' * 35)
        print ('listening on channel: %d' % (channel))

        pending = 0
        monitor = wifi.Monitor (channel=channel)
        tick = time.monotonic_ns ()

        while pending == 0:
            packet = monitor.packet ()
            if len (packet):
                raw = packet[wifi.Packet.RAW]

                address = {}
                address['addr1'] = raw_to_hex (raw[4:(4+6)])
                address['addr2'] = raw_to_hex (raw[10:(10+6)])
                address['addr3'] = raw_to_hex (raw[16:(16+6)])
                address['addr4'] = raw_to_hex (raw[24:(16+6)])

                header = raw_to_hex (raw[0:32])
                underline = ' ' * 12 + '1' * 17 + ' ' * 1 + '2' * 17 + ' ' * 1 + '3' * 17 + ' ' * 7 + '4' * 17

                del raw
                gc.collect ()

                for macid in Beacon.items:
                    beacon = Beacon.items[macid]

                    if not beacon.enabled:
                        continue

                    for region in address:
                        if macid in address[region]:
                            print ('-' * 35)
                            print ('trigger - %s (%s) found in %s' % (
                                    beacon.macid, beacon.name, region
                                )
                            )
                            print (header)
                            print (underline)

                            for name in beacon.output:
                                device = Output.items[name]
                                if device.toggle (True):
                                    pending = pending + 1
            else:
                time.sleep (0.001)

            for name in Output.items:
                device = Output.items[name]

                if device.idle ():
                    if device.toggle (False):
                        pending = pending + 1

            if max (0, (time.monotonic_ns () - tick)) > 1E9:
                Output.status ()
                gc.collect ()
                tick = time.monotonic_ns ()

        monitor.deinit ()

        #
        # synchronize the output state with the devices
        #
        Output.synchronize (secrets)

if __name__ == '__main__':
    try:
        #
        # run the main function
        #
        main ()
    except KeyboardInterrupt:
        #
        # exit to REPL
        #
        pass
    except Exception as e:
        #
        # reboot the system
        #
        traceback.print_exception (e)
        time.sleep (10)
        microcontroller.reset ()

