# Sprint Process

## Purpose

Sprints provide a lightweight planning and delivery boundary. The goal is traceability and predictable completion, not ceremony.

Each sprint should answer:

- What user or operator outcome are we delivering?
- Which issues are in scope?
- What must be true before work starts?
- What tests and documentation are required?
- What marks the sprint complete?

## Sprint naming

Use sequential names: `Sprint 1`, `Sprint 2`, and so on.

For larger sprints, individual work items may optionally use `Sxx-Dyy` identifiers, for example `S03-D02`, when that improves tracking.

Do not renumber historical work merely to fit the current process.

## Retrospective baseline: Sprint 0

The work merged immediately before formal sprint documentation is treated as **Sprint 0 — Baseline hardening and travel planning**.

Representative completed work includes:

- GitHub Actions pytest coverage on Python 3.12 and 3.13;
- Google Maps links for places;
- vlog-status filtering and result sorting;
- Docker Compose local development and testing;
- CSV export and import for place data;
- member Saved Places;
- private named trip lists.

Sprint 0 establishes the technical and process baseline for subsequent numbered sprints.

## Sprint planning

A sprint should have a short planning issue or clearly identified parent issue containing:

- sprint goal;
- in-scope issues;
- explicit out-of-scope items where ambiguity exists;
- dependencies and prerequisites;
- schema/migration expectations;
- testing expectations;
- documentation expectations;
- security/authorization considerations;
- deployment or external-service considerations.

Keep the sprint small enough that all accepted work can be merged, tested, documented, and closed as a coherent unit.

## Readiness gate

Work is ready to enter a sprint when:

- the problem and expected outcome are clear;
- acceptance criteria are testable;
- known dependencies are identified;
- data migration needs are understood;
- external services, credentials, cost, or infrastructure requirements are called out;
- security-sensitive behavior has an explicit test plan;
- there is no known blocker that makes implementation speculative.

## During the sprint

- Keep the issue tracker accurate as scope changes.
- Prefer focused PRs that close one issue or one coherent slice of an issue.
- Update tests and documentation in the same PR as behavior changes.
- Fix CI regressions before beginning unrelated follow-on work.
- Avoid silently expanding sprint scope. New ideas should become issues for a later sprint unless required to complete or safely operate current work.
- Keep migrations forward-safe and non-destructive unless explicitly approved.

## Definition of done for a work item

A work item is done only when:

- acceptance criteria are satisfied;
- code is merged to `main`;
- required CI is green;
- tests cover the changed behavior and important failure/authorization paths;
- documentation is updated;
- database migrations are included and tested when applicable;
- linked issues are closed or updated accurately;
- no unresolved merge conflicts or known release-blocking regressions remain.

## Definition of done for a sprint

A sprint is complete when every committed item is either:

1. merged and done under the criteria above; or
2. explicitly moved out of the sprint with the tracker updated.

The sprint closeout should record:

- what shipped;
- deferred items;
- notable migration/configuration changes;
- known follow-up work.

Do not mark a sprint complete solely because code was written.

## Maintenance work

Small dependency updates, documentation corrections, and urgent production fixes do not need to wait for a sprint boundary. They still follow testing, review, and issue/PR hygiene rules.

## Future sprint record

Add concise sprint closeouts below this heading as formal sprints complete.

### Sprint 1 — Trip planning usability

Status: Complete

Planning issue: #110

Shipped:

- trip-level planning notes;
- persistent ordered trip stops;
- deterministic backfill of existing stop order;
- append-to-end behavior for new stops;
- ownership-scoped up/down reordering;
- numbered stop presentation;
- regression coverage for notes, ordering, boundaries, ownership, and migration.

Deferred:

- route optimization;
- maps API integration;
- distance/time calculations;
- shared or collaborative trips;
- paid external services.

### Sprint 2 — Itinerary details

Status: Complete

Planning issue: #113

Shipped:

- optional trip start/end dates;
- malformed and reversed date-range validation;
- private per-stop planning notes;
- ownership-scoped stop-note updates;
- schema, validation, persistence, and authorization regression coverage.

Deferred:

- route optimization;
- travel-time calculations;
- calendar synchronization;
- shared or collaborative trips;
- paid external services.

### Sprint 3 — Stop scheduling

Status: Complete

