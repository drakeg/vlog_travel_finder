# Unified Product Roadmap — Vlog Travel Finder + Filming Planner

## Product direction

**One application and one codebase.** The Filming Planner is a core workflow within Vlog Travel Finder, not a separate service, repository, database, login system, or product. Creators and RV travelers should be able to discover real places, assemble practical trips, plan filming, produce production documents, and ultimately associate finished content with the destinations and journeys in the same app.

The original MVP was informed by a short filming outing from Talona Ridge RV Resort near Ellijay, Georgia: find worthwhile destinations after lunch, respect a hard before-dinner return deadline, and leave with a practical shoot sheet.

## Currently shipped

- Vlog Travel Finder: place catalog, geocoded place fields when supplied, Saved Places, private Trips, trip itinerary stops, preparation checklists and templates, user accounts, local Docker Compose development, and GitHub Actions testing.
- Filming Planner MVP, PR #278: starting point, date/windows, manual stops and reordering, creator shot checklist, title/hook/notes, Google Maps navigation, printable sheet, browser-local saving.
- Scheduling, PR #279: per-stop filming minutes, estimated drive duration per leg, arrival/finish and return estimates, time-budget warning, persisted timing inputs.
- Sprint 46 is complete; PRs #278, #279 and #280 are merged with successful Tests workflows.

**Known limits:** current timings are user-entered, not measured driving ETAs. The planner does not yet confirm weather, hours, filming access, accessibility, or nearby destination availability. Browser print is not server PDF generation; browser saves are not account-based.

## Delivery sequence and issue tracking

| Priority | Workstream | Issue | User-visible outcome | Dependencies and constraints |
| --- | --- | --- | --- | --- |
| 1 — Sprint 47 | Existing catalog destination discovery | #281 | City search surfaces real catalog places, filming angles, and one-click add-to-plan | No API key or schema change; label source and unverified hours |
| 2 | OpenStreetMap destination discovery | #282 | Real nearby places even where the local catalog is empty | Provider caching/rate limits, source attribution, graceful fallback |
| 3 | Grounded routing and duration | #283 | Round-trip ETA and hard return constraints based on a routing provider | OpenStreetMap-derived route source; preserve manual override |
| 4 | Filming conditions | #284 | Weather, daylight, opening and access warnings | Unknowns remain unknown; location and date required |
| 5 | Better planning and optimization | #285 | Natural-language time windows, editable assumptions and practical alternatives | Explicit timezone/date; never mask impossible schedules |
| 6 | Downloadable production PDF | #286 | Server-generated letter-size filming pack with checklists and route links/QR codes | Open-source Python PDF library; test generated content |
| 7 | Saved plans and existing trip integration | #287 | Account-owned cross-device plans linked to Trips, Places and checklists | Additive SQLite migration and cross-user authorization tests |
| 8 | Creator production improvements | #288 | Per-stop A-roll/B-roll, Shorts, thumbnails, equipment and published-video linkage | Shared business logic for possible Creator Desk integration |
| Deferred | Zero-cost Cloudflare/other deployment | #289 | Deploy production site without a recurring hosting bill when feasible | No costs or provider changes without authorization |

Increment order may change when a blocking prerequisite is identified. Each increment gets an issue, a focused PR, tests, documentation and verified CI. No duplicate or competing PRs for the same functionality.

## Unified data and integration rules

- **Places:** Reuse existing `Place`, `Category`, coordinates, and place URLs. External candidates require provenance, stable provider IDs and duplicate detection before saving.
- **Trips and itinerary stops:** Reuse `Trip` and `TripPlace` rather than introducing a parallel itinerary system. The Filming Planner's per-stop duration and shot plan can later extend the associated trip without changing existing behavior.
- **Checklists:** Reuse trip checklist and reusable checklist template workflows; filming-specific shot completion may have distinct metadata but must not duplicate user-owned checklists.
- **Authentication:** Existing accounts and authorization boundaries apply; browser-local draft support remains available.
- **Architecture:** Flask blueprints and services, SQLAlchemy, the existing SQLite versioned migration strategy, Bootstrap 5 templates, Docker Compose, GitHub Actions on supported Python versions.
- **External services:** Prefer no-key, free or self-hostable providers where feasible. Mock network requests in tests; cache responsibly. Do not equate provider listings with verified opening hours, trail accessibility or filming permission.
- **Privacy and costs:** No undisclosed location sharing or surprise paid APIs. Let users verify final travel times and access before departure.

## Product completion criteria

A plan should make it possible to: provide a starting location and usable time window; discover real, attributable destinations; choose an achievable route with return buffer; see data freshness and uncertainty; tailor film segments, Shorts and equipment checklists; download a production-ready PDF; and resume saved plans on another device when signed in.

The application must remain useful even when external providers are unavailable, with manual planning and known destinations as fallback. Preserve all existing Vlog Travel Finder functionality throughout delivery.
