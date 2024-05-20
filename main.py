from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import google.oauth2.id_token
from google.auth.transport import requests
import starlette.status as status
from google.cloud import firestore
from google.cloud.firestore_v1.base_query import FieldFilter, Or
import datetime

# define the app that will contain all of our routing for Fast API
app = FastAPI()

# Initialize Firestore client for database operations
firestore_db = firestore.Client()

# Set up request adapter for Firebase authentication
firebase_request_adapter = requests.Request()

# Define the static and templates directories
app.mount('/static', StaticFiles(directory='static'), name='static')
templates = Jinja2Templates(directory="templates")

# Function to retrieve user data from Firestore or create a default user if not found
def getUser(user_token):
    user = firestore_db.collection('users').document(user_token['user_id'])
    if not user.get().exists:
        user_data = {
            "username": '',
            "rooms_list": []
        }
        firestore_db.collection('users').document(user_token['user_id']).set(user_data)
    return user

# Function to validate Firebase ID token and retrieve user information
def validateFirebaseToken(id_token):
    if not id_token:
        return None
    
    user_token = None
    try:
        user_token = google.oauth2.id_token.verify_firebase_token(id_token, firebase_request_adapter)
    except ValueError as err:
        print(str(err))

    return user_token

# Route for the main page, handling user and guest authentication
@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    # Query firebase for the request token. An error message is set in case we want to output an error to 
    # the user in the template.
    id_token = request.cookies.get("token")
    error_message = "No error here"
    user_token = None
    user = None

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "error_message": None, "user_info": None})
    
    user = getUser(user_token).get()
    rooms = []
    for room in firestore_db.collection('rooms').stream():
        rooms.append(room)
    return templates.TemplateResponse('main.html', {"request": request, "user_token": user_token, "error_message": error_message, "user_info": user, "rooms_list": rooms, "all_bookings": None, "one_room_bookings": None})

@app.get('/set-username', response_class=HTMLResponse)
async def setUsername(request: Request):
    """Route (GET) for setting the username when a user logs in for the first time."""
    id_token = request.cookies.get("token")
    errors = ""
    user_token = None
    user = None

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "errors": None, "user_info": None})
    
    user = getUser(user_token).get()

    context_dict = dict(
        request=request,
        user_token=user_token,
        errors=errors,
        user_info=user,
    )

    return templates.TemplateResponse('set-username.html', context=context_dict)

@app.post('/set-username', response_class=HTMLResponse)
async def setUsername(request: Request):
    """Route (POST) for setting the username.
    
    If the username is taken, redisplay the form with the error message.
    """
    id_token = request.cookies.get("token")
    user_token = None
    errors = ''

    user_token = validateFirebaseToken(id_token)

    form = await request.form()

    user_exists = firestore_db.collection("users").where(filter=FieldFilter('username', '==', form['username'])).get()
    if user_exists:
        errors = 'This username is already taken.'
        return templates.TemplateResponse('set-username.html', {"request": request, "user_token": None, "errors": errors, "user_info": None,})
    firestore_db.collection('users').document(user_token['user_id']).update({"username": form["username"]})
    return RedirectResponse("/", status_code=status.HTTP_302_FOUND)

@app.post("/add-room", response_class=RedirectResponse)
async def addRoom(request: Request):
    """Gets the data from the form and adds it to Firestore."""
    id_token = request.cookies.get("token")
    user_token = None
    user = None
    errors = ''

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "errors": errors, "user_info": None})
    
    # get form data from the html page
    form = await request.form()

    user = getUser(user_token)
    # rooms are linked to users via keys. Get list of rooms for that user, add the new room to list, then update the list under user
    rooms = user.get().get('rooms_list')
    rooms_list = []
    for room in firestore_db.collection('rooms').stream():
        rooms_list.append(room.get("name"))
    
    if form["roomName"] not in rooms_list:
        # create a transaction object and the document reference object, then set the data and commit to save
        transaction = firestore_db.transaction()
        rooms_ref = firestore_db.collection('rooms').document()
        transaction.set(rooms_ref, {'name': form['roomName'], 'days':[], 'owner': user_token['email'], 'user_id': user.id, 'date_created': str(datetime.date.today())})
        transaction.commit()
        rooms.append(rooms_ref)
        user.update({'rooms_list': rooms})
        return RedirectResponse('/', status.HTTP_302_FOUND)
    else:
        errors = "A room with that name already exists"
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "errors": errors, "user_info": None})

@app.get("/book-room", response_class=HTMLResponse)
async def bookRoom(request: Request):
    """Returns a form for booking a room."""
    id_token = request.cookies.get("token")
    user_token = None
    user = None
    errors = ''

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "errors": errors, "user_info": None})

    user = getUser(user_token)
    # get the related rooms and store their names in a list
    rooms_list = []
    for room in firestore_db.collection("rooms").stream():
        rooms_list.append(room.get("name"))
    return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list,
                                                         "min_date": datetime.datetime.today().strftime("%Y-%m-%d"), "min_time": datetime.datetime.now().time().strftime("%H:%M")})

