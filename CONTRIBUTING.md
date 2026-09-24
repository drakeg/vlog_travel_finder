# Contributing

This repository uses small, reviewable pull requests, automated tests, Docker Compose for local parity, and GitHub Issues to track planned work.

## Development workflow

1. Start from the latest `main`.
2. Confirm the work is represented by an accurate GitHub Issue when the change is more than a trivial fix.
3. Create a focused branch:
   - `feature/<short-name>`
   - `fix/<short-name>`
   - `docs/<short-name>`
   - `ci/<short-name>`
   - `refactor/<short-name>`
4. Implement the smallest complete change that satisfies the issue.
5. Add or update automated tests for changed behavior.
6. Update documentation when behavior, setup, configuration, schema, or operator workflow changes.
7. Run the local checks described in [docs/TESTING.md](docs/TESTING.md).
8. Open a pull request using the repository template.
9. Do not merge while required CI is failing, the branch has unresolved conflicts, or required documentation/tests are incomplete.
10. After merge, verify the linked issue closed correctly and that its completion checklist reflects the final CI result.

## Pull request scope

Prefer one cohesive concern per pull request. Avoid mixing unrelated feature work, cleanup, dependency changes, and refactors unless they are inseparable.

A pull request should explain:

- what changed;
- why it changed;
- how it was tested;
- any database or migration impact;
- any security or authorization impact;
- any deployment/configuration impact;
- which issue it closes or advances.

## Issues

Feature and bug work should use the repository issue templates. Acceptance criteria should describe observable behavior rather than implementation details where possible.

Keep issue checklists current. A closed issue should not contain stale unchecked completion items such as CI or documentation checks that actually passed.

## Sprints

Sprint planning and completion rules are documented in [docs/SPRINTS.md](docs/SPRINTS.md). Sprint work should remain traceable from sprint scope to issue to pull request to merged code.

## Coding standards

Repository coding expectations are documented in [docs/CODING_STANDARDS.md](docs/CODING_STANDARDS.md).

## Testing

Testing requirements and local/CI commands are documented in [docs/TESTING.md](docs/TESTING.md).

## Database changes

SQLite schema changes must use the existing versioned `PRAGMA user_version` migration mechanism. Never require users to delete or recreate their database for a normal upgrade.

Every schema change must include a migration test and must preserve existing data unless an explicitly approved destructive migration is documented.

## Security

Changes involving authentication, authorization, redirects, uploads, user-owned data, or admin functions require explicit tests for the relevant trust boundary. User-owned records must be scoped by the authenticated user, not merely by object ID.

Do not commit credentials, secrets, production database files, or local `.env` files.
