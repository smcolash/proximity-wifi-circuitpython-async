all ::

help ::
	@echo "Environment Setup:"
	@echo
	@echo "  pip3 install esptool"
	@echo "  pip3 install mpremote"
	@echo "  pip3 install adafruit-ampy"
	@echo

#
# - consider changing /usr/lib/python3.6/site-packages/ampy/files.py...
#   BUFFER_SIZE = 512
#

help ::
	@echo "Build Targets:"
	@echo
	@echo "  make all"
	@echo "  make clean"
	@echo "  make download"
	@echo "  make erase"
	@echo "  make flash"
	@echo "  make circuitpython"
	@echo "  make repl"
	@echo "  make list"
	@echo "  make reset"
	@echo
	@echo "  make clean all repl"
	@echo

help ::
	@echo "Build Settings:"
	@echo
	@echo "  PLATFORM = $(PLATFORM)"
	@echo
	@echo "  FIRMWARE_TARGET = $(FIRMWARE_TARGET)"
	@echo "  FIRMWARE_LOCALE = $(FIRMWARE_LOCALE)"
	@echo "  FIRMWARE_VERSION = $(FIRMWARE_VERSION)"
	@echo "  FIRMWARE = $(FIRMWARE)"
	@echo
	@echo "  BUNDLE_VERSION = $(BUNDLE_VERSION)"
	@echo "  BUNDLE_BUILD = $(BUNDLE_BUILD)"
	@echo "  BUNDLE = $(BUNDLE)"
	@echo
	@echo "  USB_SESSION = $(USB_SESSION)"
	@echo "  USB_TTY = $(USB_TTY)"
	@echo "  USB_BAUD = $(USB_BAUD)"

PLATFORM ?= adafruit-circuitpython

#
# CircuitPython firmware: https://circuitpython.org/downloads
#
FIRMWARE_TARGET ?= doit_esp32_devkit_v1
FIRMWARE_LOCALE ?= en_US
FIRMWARE_VERSION ?= 9.2.1
FIRMWARE ?= $(PLATFORM)-$(FIRMWARE_TARGET)-$(FIRMWARE_LOCALE)-$(FIRMWARE_VERSION).bin

#
# CircuitPython module bundle: https://circuitpython.org/libraries
#
BUNDLE_VERSION ?= 9.x
BUNDLE_BUILD ?= 20241128
BUNDLE ?= $(PLATFORM)-bundle-$(BUNDLE_VERSION)-mpy-$(BUNDLE_BUILD)

USB_SESSION ?= REPL
USB_TTY ?= /dev/ttyUSB0
USB_BAUD ?= 921600

download :: firmware bundle

clean ::
	rm -rf .cache

firmware : .cache/$(FIRMWARE)

.cache/$(FIRMWARE) :
	mkdir -p .cache
	cd .cache && wget --no-check-certificate --output-document $(FIRMWARE) https://downloads.circuitpython.org/bin/$(FIRMWARE_TARGET)/$(FIRMWARE_LOCALE)/$(FIRMWARE)

bundle : .cache/$(BUNDLE)

.cache/$(BUNDLE) :
	mkdir -p .cache
	cd .cache && wget --no-check-certificate --output-document $(BUNDLE).zip https://github.com/adafruit/Adafruit_CircuitPython_Bundle/releases/download/$(BUNDLE_BUILD)/$(BUNDLE).zip
	cd .cache && unzip $(BUNDLE)

erase :
	-screen -S $(USB_SESSION) -X quit
	esptool.py --chip esp32 --port $(USB_TTY) --baud $(USB_BAUD) erase_flash

flash :
	-screen -S $(USB_SESSION) -X quit
	esptool.py --port $(USB_TTY) --baud $(USB_BAUD) write_flash -z 0x0 .cache/$(FIRMWARE)

circuitpython :: erase flash list

AMPY = ampy --port $(USB_TTY)

repl ::
	rm -f repl.log
	-screen -S $(USB_SESSION) -X quit
	screen -S $(USB_SESSION) -L -Logfile repl.log $(USB_TTY) 115200
	-screen -S $(USB_SESSION) -X quit

clean ::
	rm -rf repl.log

list :
	-screen -S $(USB_SESSION) -X quit
	$(AMPY) ls --recursive --long_format

reset ::
	-screen -S $(USB_SESSION) -X quit
	$(AMPY) reset

staging ::
	mkdir -p .staging/lib

clean ::
	rm -rf .staging

assets ::

staging :: assets
	mkdir -p .staging
	cp -rf source/* .staging/

upload ::
	cd .staging && find -mindepth 1 -maxdepth 1 -type d | xargs -n 1 $(AMPY) rmdir
	cd .staging && find -mindepth 1 -maxdepth 1 -type d | xargs -n 1 $(AMPY) put
	cd .staging && find -mindepth 1 -maxdepth 1 -type f | xargs -n 1 $(AMPY) put

reload :: download circuitpython staging upload

all :: reload

debug ::
	-screen -S $(USB_SESSION) -X quit
	$(AMPY) run source/code.py


