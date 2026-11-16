# Restaurant Ordering, Billing and Table Management System

A restaurant system built with Django, Django REST Framework and MySQL.
Customers scan a QR code on a table, order food, and pay. Staff use their own screens.

## Features
- Seat-level table booking with a database lock (no double seating)
- Seat holds expire after 5 minutes, and one network address can have only 2 active holds
- Order, edit, and cancel food within 2 minutes
- Ring the kitchen when an order is late
- Chef, waiter, cashier and gate screens
- Cash or online payment, receipt QR code, exit check at the gate
- Online payment is a practice payment (no real money)
- Cashier can close a visit that left without paying. Only served food is charged, unserved food is cancelled, and the amount stays on record. The customer can settle it later at the cashier and then leave through the gate.
- Our own admin panel with an audit log (no Django administration)
- Food photos uploaded by the admin (cleaned and re-saved as JPEG)
- Pages refresh every few seconds (no WebSockets)

## Security
- Own Staff table with JWT login, role checks and a login lockout (5 wrong tries = 15 minutes)
- The API denies access by default. Every view must name who may use it.
- Secrets are kept in `.env`, which is never uploaded

## Run it
1. Install Python 3.12 and MySQL 8.
2. `python -m venv venv` then `venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in your values.
5. In MySQL, create the database and a user:
   ```sql
   CREATE DATABASE restaurant_db;
   CREATE USER 'restaurant_user'@'localhost' IDENTIFIED BY 'your-password';
   GRANT ALL ON restaurant_db.* TO 'restaurant_user'@'localhost';
   ```
   Use the same password for `DB_PASSWORD` in your `.env`.
6. `python manage.py migrate`
7. `python manage.py create_admin yourname`
8. `python manage.py runserver 0.0.0.0:8000`

With `DEBUG=False`, run `python manage.py collectstatic --noinput` first, and start the server with `--insecure`.

## Tests
`python manage.py test`