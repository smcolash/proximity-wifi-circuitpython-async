import adafruit_hashlib as hashlib
import adafruit_ntp
import adafruit_requests
import circuitpython_hmac as hmac

import board
import digitalio
import gc
import json
import socketpool
import ssl
import time
import traceback
import wifi

#pool = socketpool.SocketPool (wifi.radio)

def memory_check ():
    pass

class Output (object):
    items = {}

    @classmethod
    def factory (cls, id, details):
        if details['type'] == 'gpio':
            return GPIOControl (id, details)

        if details['type'] == 'led':
            return LEDControl (id, details)

        if details['type'] == 'tuya':
            return TuyaControl (id, details)

        if details['type'] == 'webhook':
            return Control (id, details)

    def __init__ (self, name, limit, enabled):
        super ().__init__ ()

        if name in self.items:
            raise Exception ('duplicate device')

        self.items[name] = self

        self.name = name
        self.limit = limit
        self.enabled = enabled
        self.last = time.time ()
        self.pending = False
        self.on = False
        self.unknown = True

    @classmethod
    def channel (cls, secrets):
        result = None
        for network in wifi.radio.start_scanning_networks ():
            print (f'{network.ssid:<32} {network.rssi:>4} {network.channel}')

            if network.ssid in secrets.networks:
                secrets.ssid = network.ssid
                result = network.channel
                break

        wifi.radio.stop_scanning_networks ()

        if not result:
            result = 3

        return result

    def idletime (self):
        return max (0, time.time () - self.last)

    def idle (self):
        if not self.enabled:
            return False

        return self.idletime () > self.limit

    def tick (self):
        return self.idle () and (self.idletime () % self.limit == 0)

    def toggle (self, state):
        if not self.enabled:
            return False

        if state:
            self.last = time.time ()
            if not self.on:
                print ('toggle - turn on %s' % (self.name))
                self.on = True
                self.pending = True
        else:
            if self.unknown:
                print ('toggle - unknown/initial state')
                self.on = True
                self.unknown = False

            if (self.idle () and self.on) or self.tick ():
                print ('toggle - turn off %s' % (self.name))
                self.on = False
                self.pending = True

        self.unknown = False

        return self.pending

    @classmethod
    def status (cls):
        print ('-' * 35)
        for name, device in cls.items.items ():
            if not device.enabled:
                continue

            def label (value, names):
                return names[int (value)]

            print ('%-20s : %4d %s %s %s %s %d' % (
                    device.name,
                    device.idletime (),
                    label (device.idle (), ['A', 'I']),
                    label (device.on, ['0', '1']),
                    label (device.unknown, ['K', 'U']),
                    label (device.pending, ['S', 'P']),
                    gc.mem_free ()
                )
            )

    @classmethod
    def synchronize (cls, secrets):
        #
        # connect to the acces point
        #
        if secrets.ssid == None:
            print ('error - no available access point')
            return

        print (f'connecting to {secrets.ssid}')
        wifi.radio.connect (secrets.ssid, secrets.networks[secrets.ssid])
        print (f'connected to {secrets.ssid}')
        print (f'local IP address: {wifi.radio.ipv4_address}')

        #
        # apply any state updates to the devices
        #
        for name, device in cls.items.items ():
            if device.enabled:
                device.apply ()

        #
        # disconnect from the access point
        #
        wifi.radio.stop_station ()

    def apply (self):
        if not self.pending:
            return False

        self.pending = False

        try:
            self.activate ()
        except Exception as e:
            traceback.print_exception (e)
            print ('warning - device activation failed')

    def activate (self):
        print (f'{self.name:<20} : {self.output} = {self.on}')

class GPIOControl (Output):
    gpio = {}

    def __init__ (self, id, details):
        super ().__init__ (id, details['timeout'], details['enabled'])
        self.output = details['pin']

        if self.output not in self.gpio:
            self.gpio[self.output] = digitalio.DigitalInOut (getattr (board, self.output))
            self.gpio[self.output].direction = digitalio.Direction.OUTPUT

    def activate (self):
        super ().activate ()
        self.gpio[self.output].value = self.on

class LEDControl (GPIOControl):
    gpio = {}

    def __init__ (self, id, details):
        super ().__init__ (id, details)

class TuyaControl (Output):
    def __init__ (self, id, details):
        super ().__init__ (id, details['timeout'], details['enabled'])
        self.output = details['name']

        self.timestamp = 0
        self.timeout = 0
        self.client_id = details['client_id']
        self.client_secret = details['client_secret']
        self.device_id = details['device_id']
        self.output = details['name']
        self.server = details['server']

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
        super ().activate ()

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
        data = { 'commands': [ { 'code': self.output, 'value': self.on == True } ] }
        response = self.request (pool,
            'POST',
            f'/v1.0/iot-03/devices/{self.device_id}/commands',
            json.dumps (data)
        )

class WebHookControl (Output):
    # FIXME...
    def __init__ (self, id, details):
        super ().__init__ (id, details['timeout'], details['enabled'])
        self.urls = urls

    def activate (self):
        print ('TODO - WebHookCOntrol activate')
        #super ().activate ()
        #print ('%s: %d --> %s' % (self.name, self.on, self.urls[self.on]))

        #response = http.get (self.urls[self.on])
        #print (response.text)
        #response.close ()

