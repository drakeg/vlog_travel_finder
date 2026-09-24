# Testing and CI

## Required local checks

The canonical test command is:

```bash
python -m pytest -q
```

Docker Compose provides the environment-parity path:

```bash
docker compose run --rm test
```

Validate the Compose file when it changes:

```bash
docker compose config
```

## CI matrix

GitHub Actions is expected to run:

- pytest on Python 3.12;
- pytest on Python 3.13;
- Docker Compose configuration validation;
- pytest through the Compose test service.

A pull request is not ready to merge while a required job is failing.

## Test expectations by change type

### Feature

Cover:

- the primary success path;
- important validation failures;
- authentication/authorization when applicable;
- persistence behavior;
- duplicate/idempotent behavior where applicable;
- user isolation for private records.

### Bug fix

Add a regression test that fails before the fix and passes after it whenever practical.

### Database migration

Verify the migrated schema exists and existing startup/upgrade behavior remains valid.

### Admin workflow

Test that unauthenticated/non-admin access is denied or redirected and that the intended admin operation succeeds.

### Import/export

Test headers/format, representative data, escaping, validation, and malformed input behavior.

### Security-sensitive change

Test the trust boundary directly. Examples include cross-user object access, unsafe redirects, file uploads, and privileged routes.

## Test quality

- Tests should assert observable behavior, not incidental implementation details.
- Build structured data with the same libraries used by production when practical; for example, use `csv.writer` rather than hand-counted commas.
- Avoid network dependencies in unit/integration tests; mock external fetches.
- Keep fixtures isolated and deterministic.
- A test should explain one behavior clearly through its name and assertions.

## CI failures

When CI fails:

1. inspect the failing job and exact log;
2. reproduce or isolate the failure;
3. fix the cause, not the symptom;
4. push the fix to the same PR when the PR is still the correct unit of work;
5. wait for/verify the replacement workflow result before considering the issue complete.

Do not begin unrelated feature work on top of a known failing pipeline.

## Documentation and tracker verification

After merge:

- verify the final workflow passed;
- update any stale CI checkbox in the linked issue;
- confirm the issue closed with the intended reason;
- keep sprint tracking accurate.
