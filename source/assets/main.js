//
// initialize the page
//
$(document).ready(function() {
    $('.application').hide ();
    //$('#proximity').show ();
    $('#debug').show ();
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
