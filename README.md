# Restaurant Ordering, Billing and Table Management System

A restaurant system built with Django, Django REST Framework and MySQL.
Customers scan a QR code on a table, order food, and pay. Staff use their own screens.

## Features
- Seat-level table booking with a database lock (no double seating)
- Order, edit, and cancel food within 2 minutes
- Ring the kitchen when an order is late
- Chef, waiter, cashier and gate screens
- Cash or online (practice) payment, receipt QR code, exit check
- Our own admin panel with an audit log (no Django administration)
- Food photos uploaded by the admin

## Run it
1. Install Python 3.12 and MySQL 8.
2. `python -m venv venv` then `venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in your values.
5. Create the database `restaurant_db`.
6. `python manage.py migrate`
7. `python manage.py create_admin yourname`
8. `python manage.py runserver 0.0.0.0:8000`

## Tests
`python manage.py test`