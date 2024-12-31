#!/usr/bin/env python

import adafruit_hashlib as hashlib
import adafruit_ntp
import adafruit_requests
import circuitpython_hmac as hmac

import asyncio
import binascii
import board
import digitalio
import gc
import json
import microcontroller
import socketpool
import ssl
import sys
import time
import traceback
import wifi

# ------------------------------------------------------------

class AccessPoint (object):
    ssid = None
    channel = None
    location = None

    def __init__ (self, config, delay=10):
        self.config = config
        self.delay = delay

    async def __aenter__ (self):
        while True:
            #
            # scan for the list of currently available networks
            #
            networks = []
            for network in wifi.radio.start_scanning_networks ():
                known = ' '

                if network.ssid in self.config:
                    networks.append (network)
                    known = '*'

                print (f'{known} {network.ssid:<32} {network.rssi:>4} {network.channel}')

            wifi.radio.stop_scanning_networks ()

            #
            # select the strongest known network
            #
            for network in sorted (networks, key=lambda item: item.rssi, reverse=True):
                wifi.radio.connect (network.ssid, self.config[network.ssid]['password'])
                if wifi.radio.connected:
                    AccessPoint.ssid = wifi.radio.ap_info.ssid
                    AccessPoint.channel = wifi.radio.ap_info.channel
                    AccessPoint.location = self.config[self.ssid]['location']

                    return self

            #
            # wait and try again if none found
            #
            await asyncio.sleep (self.delay)

    async def __aexit__ (self, exc_type, exc_value, exc_tb):
        wifi.radio.stop_station ()

# ------------------------------------------------------------

class Frame (object):
    @classmethod
    def hex (cls, raw):
        return binascii.hexlify (raw, ':').decode ('utf-8')

    @classmethod
    def framecontrol (cls, raw):
        return raw[0] << 8 + raw[1]

    @classmethod
    def is_rts (cls, raw):
        return cls.framecontrol (raw) == 0xb400

# ------------------------------------------------------------

class Output (object):
    inventory = {}

    @classmethod
    def factory (cls, id, config):
        try:
            temp = config.get ('type', 'output')

            if temp == 'gpio':
                return GPIOOutput (id, config)

            if temp == 'led':
                return LEDOutput (id, config)

            if temp == 'tuya':
                return TuyaOutput (id, config)

            return Output (id, config)
        except Exception as e:
            traceback.print_exception (e)

    def __init__ (self, id, config):
        self.name = id
        self.type = config.get ('type', 'output')
        self.enabled = config.get ('enabled', True)
        self.timeout = config.get ('timeout', 30 * 60)

        self.pending = False
        self.known = False
        self.state = False
        self.last = time.time ()

        if self.enabled:
            self.inventory[id] = self

    def __str__ (self):
        delta = time.time () - self.last
        return f'{self.type:8} {self.name:24} {self.state:1} {"P" if self.pending else "_"} {"K" if self.known else "_"} {delta}'

    def update (self, state=None):
        #
        # handle change of state
        #
        print (f'U: {self}')
        if state is not None:
            if self.state != state:
                self.pending = True

            if not self.known:
                self.known = True
                self.pending = True

            self.state = state
            self.last = time.time ()

        #
        # handle timeout
        #
        if time.time () - self.last > self.timeout:
            print (f'T: {self}')
            self.update (False)

    @classmethod
    def waiting (cls):
        status = False
        for name, output in cls.inventory.items ():
            status |= output.pending

        return status

    @classmethod
    def synchronize (cls, mapping, location):
        #
        # get the set of relevant outputs
        #
        outputs = set ()
        for beacon in mapping[location]:
            outputs.update (mapping[location][beacon])

        #
        # set any new output states
        #
        for name, output in cls.inventory.items ():
            print (f'S: {output}')
            output.activate ()

    def activate (self):
        self.pending = False
        print (f'A: {self}')

# ------------------------------------------------------------

class GPIOOutput (Output):
    gpio = {}

    def __init__ (self, id, config):
        super ().__init__ (id, config)

        self.output = config['pin']

        if self.output not in self.gpio:
            self.gpio[self.output] = digitalio.DigitalInOut (getattr (board, self.output))
            self.gpio[self.output].direction = digitalio.Direction.OUTPUT

    def activate (self):
        if self.pending:
            self.gpio[self.output].value = self.state

        super ().activate ()

# ------------------------------------------------------------

class LEDOutput (GPIOOutput):
    pass

# ------------------------------------------------------------

class TuyaOutput (Output):
    def __init__ (self, id, config):
        super ().__init__ (id, config)

        self.output = config['name']
        self.client_id = config['client_id']
        self.client_secret = config['client_secret']
        self.device_id = config['device_id']
        self.output = config['name']
        self.server = config['server']

        self.timestamp = 0
        self.http = None
        self.token = ''
        self.authorization = None


    def request (self, pool, method, api, body = ''):
        hash = hashlib.sha256 (body.encode ()).hexdigest ()
        temp = f'{self.client_id}{self.token}{self.timestamp}{method}\n{hash}\n\n{api}'
        sign = hmac.new (self.client_secret.encode (), temp.encode (), hashlib.sha256).hexdigest ().upper ()

        headers = {
            'sign_method': 'HMAC-SHA256',
            'client_id': self.client_id,
            't': str (self.timestamp),
            'mode': 'cors',
            'Content-Type': 'application/json',
            'sign': sign
        }

        if self.token != '':
            headers['access_token'] = self.token

        if self.http == None:
            self.http = adafruit_requests.Session (pool, ssl.create_default_context ())

        with self.http.request (method, f'{self.server}{api}', headers=headers, data=body) as response:
            data = response.json ()

        gc.collect ()

        return data



    def activate (self):
        if self.pending:
            pool = socketpool.SocketPool (wifi.radio)

            ntp = adafruit_ntp.NTP (pool, tz_offset=0)
            now = int (time.mktime (ntp.datetime) * 1000)

            #
            # invalidate an older access token
            #
            if now - self.timestamp > (self.timeout - 60):
                self.timestamp = now
                self.token = ''

            #
            # get a valid access token
            #
            if self.token == '':
                response = self.request (pool,
                    'GET',
                    '/v1.0/token?grant_type=1'
                )
                self.authorization = response['result']
                self.token = response['result']['access_token']
                self.timeout = response['result']['expire_time']
                #print (response)

            #
            # send the control request for the device
            #
            data = { 'commands': [ { 'code': self.output, 'value': self.state == True } ] }
            response = self.request (pool,
                'POST',
                f'/v1.0/iot-03/devices/{self.device_id}/commands',
                json.dumps (data)
            )

        super ().activate ()

