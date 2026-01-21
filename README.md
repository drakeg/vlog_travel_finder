
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
  - Manage blog posts
  - View contact messages
- **Public**
  - Home, places search, blog, contact, about

## Local setup

### 1) Create a virtualenv and install deps

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Tests

```bash
pytest
```

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

## Configuration

- `SECRET_KEY`
  - Set this in production (do not use `dev`).
- `DATABASE_URL`
  - SQLAlchemy database URL. Defaults to SQLite.

Example:

```bash
export SECRET_KEY='your-long-random-string'
export DATABASE_URL='sqlite:////absolute/path/to/vlog_site.sqlite'

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
