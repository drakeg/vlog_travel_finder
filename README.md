
# Vlog Travel Finder

Flask app to manage and search travel-related places (restaurants, breweries, museums, festivals, etc.) and attach links to your content (YouTube, TikTok).

## Features

- **Auth (site-wide)**
  - Register: `/register`
  - Login: `/login`
  - Logout: `/logout`
- **Admin**
  - Access control: toggle anonymous access for features (blog/places/contact/about/etc.)
  - Anonymous preview mode (admins can simulate logged-out access)
  - Manage categories
  - Create / edit / delete places
  - Export all place data to CSV for backup or spreadsheet review
  - Import exported-format CSV files to restore, bulk-create, or bulk-update places
  - Manage blog posts
  - View contact messages
- **Public**
  - Home, places search, blog, contact, about
  - Registered users can save/bookmark places and revisit them from a personal Saved Places page
  - Registered users can organize destinations into private named trip lists
  - Trip lists support planning notes and explicit ordered stops
  - Trips can include start/end dates and per-stop planning notes
  - Trip stops can be scheduled with an optional planned date and time
  - Multiple trip stops can be assigned to or cleared from a planned date in one bulk action
  - Selected stops can receive sequential planned times from a chosen start time and interval
  - Selected itinerary stops can be copied into another owned trip without duplicating existing places
  - Scheduled stops are presented in day-by-day itinerary groups with unscheduled stops kept visible
  - Itinerary days can open their ordered routable stops as a Google Maps driving route without a paid API
  - Trips have print-friendly, plain-text, and iCalendar (.ics) itinerary exports
  - Existing trips can be duplicated as independent editable copies, optionally shifted to a new start date
  - Saved places can be added to trips individually or in bulk
  - Filter destinations by whether they have already been featured in your vlog
  - Sort place results by location, name, or newest additions
  - Browse filtered place results 24 at a time with persistent search and sort controls
  - Open saved places in Google Maps using coordinates or address data

## Development process

Project development follows documented sprint, coding, testing, and contribution standards:

- [Contributing](CONTRIBUTING.md)
- [Sprint process](docs/SPRINTS.md)
- [Coding standards](docs/CODING_STANDARDS.md)
- [Testing and CI](docs/TESTING.md)

Feature and bug work should be tracked in GitHub Issues, implemented in focused pull requests, and merged only after required CI is green. Tests and documentation are part of the definition of done.

## Docker Compose local development

Docker Compose can run the app and the test suite without creating a host Python virtual environment.

### Start the app

Copy the example environment file and adjust values as needed:

```bash
cp .env.example .env
docker compose up --build
```

The host port defaults to `5000` and can be changed with `APP_PORT`.

Then open:

- Public site: `http://127.0.0.1:5000/`
- Login: `http://127.0.0.1:5000/login`
- Admin: `http://127.0.0.1:5000/admin`

The app stores its SQLite database and uploaded instance data in the named `vlog_instance` volume, so local data survives container recreation.

### Run tests

```bash
docker compose run --rm test
```

This runs the same `python -m pytest -q` test command used by CI.

### Database commands

The app initializes and upgrades its SQLite schema automatically when it starts. You can also run the CLI commands explicitly:

```bash
docker compose run --rm app python -m flask --app vlog_site:create_app init-db
docker compose run --rm app python -m flask --app vlog_site:create_app upgrade-db
```

### Create or promote an admin

Create an admin interactively:

```bash
docker compose run --rm app python -m flask --app vlog_site:create_app create-admin
```

Or promote an existing account:

```bash
docker compose run --rm app python -m flask --app vlog_site:create_app promote-admin you@example.com
```

### Stop the app

```bash
docker compose down
```

To also remove the persisted local SQLite data, remove the named volume:

```bash
docker compose down -v
```

The virtualenv workflow below remains fully supported.

## Local setup

### 1) Create a virtualenv and install deps

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Tests

Run the same test command locally that CI uses:

```bash
python -m pytest -q
```

GitHub Actions runs the test suite on pull requests and pushes to `main` using Python 3.12 and 3.13.

### 2) Initialize the database

```bash
export FLASK_APP=vlog_site:create_app
flask init-db
```

