#
# Bootstrap assets
#
BOOTSTRAP_VERSION ?= 5.3.2

BOOTSTRAP_CSS ?= https://cdn.jsdelivr.net/npm/bootstrap@$(BOOTSTRAP_VERSION)/dist/css/bootstrap.min.css
BOOTSTRAP_JS ?= https://cdn.jsdelivr.net/npm/bootstrap@$(BOOTSTRAP_VERSION)/dist/js/bootstrap.bundle.min.js

#
# jQuery assets
#
JQUERY_VERSION ?= 3.7.1

JQUERY_JS ?= https://code.jquery.com/jquery-$(JQUERY_VERSION).min.js

#
# download assets from their CDNs
#
webassets :: download/css/bootstrap.min.css
download/css/bootstrap.min.css :
	mkdir -p download/css
	wget --no-check-certificate --output-document $@ $(BOOTSTRAP_CSS)

webassets :: download/js/bootstrap.bundle.min.js
download/js/bootstrap.bundle.min.js :
	mkdir -p download/js
	wget --no-check-certificate --output-document $@ $(BOOTSTRAP_JS)

webassets :: download/js/jquery.min.js
download/js/jquery.min.js :
	mkdir -p download/js
	wget --no-check-certificate --output-document $@ $(JQUERY_JS)

download :: webassets

clean ::
	rm -rf download

#
# prepare the assets to be copied to the target
#
package :: download
	mkdir -p root/assets/
	cp -rf download/css root/assets/
	cp -rf download/js root/assets/

