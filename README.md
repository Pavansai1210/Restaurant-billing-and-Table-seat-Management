# Restaurant Ordering, Billing and Table Management System

A restaurant system built with Django, Django REST Framework and MySQL.
Customers scan a QR code on a table, order food, and pay. Staff use their own screens.

## Features
- Seat-level table booking with a database lock (no double seating)
- Seat holds expire after 5 minutes, and one network address can have only 2 active holds
- Order, edit, and cancel food within 1 minute
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
1. Install Python 3.13 (tested with 3.13.3) and MySQL 8.
2. `python -m venv venv` then `venv\Scripts\activate`
3. `pip install -r requirements.txt`
4. Copy `.env.example` to `.env` and fill in your values. Do not keep `change-me` as the `SECRET_KEY`. Make a random one with the command below and paste it after `SECRET_KEY=` in `.env`.
   `python -c "from django.core.management.utils import get_random_secret_key; print(get_random_secret_key())"`
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

## Run it through a tunnel (optional, ngrok)
Use this to let someone outside your Wi-Fi try the system while your laptop is running it.
1. Install ngrok, make a free account, and run `ngrok config add-authtoken <your-token>`.
2. In `.env` add your tunnel address (without `https://` for `ALLOWED_HOSTS`, with it for the next line):
   ```
   ALLOWED_HOSTS=127.0.0.1,localhost,your-name.ngrok-free.dev
   CSRF_TRUSTED_ORIGINS=https://your-name.ngrok-free.dev
   TRUST_FORWARDED_FOR=True
   ```
3. Start Django, then in a second window run `ngrok http 8000 --url https://your-name.ngrok-free.dev`
4. In the admin panel, open Settings and save `https://your-name.ngrok-free.dev` (no slash at the end) as the address for table QR codes.

Notes:
- The free ngrok plan shows a warning page first. Click "Visit Site".
- Set `TRUST_FORWARDED_FOR=True` only when the app runs behind a tunnel on your own computer. The app then reads the real visitor address, and only for requests that come from this computer. Without it, every visitor looks like the same address and shares the limit of 2 seat holds. Keep it `False` in all other cases.

## Live demo
- Link: https://unified-goldfish-alkaline.ngrok-free.dev (works only while the demo is running on my laptop)
- The first page is an ngrok warning. Click "Visit Site" to continue.
- Roles to try: customer (scan a table QR code from the admin Tables page), admin, chef, waiter, cashier, gate.
- Demo logins are given in the project form, not in this file.
- Demo video: (add the link here)

## Tests
`python manage.py test`