@app.post("/book-room", response_class=RedirectResponse)
async def bookRoom(request: Request):
    """Creates a booking for a room on the specified date."""
    id_token = request.cookies.get("token")
    user_token = None
    user = None
    errors = ''

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "errors": errors, "user_info": None})
    
    # get form data from the html page
    form = await request.form()

    rooms = firestore_db.collection("rooms").stream()

    if form["bookingStartTime"] >= form["bookingEndTime"]:
        rooms_list = [room.get("name") for room in rooms]
        errors = "Invalid start and end time selected"
        return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list})
    
    if datetime.date.fromisoformat(form['bookingDate']) < datetime.date.today():
        rooms_list = [room.get("name") for room in rooms]
        errors = "Select a present or future date"
        return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list})  
    
    if datetime.date.fromisoformat(form['bookingDate']) == datetime.date.today():
        '''If booking date is today and booking time is past'''
        if datetime.time.fromisoformat(form['bookingStartTime']) < datetime.time.fromisoformat(datetime.datetime.now().time().isoformat(timespec='minutes')):
            rooms_list = [room.get("name") for room in rooms]
            errors = "Select a valid time"
            return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list})

    user = getUser(user_token)

    try:
        *_, room_query = firestore_db.collection("rooms").where(filter=FieldFilter('name', '==', form['roomName'])).get()
    except ValueError:
        rooms_list = [room.get("name") for room in rooms]
        errors = "The selected room is no longer available"
        return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list})

    #  get the dates associated with the room
    dates = [day.get().get('date') for day in room_query.get('days')]

    transaction = firestore_db.transaction()
    if form["bookingDate"] not in dates:
        """The day we want to add booking for is not in the room yet.
        
        There is no validation to do for bookings since there will be no bookings.
        Create a ref object for the new day document, build a dict for the booking info,
        and save it in a transaction.
        Then update the room's days list to include the new day ref.
        """
        days_ref = firestore_db.collection('days').document()
        room_booking = {
            'name': form['eventName'],
            'date': form['bookingDate'],
            'room': form['roomName'],
            'from': form['bookingStartTime'],
            'to': form['bookingEndTime'],
            'user': user.id
        }
        transaction.set(days_ref, {'date': form['bookingDate'], 'room': form['roomName'], 'bookings':[room_booking,]})
        transaction.commit()
        days_list = room_query.get("days")
        days_list.append(days_ref)
        room_ref = room_query.reference
        room_ref.update({'days': days_list})
    else:
        """The day we want to add booking for is in the room.
        
        We do validation for bookings.
        Iterate through the days in the room, checking if the day matches our target.
        Once we find a match we iterate through the bookings associated with that day
        and do two checks to validate the new booking.
        1. We check if the booking end time given in the form is greater than the start
        time of the current booking we are iterating over.
        2. We check if the booking start time given in the form is less than the end
        time of the current booking we are iterating over.
        If both the conditions are true then the user is trying to book a meeting in a time
        slot that is already booked so we raise an exception.
        If we iterate through the days without raising an exception it means the booking is
        valid so we follow same steps as above to add it.
        """
        days = room_query.get("days")
        day = days[dates.index(form['bookingDate'])]
        for booking in day.get().get("bookings"):
            if form["bookingEndTime"] > booking["from"] and form["bookingStartTime"] < booking["to"]:
                rooms_list = [room.get("name") for room in rooms]
                errors = f"The room is already booked in this time slot: {booking['name']}, {booking['date']}, {booking['room']}, from {booking['from']} to {booking['to']}"
                return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list})

            room_booking = {
                'name': form['eventName'],
                'date': form['bookingDate'],
                'room': form['roomName'],
                'from': form['bookingStartTime'],
                'to': form['bookingEndTime'],
                'user': user.id
            }
            bookings_list = day.get().get('bookings')
            bookings_list.append(room_booking)
            day.update({"bookings": bookings_list})
        
    return RedirectResponse('/', status.HTTP_302_FOUND)

@app.get('/view-bookings')
async def viewBookings(request: Request):
    """Show all the bookings the user has made on all the rooms."""
    id_token = request.cookies.get("token")
    user_token = None
    user = None

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "error_message": None, "user_info": None})

    user = getUser(user_token).get()
    rooms = [room.get("name") for room in firestore_db.collection("rooms").stream()]

    bookings_list = []
    for day in firestore_db.collection("days").stream():
        for booking in day.get('bookings'):
            if booking['user'] == user.id:
                bookings_list.append(booking)
    return templates.TemplateResponse('view-bookings.html', {"request": request, "user_token": user_token, "error_message": None, "user_info": user, "rooms": rooms, "bookings": bookings_list})

