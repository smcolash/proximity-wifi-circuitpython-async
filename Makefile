#
# use the common build settings
#
all :: submodules
submodules ::
	git submodule update --init --remote

#
# boilerplate support
#
ifneq ($(findstring submodules,$(MAKECMDGOALS)),submodules)
include submodules/linux-circuitpython-esp32/mak/circuitpython.mak
endif

#
# add the biplane web server module
#
download ::
	curl --output .cache/biplane.py https://raw.githubusercontent.com/Uberi/biplane/refs/heads/main/biplane.py
	sed -i '/print("response status/d' .cache/biplane.py

staging ::
	cp -rf .cache/biplane.py .staging/lib

#
# add the HMAC key hashing module
#
download ::
	curl --output .cache/circuitpython_hmac.py https://raw.githubusercontent.com/jimbobbennett/CircuitPython_HMAC/refs/heads/master/circuitpython_hmac.py

staging ::
	cp -rf .cache/circuitpython_hmac.py .staging/lib

#
# stage specific library bundle modules
#
staging ::
	cp -rf .cache/$(BUNDLE)/lib/adafruit_connection_manager.mpy .staging/lib
	cp -rf .cache/$(BUNDLE)/lib/adafruit_hashlib* .staging/lib
	cp -rf .cache/$(BUNDLE)/lib/adafruit_ntp* .staging/lib
	cp -rf .cache/$(BUNDLE)/lib/adafruit_requests* .staging/lib
	cp -rf .cache/$(BUNDLE)/lib/adafruit_ticks* .staging/lib
	cp -rf .cache/$(BUNDLE)/lib/asyncio* .staging/lib

#
# stage project web assets
#
staging ::
	mkdir -p .staging/assets
	cp -rf source/assets/* .staging/assets/

