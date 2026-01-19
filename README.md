
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
