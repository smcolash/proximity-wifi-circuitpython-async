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
$(CACHE)/biplane.py :
	$(WGET) \
		--output-document $(CACHE)/biplane.py \
		https://raw.githubusercontent.com/Uberi/biplane/refs/heads/main/biplane.py
	sed -i '/print("response status/d' $(CACHE)/biplane.py

modules :: $(CACHE)/biplane.py

staging ::
	cp -rfp $(CACHE)/biplane.py .staging/lib

#
# add the HMAC key hashing module
#
$(CACHE)/circuitpython_hmac.py :
	$(WGET) \
	    --output-document $(CACHE)/circuitpython_hmac.py \
		https://raw.githubusercontent.com/jimbobbennett/CircuitPython_HMAC/refs/heads/master/circuitpython_hmac.py

modules :: $(CACHE)/circuitpython_hmac.py

staging ::
	cp -rfp $(CACHE)/circuitpython_hmac.py .staging/lib

#
# stage specific library bundle modules
#
staging ::
	cp -rfp $(CACHE)/$(BUNDLE)/lib/adafruit_connection_manager.mpy .staging/lib
	cp -rfp $(CACHE)/$(BUNDLE)/lib/adafruit_hashlib* .staging/lib
	cp -rfp $(CACHE)/$(BUNDLE)/lib/adafruit_ntp* .staging/lib
	cp -rfp $(CACHE)/$(BUNDLE)/lib/adafruit_requests* .staging/lib
	cp -rfp $(CACHE)/$(BUNDLE)/lib/adafruit_ticks* .staging/lib
	cp -rfp $(CACHE)/$(BUNDLE)/lib/asyncio* .staging/lib

