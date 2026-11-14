# Filming Planner — phase 1 MVP

Route: `/filming-planner`

The first phase adds a responsive, publicly accessible, client-side filmmaking
workspace to the existing Vlog Travel Finder Flask application.

## Available now
- Starting location and date.
- Flexible time presets (after lunch, morning, afternoon, all day, exact).
- Leave time, hard return time and adjustable contingency buffer.
- Walking preference and weather/other constraint notes.
- Map search links for filming categories around the entered location.
- Manually selected, reorderable and removable filming stops.
- A Google Maps directions handoff for the selected stops and return.
- Video title, opening hook, production shot checklist and field notes.
- Printer-friendly sheet with browser **Print / Save PDF**.
- Optional save/reload in browser localStorage on the same device.

## Important limitations
This phase does **not** automatically verify live availability, driving times,
opening hours, events, weather, or accessibility. Category buttons open map
searches; they are not AI-ranked place recommendations. The map handoff uses
Google Maps directions; it does not compute ETAs or optimize stop order.

The print feature saves PDF through the browser's print-to-PDF functionality;
the backend does not yet stream a directly downloaded PDF attachment. The
saved plan is local to the device/browser, not associated with a user account.

## Suggested next increments
1. User-owned persistent filming plans, reusable shot templates and a trip link.
2. Place candidate search using geocoding/places provider, with provenance,
   hours and access status; keep unknowns explicit.
3. Route matrices and duration-aware itinerary optimization, with hard return
   constraint and configurable weather/walking rules.
4. Weather/daylight forecasts, event times, cold/wind risk and filming constraints.
5. Server-side PDF download, map QR codes, printable field checklist.
6. Link filming plans to shot assets and published Mad Mallards Adventures videos.
7. Support Cloudflare-friendly deployment and zero-cost/low-cost provider options.

No third-party geolocation or AI keys are needed to operate this MVP.