# ------------------------------------------------------------

class Beacon (object):
    inventory = {}

    @classmethod
    def factory (cls, id, config):
        Beacon (id, config)

    def __init__ (self, id, config):
        self.macid = id
        self.enabled = config['enabled']
        self.name = config['name']
        self.frames = 0

        if self.enabled:
            self.inventory[id] = self

    def __str__ (self):
        return f'{self.name:10} {self.macid} {self.frames}'

    @classmethod
    def match (cls, raw):
        dumb = Frame.hex (raw[0:22])

        for id, beacon in cls.inventory.items ():
            if id in dumb:
                print ('-' * 35)
                print (f'F: {beacon.name}')
                print (dumb)
                print (' ' * dumb.index (id) + '-----------------')
                beacon.frames += 1

#
# update output state after beacons have been identified
#
async def tick (config, lock):
    while True:
        try:
            #
            # process any new beacon frames
            #
            for name, beacon in Beacon.inventory.items ():
                #DEBUG# print (f'B: {beacon}')

                #
                # update outputs based on beacon activity
                #
                if beacon.frames > 0 and beacon.name in config['mapping'][AccessPoint.location]:
                    try:
                        print ('==========')
                        print (f'L: {AccessPoint.location}')
                        print (f'M: {name}')
                        print (f'N: {beacon.name}')
                        for output in config['mapping'][AccessPoint.location][beacon.name]:
                            print (f'P: {output}')
                            Output.inventory[output].update (True)
                        print ('==========')
                    except Exception as e:
                        traceback.print_exception (e)

                    beacon.frames = 0

            #
            # update the state of all of the outputs in the local mapping
            #
            outputs = set ()
            for items in config['mapping'][AccessPoint.location].values ():
                outputs.update (items)

            for name in sorted (items):
                Output.inventory[name].update ()

            #
            # apply any pending changes
            #
            if Output.waiting ():
                async with lock:
                    async with AccessPoint (config['wifi']) as ap:
                        Output.synchronize (config['mapping'], ap.location)

        except Exception as e:
            traceback.print_exception (e)
            pass

        gc.collect ()
        await asyncio.sleep (1.0)

#
# periodically resynchronize everything
#
async def resync (config, lock):
    #
    # loop forever
    #
    while True:
        #
        # wait one hour
        #
        await asyncio.sleep (1 * 60 * 60)

        #
        # mark each output as pending
        #
        try:
            for name, output in Output.inventory.items ():
                output.pending = True
        except:
            pass

#
# watch for WiFi header frames that correspond to the configured beacons
#
async def sniff (config, lock):
    #
    # monitor packet headers on the current access point channel
    #
    while True:
        if Output.waiting ():
            await asyncio.sleep (1.0)
        else:
            async with lock:
                #
                # initialize WiFi for packet sniffing
                #
                print ('-' * 35)
                print (f'listening on channel {AccessPoint.channel} [{AccessPoint.location}]')
                monitor = wifi.Monitor (channel=AccessPoint.channel)

                #
                # loop until an output needs to be synchronized
                #
                while not Output.waiting ():
                    packet = monitor.packet ()
                    if len (packet) == 0:
                        await asyncio.sleep (0.001)
                        continue

                    raw = packet[wifi.Packet.RAW]
                    Beacon.match (raw)

                    del raw
                    gc.collect ()

                #
                # stop using the WiFi
                #
                monitor.deinit ()

#
# main task
#
async def main ():
    gc.enable ()

    lock = asyncio.Lock ()

    #
    # read the configuration data
    #
    with open ('secrets.json') as file:
        config = json.load (file)

    #
    # create the inputs
    #
    for id, parameters in config['beacon'].items ():
        Beacon.factory (id, parameters)

    #
    # create the outputs
    #
    for id, parameters in config['output'].items ():
        Output.factory (id, parameters)

    #
    # find an initial access point
    #
    async with AccessPoint (config['wifi']):
        pass

    #
    # create the set of independent tasks
    #
    tasks = [
        #
        # task to listen for WiFi packets as inputs
        #
        asyncio.create_task (sniff (config, lock)),
        #
        # task to update output state on change of inputs
        #
        asyncio.create_task (tick (config, lock)),
        #
        # task to periodically resynchronize things
        #
        asyncio.create_task (resync (config, lock))
    ]

    #
    # wait for all of the tasks to complete
    #
    await asyncio.gather (*tasks)

#
# main entry point
#
if __name__ == '__main__':
    try:
        #
        # run the main task
        #
        asyncio.run (main ())
    except KeyboardInterrupt:
        #
        # exit to the REPL
        #
        pass
    except Exception as e:
        #
        # try to show what happened
        #
        traceback.print_exception (e)
        time.sleep (10)

        #
        # reboot the system
        #
        microcontroller.reset ()

