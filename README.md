# Room Booking Service
This application is a service for scheduling rooms for use. There a numerous rooms and users. <br>
Due to the potential risk of overlap in bookings made on a room, the application does validation each time a booking is made to prevent double booking.<br>


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