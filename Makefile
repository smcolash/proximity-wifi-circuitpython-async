#
# use the common build settings
#
include submodules/linux-circuitpython-esp32/mak/circuitpython.mak

staging ::
	cp -rf .cache/$(BUNDLE)/lib/adafruit_connection_manager.mpy .staging/lib
	cp -rf .cache/$(BUNDLE)/lib/adafruit_hashlib* .staging/lib
	cp -rf .cache/$(BUNDLE)/lib/adafruit_ntp* .staging/lib
	cp -rf .cache/$(BUNDLE)/lib/adafruit_requests* .staging/lib
	cp -rf .cache/$(BUNDLE)/lib/adafruit_ticks* .staging/lib
	cp -rf .cache/$(BUNDLE)/lib/asyncio* .staging/lib

#
# select specific web assets
#
#BOOTSTRAP_VERSION = 5.3.2
#JQUERY_VERSION = 3.7.1
#include submodules/linux-circuitpython-esp32/mak/webassets.mak

#staging ::
#	mkdir -p .staging/assets
#	cp -rf source/assets/* .staging/assets/

submodules ::
	git submodule update --init