This creates the SQLite DB in `./instance/vlog_site.sqlite` (if it doesn't exist) and is safe to re-run.

### Upgrading the database schema (no data loss)

When you pull new code that changes the DB structure, run:

```bash
export FLASK_APP=vlog_site:create_app
flask upgrade-db
```

This applies versioned schema upgrades using SQLite's `PRAGMA user_version` and **does not wipe existing data**.

### 3) Create an admin user

```bash
export FLASK_APP=vlog_site:create_app
flask create-admin
```

If the user already exists (for example, created via `/register`), promote them:

```bash
export FLASK_APP=vlog_site:create_app
flask promote-admin you@example.com
```

### 4) Run the dev server

```bash
export FLASK_APP=vlog_site:create_app
export FLASK_ENV=development
flask run
```

Open:

- Public site: `http://127.0.0.1:5000/`
- Login: `http://127.0.0.1:5000/login`
- Admin: `http://127.0.0.1:5000/admin`

## Access control

As an admin, configure anonymous access for each feature:

- Admin page: `http://127.0.0.1:5000/admin/access-control`
- Use **Preview as anonymous** in the navbar to simulate logged-out access without logging out.
- While preview is active, member-only pages and actions are treated as unauthenticated; the admin can still use **Stop preview** to return to the authenticated session.

## CSRF protection

State-changing browser form requests are protected with a per-session CSRF token. Rendered POST forms include the token automatically, and missing or invalid tokens receive HTTP 400.

CSRF protection is enabled by default. It can be disabled explicitly with `CSRF_ENABLED=false` for controlled test environments only; production deployments should leave it enabled.

## Production configuration safeguards

Set `APP_ENV=production` for production deployments. Startup will reject a default, placeholder, or shorter-than-32-character `SECRET_KEY`, disabled `CSRF_ENABLED`, disabled `SESSION_COOKIE_SECURE`, or enabled `FLASK_DEBUG`. Generate a unique random signing secret; do not use the example `.env` value. These checks are opt-in so the local HTTP workflow remains unchanged. Serve the production app over HTTPS before enabling Secure cookies, and configure TLS at the hosting platform or reverse proxy.

## Configuration

- `APP_ENV`
  - Defaults to `development`. Set to `production` to enable mandatory startup checks.
- `SECRET_KEY`
  - Set this in production (do not use `dev`).
- `DATABASE_URL`
  - SQLAlchemy database URL. Defaults to SQLite.
- `SESSION_COOKIE_SECURE`
  - Defaults to `false` for local HTTP development. Set to `true` when the site is served over HTTPS in production.
- Session cookies are explicitly `HttpOnly` and `SameSite=Lax`.
- `CSRF_ENABLED`
  - Defaults to `true`. Disable only in controlled test environments.
- `SECURITY_HSTS_ENABLED`
  - Defaults to `false` for local HTTP development. Set to `true` only when the site is served over HTTPS.
- `SECURITY_HSTS_MAX_AGE`
  - Defaults to `31536000` seconds (one year) when HSTS is enabled.
- Responses also include `X-Content-Type-Options: nosniff`, `X-Frame-Options: SAMEORIGIN`, `Referrer-Policy: strict-origin-when-cross-origin`, and a restrictive camera/microphone/geolocation `Permissions-Policy`.

Example:

```bash
export SECRET_KEY='your-long-random-string'
export DATABASE_URL='sqlite:////absolute/path/to/vlog_site.sqlite'
export SESSION_COOKIE_SECURE=true
export SECURITY_HSTS_ENABLED=true
export SECURITY_HSTS_MAX_AGE=31536000

# Postgres example:
# export DATABASE_URL='postgresql+psycopg://user:password@localhost:5432/vlog_site'

# MySQL example:
# export DATABASE_URL='mysql+pymysql://user:password@localhost:3306/vlog_site'
```

## Deploying on PythonAnywhere (uWSGI)

PythonAnywhere runs your Flask app via a WSGI entrypoint.

### Web app setup

- In the PythonAnywhere **Web** tab, create a new **Flask** web app (manual configuration is fine).
- Set your **Source code** directory to your project (the folder that contains `app.py`).
- Create and select a **virtualenv**.
- Install requirements:

```bash
pip install -r requirements.txt
```

### WSGI configuration

Edit your PythonAnywhere WSGI config file (Web tab -> WSGI configuration file) and ensure it loads this project.

This project provides `app.py` which creates the Flask app as `app = create_app()`. You can expose it as the WSGI `application` like this:

```python
import os
import sys

# Update this path to the repo root (the folder that contains app.py and vlog_site/).
# Example:
# project_home = "/home/drakeg/vlog_travel_finder"
project_home = "/home/YOUR_USERNAME/vlog_travel_finder"
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Production config (set these in the Web tab -> Environment variables if you prefer).
os.environ.setdefault("SECRET_KEY", "change-me")
os.environ.setdefault(
    "DATABASE_URL",
    "sqlite:////home/YOUR_USERNAME/vlog_travel_finder/instance/vlog_site.sqlite",
)

from app import app as application
```

### Environment variables

Recommended approach on PythonAnywhere is to set these in **Web tab -> Environment variables**:

- `SECRET_KEY`
- `DATABASE_URL`

SQLite example `DATABASE_URL` for PythonAnywhere:

```text
sqlite:////home/YOUR_USERNAME/vlog_site/instance/vlog_site.sqlite
```

### Database initialization

After the web app is created and the virtualenv is active:

```bash
export FLASK_APP=vlog_site:create_app
flask init-db
```

Then create or promote an admin:

```bash
export FLASK_APP=vlog_site:create_app
flask create-admin
# or
flask promote-admin you@example.com
```
