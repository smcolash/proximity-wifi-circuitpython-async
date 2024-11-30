import json

from output import Output
from beacon import Beacon

#
# read the secrets and definitions
#
data = {}
with open ('secrets.json') as file:
    data = json.load (file)

#
# get the network configuration
#
networks = data['wifi']
ssid = None

#
# create and initialize all of the devices and beacons
#
for name, details in data['output'].items ():
    Output.factory (name, details)

for macid, details in data['beacon'].items ():
    Beacon.factory (macid, details)

