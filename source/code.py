#!/usr/bin/env python

import adafruit_hashlib as hashlib
import adafruit_ntp as ntp
import adafruit_requests as requests
import circuitpython_hmac as hmac

import asyncio
import binascii
import board
import digitalio
import gc
import json
import mdns
import microcontroller
import os
import socketpool
import ssl
import sys
import time
import traceback
import wifi

import biplane

BUSY = 0

# ------------------------------------------------------------

def logger (text):
    print (text)

def info (text):
    logger (f'info - {text}')

def warn (text):
    logger (f'warning - {text}')

def error (text):
    logger (f'error - {text}')

def fixme (text):
    logger (f'FIXME :: {text}')

def emphasis (text):
    length = len (text) + 6
    logger ('*' * length)
    logger (f'** {text} **')
    logger ('*' * length)

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
            logger ('\n'.join (traceback.format_exception (e)))

    def __init__ (self, id, config):
        self.name = id
        self.config = config

        self.type = self.config.get ('type', 'output')
        self.enabled = self.config.get ('enabled', True)
        self.timeout = self.config.get ('timeout', 30 * 60)

        self.pending = False
        self.known = False
        self.state = False
        self.last = time.time ()

        if self.enabled:
            self.inventory[id] = self

    def __str__ (self):
        delta = time.time () - self.last
        return f'{self.type:8} {self.name:24} {self.state:1} {"P" if self.pending else "_"} {"K" if self.known else "_"} {delta:5}'

    def update (self, state=None):
        #
        # handle change of state
        #
        memory = gc.mem_free ()
        logger (f'U: {self} {memory}')

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
            logger (f'T: {self}')
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
            memory = gc.mem_free ()
            logger (f'S: {output} {memory}')
            output.activate ()

    def activate (self):
        self.pending = False
        logger (f'A: {self}')

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
    http = None

    def __init__ (self, id, config):
        super ().__init__ (id, config)

        self.output = config['name']
        self.client_id = config['client_id']
        self.client_secret = config['client_secret']
        self.device_id = config['device_id']
        self.output = config['name']
        self.server = config['server']

        self.timestamp = 0
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

        if self.http is None:
            self.http = requests.Session (pool, ssl.create_default_context ())

        with self.http.request (method, f'{self.server}{api}', headers=headers, data=body) as response:
            data = response.json ()

        gc.collect ()

        return data

    def activate (self):
        if self.pending:
            pool = socketpool.SocketPool (wifi.radio)

            #
            # invalidate an older access token
            #
            now = int (time.mktime (ntp.NTP (pool, tz_offset=0).datetime) * 1000)
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
                logger ('-' * 35)
                logger (f'F: {beacon.name}')
                logger (dumb)
                logger (' ' * dumb.index (id) + '-----------------')
                beacon.frames += 1

#
# task to monitor beacon and timeout status
#
async def system_monitor_task (configuration, lock):
    while True:
        gc.collect ()
        await asyncio.sleep (1.0)

        #
        # wait to be connected to an access point
        #
        if not wifi.radio.connected:
            continue

        #
        # wait until a location is set
        #
        location = configuration['system']['location']
        if location is None:
            continue

        try:
            #
            # process any new beacon frames
            #
            for name, beacon in Beacon.inventory.items ():
                #DEBUG# logger (f'B: {beacon}')

                #
                # update outputs based on beacon activity
                #
                if beacon.frames > 0 and beacon.name in configuration['mapping'][location]:
                    try:
                        logger ('==========')
                        logger (f'L: {location}')
                        logger (f'M: {name}')
                        logger (f'N: {beacon.name}')
                        for output in configuration['mapping'][location][beacon.name]:
                            logger (f'P: {output}')
                            Output.inventory[output].update (True)
                        logger ('==========')
                    except Exception as e:
                        logger ('\n'.join (traceback.format_exception (e)))

                    beacon.frames = 0

            #
            # update the state of all of the outputs in the local mapping
            #
            outputs = set ()
            for items in configuration['mapping'][location].values ():
                outputs.update (items)

            for name in sorted (outputs):
                Output.inventory[name].update ()

            #
            # temporarily release to the other tasks
            #
            await asyncio.sleep (0)

            #
            # apply any pending changes
            #
            if Output.waiting ():
                async with lock:
                    Output.synchronize (configuration['mapping'], location)

        except Exception as e:
            logger ('\n'.join (traceback.format_exception (e)))

