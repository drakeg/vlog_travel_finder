Always create tests for any new functionality.

# Flask Code

## README badge standard

Follow [Mad Mallard repository standards](https://github.com/drakeg/madmallard-repository-standards) when that repository publishes detailed rules; the current repository-specific requirements are:

- Maintain a compact badge block immediately below the root README title, above its description, in technology, CI, and community rows.
- Inspect `requirements.txt`, `Dockerfile`, `compose.yaml`, configuration and `.github/workflows` before adding or updating badges. Include versions only when explicitly verified.
- CI badges must use the real GitHub Actions workflow URL and dynamic status. Never hardcode successful tests, lint, security or deployment.
- Include release and license badges only if a release and actual license exist. Never imply a release, license, hosting provider or database not supported by the repository.
- Use clickable Shields.io links where useful. Preserve all other README documentation and remove stale or duplicate badges.
- Run `python scripts/validate_readme_badges.py` when changing README, workflows, dependencies, Docker or project metadata. CI runs this check automatically. Update badge links/versions in the same PR as related changes.
