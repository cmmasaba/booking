'use strict';

document.getElementById("add-room").addEventListener("click", function(){
    document.getElementById("add-form").hidden = false;
    document.getElementById("list-of-rooms").hidden = true;
    document.getElementById("list-of-bookings-all-rooms").hidden = true;
    document.getElementById("list-of-bookings-one-room").hidden = true;
    document.getElementById("list-of-bookings-filtered-by-day").hidden = true;
})

document.getElementById("list-of-rooms").hidden = false;
document.getElementById("list-of-bookings-all-rooms").hidden = false;
document.getElementById("list-of-bookings-one-room").hidden = false;
document.getElementById("list-of-bookings-filtered-by-day").hidden = false;