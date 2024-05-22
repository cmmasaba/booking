# Room Booking Service
This application is a service for scheduling rooms for use. There a numerous rooms and users. <br>
Due to the potential risk of ocerlap in bookings made on a room, the application does validation each time a booking is made to prevent double booking.<br>
In the application it is possible to do the following:
- Add and delete rooms. A room cannot be added twice, and a room cannot be deleted if it has bookings.
- Add or delete bookings on a room. Bookings can only be made if they don't overlap with other bookings on the same room.
- View all bookings for a given day or room, listed in the order of time. When a room is viewed, it should be possible to delete the booking if the user is the one who created it.

## Tech Stacks used
- Python
- FastAPI
- JavaScript
- HTML
- CSS
- Bootstrap
- GCP Firestore for storage
- GCP Firebase for authentication

## Features
- Adding a room, room names are guaranteed to be unique.
- Deleting a room by the user who created it, a room with bookings cannot be deleted.
- Making a booking on a room, bookings are guaranteed to not overlap with each other.
- Listing bookings made by the user, filters like room name or date can be used.
- Editing a booking by the user who created it.
- Deleting a booking by the user who created it.