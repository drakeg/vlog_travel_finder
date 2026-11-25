"""Verify the repository's README badge block reflects real project metadata.

Dependency-free; intentionally fails on stale versions, nonexistent workflows,
unsupported license/release badges, and hardcoded passing status.
"""
from pathlib import Path
import re

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
OWNER_REPO = "drakeg/vlog_travel_finder"


def validate():
    content = README.read_text(encoding="utf-8")
    assert content.lstrip().startswith("# Vlog Travel Finder\n"), "README title missing"
    title_end = content.index("# Vlog Travel Finder") + len("# Vlog Travel Finder")
    description = content.index("Flask app to manage", title_end)
    block = content[title_end:description]
    assert "img.shields.io" in block and "badge.svg?branch=main" in block, "Badge section must be below title"
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    dockerfile = (ROOT / "Dockerfile").read_text(encoding="utf-8")
    compose = (ROOT / "compose.yaml").read_text(encoding="utf-8")
    for dependency, label in (("Flask", "Flask"), ("SQLAlchemy", "SQLAlchemy")):
        version = re.search(rf"(?im)^{re.escape(dependency)}==([^\s]+)$", requirements)
        assert version, f"{dependency} version missing from requirements"
        assert f"{label}-{version.group(1)}-" in block, f"{dependency} badge version is stale"
    python = re.search(r"(?m)^FROM python:(\d+\.\d+)-slim", dockerfile)
    assert python and f"Python-{python.group(1)}-" in block, "Python image badge is stale"
    assert "sqlite:" in compose.lower(), "SQLite badge unsupported by Compose"
    assert (ROOT / "compose.yaml").exists() and (ROOT / "Dockerfile").exists()
    workflows = re.findall(r"actions/workflows/([^/\s)]+)\/badge\.svg", block)
    assert workflows, "Missing dynamic Actions badge"
    for workflow in workflows:
        assert (ROOT / ".github" / "workflows" / workflow).is_file(), f"Missing workflow {workflow}"
    assert not re.search(r"(?i)(badge|status)[^\n]*-(passing|success|green)-", block), "Hardcoded CI success"
    assert "img.shields.io/github/issues/" + OWNER_REPO in block
    assert "img.shields.io/github/issues-pr/" + OWNER_REPO in block
    assert ("img.shields.io/github/license/" + OWNER_REPO in block) == (ROOT / "LICENSE").is_file(), "License badge must reflect tracked license"
    assert "img.shields.io/github/v/release/" not in block, "No release verified"
    print("README badge metadata validated")


if __name__ == "__main__":
    validate()
