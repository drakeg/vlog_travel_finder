
"""Thin entrypoint.

The app implementation lives in the `vlog_site` package (MVC-ish structure).
"""

from vlog_site import create_app


app = create_app()