#
# task to periodically resynchronize the output status
#
async def resynchronize_task (configuration, lock):
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
# task to listen for WiFi packets as inputs
#
async def packet_sniffer_task (configuration, lock):
    #
    # monitor packet headers on the current access point channel
    #
    while True:
        gc.collect ()
        await asyncio.sleep (1.0)

        #
        # wait to be connected to an access point
        #
        if not wifi.radio.connected:
            continue

        #
        # wait until the outputs are synchronized
        #
        if Output.waiting ():
            continue

        #
        # wait until the web server is idle
        #
        if BaseResponse.busy ():
            continue

        #
        # start monitoring packets
        #
        monitor = wifi.Monitor (channel=wifi.radio.ap_info.channel)

        emphasis (f'listening on channel {wifi.radio.ap_info.channel}')

        while wifi.radio.connected:
            gc.collect ()
            await asyncio.sleep (0)

            try:
                async with lock:
                    #
                    # temporarily stop to finish web responses
                    #
                    if BaseResponse.busy ():
                        info ('waiting for http responses to complete')
                        monitor.deinit ()
                        break

                    #
                    # temporarily stop to synchronize outputs
                    #
                    if Output.waiting ():
                        info ('pausing packet analysis')
                        monitor.deinit ()
                        break

                    #
                    # get the next usable packet
                    #
                    packet = monitor.packet ()

                    #
                    # check for a match against the becaons
                    #
                    Beacon.match (packet[wifi.Packet.RAW])

                    #
                    # clean up immediately
                    #
                    del packet
            except:
                pass

        info ('stopped packet analysis')

class BaseResponse (biplane.Response):
    timestamp = 0

    @classmethod
    def update (cls):
        BaseResponse.timestamp = time.time ()

    @classmethod
    def busy (cls, delta=1):
        return (time.time () - BaseResponse.timestamp) < delta

    def __init__(self, status_code=200, content_type='text/plain', headers={}):
        self.status_code = status_code
        self.headers = headers
        self.headers['content-type'] = content_type
        self.update ()

    def serialize(self):
        self.update ()
        response = bytearray(f'HTTP/1.1 {self.status_code} {self.status_code}\r\n'.encode('ascii'))
        yield response

        for name, value in self.headers.items():
            yield f'{name}: {value}\r\n'.encode('ascii')

        yield b'\r\n'

class Response (BaseResponse):
    def __init__(self, data, action=None, status_code=200, content_type='application/json', headers={}):
        super ().__init__ (status_code, content_type, headers)

        self.data = data
        self.action = action

        self.length = len (self.data)
        self.headers['content-length'] = self.length
        self.headers['cache-control'] = 'no-cache'

    def serialize(self):
        yield from super ().serialize ()
        yield self.data

        if self.action:
            self.action ()

class FileResponse (BaseResponse):
    def __init__(self, path, status_code=200, content_type='text/plain', headers={}):
        super ().__init__ (status_code, content_type, headers)

        self.path = path
        self.length = os.stat (self.path)[6]
        self.headers['content-length'] = self.length
        self.headers['cache-control'] = 'max-age=86400'
        self.headers['cache-control'] = 'no-cache'

    def serialize(self):
        yield from super ().serialize ()

        with open (self.path, 'rb') as file:
            while True:
                buffer = file.read (256)
                if not buffer:
                    break
                yield buffer
       
class JSONResponse (BaseResponse):
    def __init__(self, data, status_code=200, content_type='application/json', headers={}):
        super ().__init__ (status_code, content_type, headers)

        self.data = json.dumps (data)
        self.length = len (self.data)
        self.headers['content-length'] = self.length
        self.headers['cache-control'] = 'no-cache'

    def serialize(self):
        yield from super ().serialize ()
        yield self.data

class SSEResponse (BaseResponse):
    def __init__(self, generator, status_code=200, content_type='text/event-stream', headers={}):
        super ().__init__ (status_code, content_type, headers)

        self.generator = generator
        self.headers['cache-control'] = 'no-cache'
        self.headers['connection'] = 'keep-alive'

    def serialize(self):
        yield from super ().serialize ()
        yield from self.generator ()

    def send_event (self):
        data = json.dumps ({'a': 1234})
        yield b'event: zxcv' + b'\r\n'
        yield f'data: {data}'.encode ('ascii') + b'\r\n'
        yield b'\r\n'