@app.post('/view-bookings')
async def filterByRoomAndDay(request: Request):
    """Show all the bookings the user has made on one the rooms."""
    id_token = request.cookies.get("token")
    user_token = None
    user = None

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "error_message": None, "user_info": None})
    
    # get form data from the html page
    form = await request.form()
    date = form['date']
    room = form['room']

    user = getUser(user_token).get()

    bookings_list = []
    if date:
        for day in firestore_db.collection("days").where(filter=FieldFilter('date', '==', date)).stream():
            for booking in day.get('bookings'):
                if room:
                    if booking['user'] == user.id and booking['room'] == room:
                        bookings_list.append(booking)
                else:
                    bookings_list.append(booking)
    elif room:
        for day in firestore_db.collection("days").stream():
            for booking in day.get('bookings'):
                if booking['user'] == user.id and booking['room'] == room:
                        bookings_list.append(booking)
    else:
        for day in firestore_db.collection("days").stream():
            for booking in day.get('bookings'):
                if booking['user'] == user.id:
                    bookings_list.append(booking)
    return templates.TemplateResponse('view-bookings.html', {"request": request, "user_token": user_token, "error_message": None, "user_info": user, "bookings": bookings_list})

@app.post('/delete-booking')
async def deleteBooking(request: Request):
    """Delete a booking."""
    id_token = request.cookies.get("token")
    user_token = None
    user = None

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "error_message": None, "user_info": None})
    
    # get form data from the html page
    form = await request.form()

    try:
        *_, room = firestore_db.collection('rooms').where(filter=FieldFilter('name', '==', form['room'])).get()
    except ValueError:
        pass

    for day in room.get('days'):
        if day.get().get('date') == form['date']:
            bookings = day.get().get('bookings')
            for index, value in enumerate(bookings):
                if value.get("from") == form['from'] and value.get("to") == form['to']:
                    del bookings[index]
            day.update({'bookings': bookings})

    return RedirectResponse('/', status.HTTP_302_FOUND)

@app.get('/edit-booking')
async def editBooking(request: Request, booking_room: str, date: str, start: str, end: str, ):
    """Edit a booking.
    
    Why delete a booking first when updating? A lot of information can change when a booking is updated,
    notably the Room and Day. In that case we would have to delete the existing booking in the current day
    and room then update it in the new day and room. Considering this is a possibility then it does no harm
    to delete the booking right away an update is initiated, then recreate a new booking with the new information.
    """
    id_token = request.cookies.get("token")
    user_token = None
    user = None

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "error_message": None, "user_info": None})
    
    # get form data from the html page
    #form = await request.form()

    user = getUser(user_token).get()

    rooms = [room.get("name") for room in firestore_db.collection("rooms").stream()]

    *_, room = firestore_db.collection("rooms").where(filter=FieldFilter('name', '==', booking_room)).get()
    for day in room.get('days'):
        if day.get().get('date') == date:
            bookings = day.get().get('bookings')
            for index, value in enumerate(bookings):
                if value.get("from") == start and value.get("to") == end:
                    booking = {
                        'event': bookings[index].get('name'),
                        'date': bookings[index].get('date'),
                        'room': bookings[index].get('room'),
                        'from': bookings[index].get('from'),
                        'to': bookings[index].get('to')
                    }
                    del bookings[index]
                    day.update({'bookings': bookings})
                    return templates.TemplateResponse('edit-booking.html', {"request": request, "user_token": user_token, "error_message": None, "user_info": user, "booking": booking, "rooms_list": rooms})