Planning issue: #116

Shipped:

- optional planned date/time on trip stops;
- server-side date/time validation;
- enforcement of configured trip date ranges;
- ownership-scoped scheduling edits;
- scheduled date/time display on ordered stops;
- migration and regression coverage for scheduling behavior.

Deferred:

- automatic route optimization;
- travel-time calculations;
- calendar synchronization;
- shared or collaborative trips;
- paid external services.

### Sprint 4 — Day-by-day itinerary view

Status: Complete

Planning issue: #119

Shipped:

- chronological day grouping for scheduled stops;
- manual stop order preserved within each day;
- a separate unscheduled section;
- overall stop sequence numbering retained;
- existing stop controls preserved;
- improved empty itinerary behavior;
- regression coverage for grouping, ordering, controls, unscheduled stops, and empty states.

Deferred:

- automatic route optimization;
- travel-time calculations;
- calendar synchronization;
- shared or collaborative trips;
- paid external services.

### Sprint 5 — Printable itinerary export

Status: Complete

Planning issue: #122

Shipped:

- ownership-scoped print-friendly itinerary view;
- downloadable plain-text itinerary;
- shared grouping/order logic across editable and export views;
- trip dates/notes and stop schedule/notes/location details in exports;
- addresses and Google Maps URLs when available;
- editing controls excluded from the print view;
- auth, ownership, representative-content, and empty-trip regression coverage.

Deferred:

- PDF generation;
- direct calendar synchronization;
- route optimization;
- shared or collaborative trips;
- paid external services.

### Sprint 6 — Calendar export

Status: Complete

Planning issue: #125

Shipped:

- ownership-scoped iCalendar (.ics) export;
- one VEVENT per scheduled stop;
- all-day events for date-only stops;
- floating local-time events for timed stops;
- stop notes, location text, and Google Maps URLs when available;
- safe iCalendar text escaping;
- valid calendars when no stops are scheduled;
- auth, ownership, formatting, escaping, and no-event regression coverage.

Deferred:

- direct Google Calendar or Outlook synchronization;
- reminders/notifications;
- route optimization;
- shared or collaborative trips;
- paid external services.

### Sprint 7 — Trip duplication

Status: Complete

Planning issue: #128

Shipped:

- ownership-scoped trip duplication;
- copied trip metadata and all stop memberships;
- preserved stop order, notes, schedules, and dates;
- clear "(Copy)" default naming;
- independent source and duplicate records;
- populated-trip, empty-trip, independence, and cross-user regression coverage.

Deferred:

- shared templates across users;
- public trip templates;
- automatic date shifting;
- route optimization;
- paid external services.

### Sprint 8 — Saved places to trips

Status: Complete

Planning issue: #131

Shipped:

- owned-trip selection on Saved Places;
- single-place add-to-trip workflow;
- bulk saved-place add-to-trip workflow;
- append-after-existing-stop ordering;
- duplicate membership skipping;
- ownership enforcement;
- regression coverage for single add, bulk add, ordering, duplicates, ownership, and empty states.

Deferred:

- drag-and-drop trip building;
- shared or collaborative trips;
- automatic route optimization;
- paid external services.

### Sprint 9 — Anonymous preview authorization hardening

Status: Complete

Planning issue: #135

Shipped:

- anonymous-preview sessions treated as unauthenticated by login_required;
- private Saved Places and Trips GET routes blocked during preview;
- member-only mutations and exports blocked during preview;
- admin-only Stop Preview preserved;
- normal authenticated access preserved;
- representative GET/POST and preview-exit regression coverage.

Deferred:

- CSRF protection;
- session backend replacement;
- role-system redesign;
- shared or collaborative trips.

### Sprint 10 — CSRF protection

Status: In progress

Planning issue: #140

Current work:

- #141 — add a cryptographically random per-session CSRF token;
- validate unsafe browser form requests with constant-time comparison;
- add CSRF hidden fields to public, auth, and admin POST forms;
- return HTTP 400 for missing or invalid tokens;
- keep safe methods unaffected;
- isolate CSRF-specific test coverage while keeping the broader suite maintainable;
- document production behavior and test-only disablement.

Out of scope for Sprint 10:

- API-key authentication;
- OAuth;
- session backend replacement;
- same-origin API redesign.