#
# task to provide a web interface for status and configuration
#
async def web_server_task (configuration, lock):

    server = biplane.Server ()

    #
    # page content
    #
    @server.route ('/', 'GET')
    def handler (query_parameters, headers, body):
        return FileResponse ('assets/index.html', content_type='text/html')

    #
    # page styles
    #
    @server.route ('/styles.css', 'GET')
    def handler (query_parameters, headers, body):
        return FileResponse ('assets/styles.css', content_type='text/css')

    #
    # page code
    #
    @server.route ('/main.js', 'GET')
    def handler (query_parameters, headers, body):
        return FileResponse ('assets/main.js', content_type='text/javascript')

    #
    # icons
    #
    @server.route ('/eye-fill.svg', 'GET')
    def handler (query_parameters, headers, body):
        return FileResponse ('assets/eye-fill.svg', content_type='image/svg+xml')

    @server.route ('/file-earmark-plus.svg', 'GET')
    def handler (query_parameters, headers, body):
        return FileResponse ('assets/file-earmark-plus.svg', content_type='image/svg+xml')

    @server.route ('/file-earmark-check.svg', 'GET')
    def handler (query_parameters, headers, body):
        return FileResponse ('assets/file-earmark-check.svg', content_type='image/svg+xml')

    @server.route ('/trash3.svg', 'GET')
    def handler (query_parameters, headers, body):
        return FileResponse ('assets/trash3.svg', content_type='image/svg+xml')

    @server.route ('/secrets.json', 'GET')
    def handler (query_parameters, headers, body):
        return FileResponse ('assets/secrets.json', content_type='image/svg+xml')

    #
    # supporting REST API
    #
    @server.route ('/api/v1/config', 'GET')
    def handler (query_parameters, headers, body):
        return JSONResponse (configuration)

    @server.route ('/api/v1/restart', 'GET')
    def handler (query_parameters, headers, body):

        def action ():
            microcontroller.reset ()

        return Response ('rebooting', action=action)

    @server.route ('/api/v1/events', 'GET')
    def handler (query_parameters, headers, body):

        '''
        async def task (sse):
            try:
                for loop in range (50):
                    await asyncio.sleep (1.0)
                    sse.send_event (json.dumps ({'index': loop}), event="event_name")
            except:
                pass

            sse.close()
        '''

        def generator ():
            for loop in range (50):
                time.sleep (0.5)

                data = json.dumps ({'a': 1234})
                yield b'event: zxcv' + b'\r\n'
                yield f'data: {data}'.encode ('ascii') + b'\r\n'
                yield b'\r\n'

        return SSEResponse (generator)

    '''
    @server.route ('/api/v1/events', 'GET')
    def handler( request: httpserver.Request):

        async def task (sse):
            try:
                for loop in range (50):
                    await asyncio.sleep (1.0)
                    sse.send_event (json.dumps ({'index': loop}), event="event_name")
            except:
                pass

            sse.close()

        sse = httpserver.SSEResponse (request)
        asyncio.create_task (task (sse))

        return sse
    '''



    @server.route('/fml', 'GET')
    async def handler (query_parameters, headers, body):
        async def event_stream():
            while True:
                # Generate or fetch data for the event
                data = 'Hello from SSE!'

                # Format the event according to the SSE protocol
                event = f'data: {data}\n\n'

                # Yield the event to the client
                yield event.encode()

                # Wait for a specified interval
                await asyncio.sleep(1)

        # Set the appropriate headers for SSE
        headers = {
            'content-type': 'text/event-stream',
            'cache-control': 'no-cache',
            'connection': 'keep-alive',
        }

        # Return the event stream as a response
        return Response(event_stream(), headers=headers)




    pool = socketpool.SocketPool (wifi.radio)
    with pool.socket () as socket:
        for _ in server.start (socket, listen_on=('0.0.0.0', 80), max_parallel_connections=1):
            await asyncio.sleep (0)