@app.post('/edit-booking')
async def editBooking(request: Request):
    """Edit a booking."""
    id_token = request.cookies.get("token")
    user_token = None
    user = None

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "error_message": None, "user_info": None})
    
    # get form data from the html page
    form = await request.form()

    rooms = firestore_db.collection("rooms").stream()

    if form["bookingStartTime"] >= form["bookingEndTime"]:
        rooms_list = [room.get("name") for room in rooms]
        errors = "Invalid start and end time selected"
        return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list})

    if datetime.date.fromisoformat(form['bookingDate']) < datetime.date.today():
        rooms_list = [room.get("name") for room in rooms]
        errors = "Select a present or future date"
        return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list})  

    if datetime.date.fromisoformat(form['bookingDate']) == datetime.date.today():
        '''If booking date is today and booking time is past'''
        if datetime.time.fromisoformat(form['bookingStartTime']) < datetime.time.fromisoformat(datetime.datetime.now().time().isoformat(timespec='minutes')):
            rooms_list = [room.get("name") for room in rooms]
            errors = "Select a valid time"
            return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list})

    user = getUser(user_token).get()

    try:
        *_, room_query = firestore_db.collection("rooms").where(filter=FieldFilter('name', '==', form['roomName'])).get()
    except ValueError:
        rooms_list = [room.get("name") for room in rooms]
        errors = "The selected room is no longer available"
        return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list})

    # validation for day and bookings
    dates = [day.get().get('date') for day in room_query.get('days')]

    transaction = firestore_db.transaction()
    if form["bookingDate"] not in dates:
        days_ref = firestore_db.collection('days').document()
        room_booking = {
            'name': form['eventName'],
            'date': form['bookingDate'],
            'room': form['roomName'],
            'from': form['bookingStartTime'],
            'to': form['bookingEndTime'],
            'user': user.id
        }
        transaction.set(days_ref, {'date': form['bookingDate'], 'bookings':[room_booking,]})
        transaction.commit()
        days_list = room_query.get("days")
        days_list.append(days_ref)
        room_ref = room_query.reference
        room_ref.update({'days': days_list})
    else:
        days = room_query.get("days")
        day = days[dates.index(form['bookingDate'])]
        for booking in day.get().get("bookings"):
            if form["bookingEndTime"] > booking["from"] and form["bookingStartTime"] < booking["to"]:
                rooms_list = [room.get("name") for room in rooms]
                errors = f"The room is already booked in this time slot: {booking['name']}, {booking['date']}, {booking['room']}, from {booking['from']} to {booking['to']}"
                return templates.TemplateResponse('book-room.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms_list})

        room_booking = {
            'name': form['eventName'],
            'date': form['bookingDate'],
            'room': form['roomName'],
            'from': form['bookingStartTime'],
            'to': form['bookingEndTime'],
            'user': user.id
        }
        bookings_list = day.get().get('bookings')
        bookings_list.append(room_booking)
        day.update({"bookings": bookings_list})
    return RedirectResponse('/', status.HTTP_302_FOUND)

@app.post('/delete-room')
async def deleteRoom(request: Request):
    """Delete a room."""
    id_token = request.cookies.get("token")
    user_token = None
    user = None
    errors = ''

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "errors": None, "user_info": None})
    
    # get form data from the html page
    form = await request.form()

    user = getUser(user_token)

    if form['user'] != user.id:
        rooms = firestore_db.collection('rooms').stream()
        errors = 'Rooms can only be deleted by the person who created it.'
        return templates.TemplateResponse('main.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms, "all_bookings": None, "one_room_bookings": None, "filteredbookings": None})

    *_, room_query = firestore_db.collection('rooms').where(filter=FieldFilter('name', '==', form['room'])).where(filter=FieldFilter('user_id', '==', form['user'])).get()
    days = room_query.get('days')
    
    for day_index, day in enumerate(days):
        """Check if the room has bookings associated."""
        if day.get().get('bookings'):
            rooms = firestore_db.collection('rooms').stream()
            errors = 'Cannot delete room with bookings'
            return templates.TemplateResponse('main.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms, "all_bookings": None, "one_room_bookings": None, "filteredbookings": None})
        else:
            days[day_index].delete()
            del days[day_index]

    user_rooms = user.get().get('rooms_list')
    room_names = [room.get().get("name") for room in user_rooms]
    room_index = room_names.index(form['room'])
    room_query.reference.update({'days':[]})
    user_rooms[room_index].delete()
    del user_rooms[room_index]
    user.update({'rooms_list': user_rooms})

    return RedirectResponse('/', status.HTTP_302_FOUND)

@app.get("/view-room/{room}", response_class=RedirectResponse)
async def viewRoom(request: Request, room: str):
    """Gets the details of a specified room."""
    id_token = request.cookies.get("token")
    user_token = None
    user = None

    user_token = validateFirebaseToken(id_token)

    # Validate user token - check if we have a valid firebase login if not return the template with empty data as we will show the login box
    if not user_token:
        return templates.TemplateResponse('main.html', {"request": request, "user_token": None, "error_message": None, "user_info": None})

    # get form data from the html page
    # form = await request.form()

    user = getUser(user_token)
    bookings = []
    try:
        *_, room_query = firestore_db.collection('rooms').where(filter=FieldFilter('name', '==', room)).get()
    except ValueError:
        rooms = firestore_db.collection('rooms').stream()
        errors = 'The selected room is no longer available.'
        return templates.TemplateResponse('main.html', {"request": request, "user_token": user_token, "errors": errors, "user_info": user, "rooms_list": rooms, "all_bookings": None, "one_room_bookings": None, "filteredbookings": None})

    for day in room_query.get("days"):
        if day.get().get("bookings"):
            '''Only add to bookings if the list of bookings associated with this day is not empty.'''
            bookings.append({day.get().get('date'): [item for item in day.get().get("bookings")]})

    return templates.TemplateResponse('view-room.html', {"request": request, "user_token": user_token, "error_message": None, "user_info": user, "room": room_query, "bookings": bookings})