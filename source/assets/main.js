function create_beacon_config (macid, name) {
    let item = $('<div class="input-group mb-3">');
    item.append ($('<span class="input-group-text proximity-beacon-label">' + name + '</span>'));
    item.append ($('<input type="text" class="form-control" value="' + macid + '">'));
    item.append ($('<button class="btn btn-outline-secondary proximity-update-beacon" type="button"><img src="file-earmark-check.svg"></button>'));
    item.append ($('<button class="btn btn-outline-secondary proximity-delete-beacon" type="button"><img src="trash3.svg"></button>'));

    $('#configure-beacons').append (item);
}

$('.proximity-add-beacon').click (function () {
    console.log ($(this).parent ());
    create_beacon_config ('aa:aa:aa:aa:aa', 'another');
});

$('.proximity-delete-beacon').click (function () {
    console.log (this);
});



//
// initialize the page
//
$(document).ready(function() {
    //
    // show the initial page
    //
    $('.application').hide ();
    //proximity').show ();
    $('#configure').show ();



    //
    // get the configuration data
    //
    $.getJSON ('secrets.json')
        .done (function (data) {
            console.log (data);




            //
            // populate the beacon configuration area
            //
            for (let macid in data.beacon) {
                let details = data.beacon[macid];
                create_beacon_config (macid, details.name);
            }



        })
        .fail (function () {
            console.log ('crud...');
        })
        .always (function () {
            console.log ('always...');
        });





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
