# Optional geocoding provider foundation

The Filming Planner now has a testable, **inactive** adapter at `vlog_site/services/filming_geocoding.py` for a Nominatim-compatible endpoint. It converts a typed city, campground or address query into a bounded list of actual OpenStreetMap results, including coordinates and source links. It is not wired into any Flask route or UI; the current catalog picker and manual coordinates remain unchanged.

Before activation, an operator must configure a permitted provider and enforce **deployment-wide** caching and rate limits at a shared proxy or self-hosted service, prevent unsafe redirects, verify outbound host allowlists and obtain the user's explicit consent before forwarding a typed location. Public Nominatim's usage policy includes an absolute maximum of one request per second per application, caching and valid identification, and prohibits autocomplete and systematic queries. Do not treat a single-process throttle as sufficient for multiworker production.

Provider documentation: https://operations.osmfoundation.org/policies/nominatim/

Follow-up to issue #282: implement a safe shared provider gateway, opt-in UI flow, user-selectable geocoding candidates and integration with existing nearby discovery. No API key, deployment, or paid service is introduced by this increment.
