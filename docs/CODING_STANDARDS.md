# Coding Standards

These standards are the default for Vlog Travel Finder. Deviations are acceptable when there is a concrete technical reason and the pull request explains it.

## General principles

- Favor readable, explicit code over clever abstractions.
- Keep functions and routes focused on one responsibility.
- Prefer small, reversible changes.
- Preserve backward compatibility for user data and documented workflows.
- Remove dead code when its replacement is proven and no compatibility requirement remains.
- Never hide errors that affect correctness, security, or data integrity. Catch exceptions narrowly and intentionally.

## Python

- Target the Python versions exercised by CI.
- Follow PEP 8 naming and layout conventions.
- Use type annotations for new functions where they improve clarity, especially public helpers and service boundaries.
- Use `pathlib` or clear `os.path` handling consistently within a module rather than mixing styles gratuitously.
- Prefer f-strings for interpolation.
- Avoid mutable default arguments.
- Avoid broad `except Exception` unless the operation is deliberately best-effort and failure cannot compromise correctness or security.
- Keep imports grouped as standard library, third-party, then local modules.

## Flask

- Keep request parsing, validation, and authorization explicit at route boundaries.
- Use decorators such as `login_required`, `admin_required`, and feature-access controls consistently.
- Treat every URL or identifier supplied by a client as untrusted.
- Redirect targets supplied by requests must be constrained to safe local URLs.
- Use POST for state-changing operations.
- Keep templates presentation-focused; business rules and authorization belong in Python.

## Authentication and user-owned data

- User-owned resources must always be scoped to the authenticated user in the database query or immediately validated for ownership.
- Do not rely on hidden form fields, URL obscurity, or client-side controls for authorization.
- Add regression tests proving that one user cannot read or modify another user's private data.
- Admin-only operations require server-side admin checks.

## SQLAlchemy and data access

- Use SQLAlchemy expressions instead of interpolating user input into SQL.
- Prefer clear `select(...)` queries and explicit ordering.
- Avoid N+1 query patterns on paths that can return many records.
- Enforce uniqueness and referential integrity at the database level when practical, not only in application logic.
- Keep transaction boundaries obvious. Commit only after a complete logical mutation is ready.

## SQLite migrations

- Schema evolution uses the repository's versioned `PRAGMA user_version` strategy.
- Increment `latest_version` exactly once per schema version.
- Each migration must be idempotent enough to survive normal application startup semantics.
- Never require deleting the existing database as an upgrade procedure.
- Add a migration regression test whenever tables, columns, indexes, or constraints change.
- Preserve user data unless a destructive migration is explicitly approved and documented.

## Templates and UI

- Use Bootstrap conventions already present in the project.
- Keep forms accessible with labels or appropriate accessible names.
- State-changing forms use POST.
- External links opened in a new tab use an appropriate `rel` value such as `noreferrer`.
- Responsive layouts must remain usable on narrow screens.
- Avoid duplicating complex business conditions across templates; move them into helpers or view-model data when they become difficult to understand.

## CSV and file handling

- Use the standard `csv` module for CSV generation and parsing rather than manual comma construction.
- Validate required columns before processing imports.
- Validate numeric and typed input before persistence.
- Treat uploads as untrusted: validate type/extension, normalize names where applicable, and never trust a client-provided path.
- Import flows should report skipped/invalid rows clearly rather than silently discarding them.

## Security

- Never commit secrets or credentials.
- Production must use a non-default `SECRET_KEY`.
- Validate redirect destinations.
- Test authorization boundaries.
- Prefer allowlists over denylists for uploads and enumerated options.
- Do not expose internal exception details to public users.
- Security scanners complement, but do not replace, application-level tests.

## Documentation

Update documentation in the same PR when changing:

- setup or local-development commands;
- Docker/Compose behavior;
- environment variables;
- database schema/upgrade steps;
- user-visible features;
- admin/operator workflows;
- public API or URL behavior that users rely on.

## Tests

Every bug fix should add a regression test when practical. Every feature should cover its primary success path and material failure/authorization paths.

See [TESTING.md](TESTING.md) for the full test policy.
