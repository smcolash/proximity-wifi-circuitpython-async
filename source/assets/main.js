var configuration = {
    'beacon': {},
    'mapping': {},
    'output': {},
    'wifi': {}
};

function isMACID (text) {
  const re = /^([0-9a-fA-F]{2}[:-]){5}([0-9a-fA-F]{2})$/;
  return re.test (text);
}

function create_beacon_config (macid, name) {
    if (!isMACID (macid)) {
        alert ('invalid macid');
        return;
    }

    if (macid in configuration.beacon) {
        alert ('duplicate macid');
        return;
    }

    let item = $('<div class="input-group mb-3">');
    item.append ($('<span class="input-group-text proximity-beacon-label">' + name + '</span>'));
    item.append ($('<input type="text" class="form-control proximity-beacon-macid" value="' + macid + '">'));

    let update = $('<button class="btn btn-outline-secondary proximity-update-beacon" type="button"><img src="file-earmark-check.svg"></button>');
    let remove = $('<button class="btn btn-outline-secondary proximity-delete-beacon" type="button"><img src="trash3.svg"></button>');

    item.append (update);
    item.append (remove);

    $('#configure-beacon').append (item);

    update.click (function () {
        console.log ('TBD...');
        console.log (this);
        console.log (configuration);
    });

    remove.click (function () {
        let macid = $(this).parent ().find ('.proximity-beacon-macid');
        delete configuration.beacon[macid.val ()];
        $(this).parent ().remove ();
    });

    configuration.beacon[macid] = {'name': name, 'enabled': true};
}

$('.proximity-add-beacon').click (function () {
    let name = $(this).parent ().find ('.proximity-beacon-name');
    let macid = $(this).parent ().find ('.proximity-beacon-macid');

    create_beacon_config (macid.val (), name.val ());

    macid.val ('');
    name.val ('');
});










function create_wifi_config (place, ssid, password) {
    if (place == '') {
        alert ('invalid location');
        return;
    }

    if (ssid == '') {
        alert ('invalid ssid');
        return;
    }

    if (password == '') {
        alert ('invalid password');
        return;
    }

    if (ssid in configuration.wifi) {
        alert ('duplicate ssid');
        return;
    }

    let item = $('<div class="input-group mb-3">');
    item.append ($('<span class="input-group-text proximity-config-label">' + place + '</span>'));
    item.append ($('<span class="input-group-text proximity-config-label">' + ssid + '</span>'));
    item.append ($('<input type="password" class="form-control proximity-beacon-password" value="' + password + '">'));

    let update = $('<button class="btn btn-outline-secondary proximity-update-wifi" type="button"><img src="file-earmark-check.svg"></button>');
    let remove = $('<button class="btn btn-outline-secondary proximity-delete-wifi" type="button"><img src="trash3.svg"></button>');

    item.append (update);
    item.append (remove);

    $('#configure-wifi').append (item);

    update.click (function () {
        console.log ('TBD...');
        console.log (this);
        console.log (configuration);
    });

    remove.click (function () {
        let ssid = $(this).parent ().find ('.proximity-wifi-ssid');
        delete configuration.wifi[ssid.val ()];
        $(this).parent ().remove ();
    });

    configuration.wifi[ssid] = {'location': place, 'password': password};
}

$('.proximity-add-wifi').click (function () {
    let place = $(this).parent ().find ('.proximity-wifi-location');
    let ssid = $(this).parent ().find ('.proximity-wifi-ssid');
    let password = $(this).parent ().find ('.proximity-wifi-password');

    create_wifi_config (place.val (), ssid.val (), password.val ());

    place.val ('');
    ssid.val ('');
    password.val ('');
});














//
// download configuration through browser
//
$('.proximity-download-json').click (function () {
    let blob = 'data:text/json;charset=utf-8,' + encodeURIComponent (JSON.stringify (configuration));
    let temp = document.createElement ('a');
    temp.setAttribute ('href', blob);
    temp.setAttribute ('download', 'proximity.json');
    document.body.appendChild (temp);
    temp.click ();
    temp.remove ();
});


function reset_configuration () {
    configuration.wifi = {};
    $('#configure-wifi').empty ();

    configuration.beacon = {};;
    $('#configure-beacon').empty ();
}

function process_configuration (data) {

    console.log (data);


reset_configuration ();

            //
            // populate the WiFi configuration area
            //
            if (!('wifi' in data)) {
                data.wifi = {};
            }

            for (let ssid in data.wifi) {
                let details = data.wifi[ssid];
                create_wifi_config (details.location, ssid, details.password);
            }





            //
            // populate the beacon configuration area
            //
            if (!('beacon' in data)) {
                data.beacon = {};
            }

            for (let macid in data.beacon) {
                let details = data.beacon[macid];
                create_beacon_config (macid, details.name);
            }

}


//
// initialize the page
//
$(document).ready(function() {
    //
    // show the initial page
    //
    $('.application').hide ();
    proximity').show ();
    //$('#configure').show ();



    //
    // get the configuration data
    //
    $.getJSON ('secrets.json')
        .done (function (data) {

            process_configuration (data);



        })
        .fail (function () {
            console.log ('fail...');
        })
        .always (function () {
            console.log ('always...');

            console.log (configuration);
        });
});



const fileInput = document.getElementById ('formFile');




fileInput.addEventListener ('change', (event) => {
  const file = event.target.files[0];
  const reader = new FileReader ();

  reader.onload = (e) => {
    try {
      const data = JSON.parse (e.target.result);
        process_configuration (data);
    } catch (error) {
        alert ('error parsing JSON file');
    }
      //fileInput.value = null;
  };

  reader.readAsText (file);
});

$('.proximity-apply_changes').click (function () {
    console.log (configuration);
});



//
// handle navbar clicks
//
$('.nav-link').click (function () {
    let page = $(this).text ();

    if (page == 'About') {
        window.open ('https://github.com/smcolash/proximity-wifi-circuitpython-async', '_PROJECT');
        return;
    }

    $('.application').hide ();

    if (page == 'Control') {
        $('#control').show ();
        return;
    }

    if (page == 'Debug') {
        $('#debug').show ();
        return;
    }

    if (page == 'Configure') {
        $('#configure').show ();
        return;
    }

    $('#proximity').show ();
});