#
# task to monitor button and set system mode
#
async def configuration_task (configuration, lock):
    # this pin is specific to the ESP32 DevKit V1
    button = digitalio.DigitalInOut (microcontroller.pin.GPIO0)
    button.direction = digitalio.Direction.INPUT
    button.pull = digitalio.Pull.UP

    if 'D2' not in GPIOOutput.gpio:
        GPIOOutput.gpio['D2'] = digitalio.DigitalInOut (getattr (board, 'D2'))
        GPIOOutput.gpio['D2'] = digitalio.Direction.OUTPUT
    led = GPIOOutput.gpio['D2']

    mdns_server = mdns.Server (wifi.radio)
    mdns_server.hostname = configuration['system']['hostname']
    mdns_server.advertise_service (service_type='_http', protocol='_tcp', port=80)

    info (f'using MDNS name of {configuration["system"]["hostname"]}.local')

    #
    # default to station mode
    #
    station = True
    ready = False

    #
    # revert to AP mode if there is no WiFi configuration
    #
    if 'wifi' not in configuration:
        station = False

    if len (configuration['wifi']) == 0:
        station = False

    button_delay = 5
    interval = 0.25
    count = 0

    while True:
        if button.value == False:
            count = min (button_delay / interval, count + 1)

            #
            # blink the LED when ready to change mode
            #
            if count == button_delay / interval:
                led.value = not led.value
        else:
            if count == button_delay / interval:
                led.value = 0
                info ('changing mode')
                station = station ^ True
                ready = False
                count = 0

        if station:
            if not wifi.radio.connected:
                ready = False

            if not ready:
                info ('starting station (client) mode')
                wifi.radio.stop_ap ()
                await asyncio.sleep (0)

                #
                # scan for currently available networks
                #
                networks = []
                for network in wifi.radio.start_scanning_networks ():
                    known = ' '

                    if network.ssid in configuration['wifi']:
                        networks.append (network)
                        known = '*'

                    logger (f'{known} {network.ssid:<32} {network.rssi:>4} {network.channel}')

                wifi.radio.stop_scanning_networks ()

                #
                # connect to the strongest known network
                #
                for network in sorted (networks, key=lambda item: item.rssi, reverse=True):
                    try:
                        wifi.radio.connect (network.ssid, configuration['wifi'][network.ssid]['password'])
                        await asyncio.sleep (0)
                        location = configuration['wifi'][wifi.radio.ap_info.ssid]['location']
                        configuration['system']['location'] = location

                        info (f'connected to access point {wifi.radio.ap_info.ssid}')
                        info (f'location set to {location}')
                        info (f'assigned address of {wifi.radio.ipv4_address}')
                        ready = True
                        break
                    except Exception as e:
                        logger ('\n'.join (traceback.format_exception (e)))
                        error ('unrecoverable condition')
                        microcontroller.reset ()

                #
                # wait and try again if not connected
                #
                if not ready:
                    error (f'failed to connect to a known network, retrying...')
                    await asyncio.sleep (5)

            pass
        else:
            if not ready:
                info ('starting access point (server) mode')
                wifi.radio.stop_station ()
                await asyncio.sleep (0)

                wifi.radio.start_ap (configuration['system']['hostname'])
                await asyncio.sleep (0)

                info (f'assigned address of {wifi.radio.ipv4_address_ap}')

                ready = True

            pass

        await asyncio.sleep (interval)

#
# main task
#
async def main ():
    #
    # encourage garbage collection
    #
    gc.enable ()

    #
    # allow locking between tasks
    #
    lock = asyncio.Lock ()

    #
    # read the persistent configuration data
    #
    with open ('secrets.json') as file:
        configuration = json.load (file)

    #
    # add the variable configuration data
    #
    configuration['system'] = {
        'hostname': 'proximity-' + binascii.hexlify (wifi.radio.mac_address, '-').decode ('utf-8'),
        'location': None
    }

    #
    # create the inputs
    #
    for id, parameters in configuration['beacon'].items ():
        Beacon.factory (id, parameters)

    #
    # create the outputs
    #
    for id, parameters in configuration['output'].items ():
        Output.factory (id, parameters)

    #
    # create the set of independent tasks to run
    #
    tasks = []

    #
    # start a task to listen for WiFi packets as inputs
    #
    tasks.append (asyncio.create_task (packet_sniffer_task (configuration, lock)))

    #
    # start a task to monitor beacon and timeout status
    #
    tasks.append (asyncio.create_task (system_monitor_task (configuration, lock)))

    #
    # start a task to periodically resynchronize the output status
    #
    tasks.append (asyncio.create_task (resynchronize_task (configuration, lock)))

    #
    # start a task to provide a web interface for status and configuration
    #
    tasks.append (asyncio.create_task (web_server_task (configuration, lock)))

    #
    # start a task to monitor button and set system mode
    #
    tasks.append (asyncio.create_task (configuration_task (configuration, lock)))

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
        logger ('\n'.join (traceback.format_exception (e)))
        time.sleep (10)

        #
        # reboot the system
        #
        microcontroller.reset ()

