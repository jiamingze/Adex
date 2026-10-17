# On-demand location context

Client asks for consent only for location-relevant requests. Device positioning is
foreground/one-shot, approximate (rounded to 0.01 degrees); no background tracking.
Manual city/area is a supported alternative; denying location never blocks chat.
The consent explains transmission of approximate location to Adex and relevant
query providers. Explicit locations in user text take precedence over device context.

MessageInput gains optional `client_location`: source=device|manual, label<=120,
latitude/longitude optional paired finite bounds, observed_at RFC3339. App validates
and normalizes input before a Turn is written. Migration app/023 adds a nullable
JSON location column and a stable digest for retries. No new service or scheduler.
Location is scoped to this turn/owner, not memory; background jobs never inherit it.
Coordinate metadata is cleared on terminal turns/cancellation/deletion; retain only
the digest for idempotency. Agent L1 must not cache location-bearing contexts.

Client caches device fixes only in memory for at most 5 minutes; it never persists
coordinates in localStorage. User may disable positioning or change manual city in
Settings. Failed/expired positioning yields no invented city or location. Agent
prompts and search query grounding must distinguish unavailable, manual and device
locations. Local weather uses provider data, timestamps and the actual forecast
range; hotel search must not invent star ratings, distance, prices or availability.

Verification uses synthetic locations and isolated DBs. Real permission grant and
physical positioning require the user; never claim simulated fixes are real.


Coordinates are consumed by Tools weather lookup only; the model prompt and durable
interactive plan receive city/area, source and observation time, not coordinate
numbers. A reverse-geocoding failure yields no guessed city: weather may still use
the approximate fix, but nearby recommendations request a city/area. Native reverse
geocoding uses Apple's system geocoder with the rounded fix, not a public community
reverse API. Web users may supply a manual city when an area label is unavailable.

Tools adds `POST /internal/weather/forecast`, Agent-only `weather:read`, paired
bounded coordinates, seven-day Open-Meteo daily dates in the provider timezone,
units, source URL and fetched_at. Provider failure returns 503; Agent can use real
search evidence or state it cannot verify, never invent weather.


## Validation and deployment

- `mvn -q -pl services/adex-app -am test package`: passed including validation of
  malformed, out-of-range/future/unconsented inputs and coarse-coordinate normalization.
- `uv run --project services/adex-agent pytest services/adex-agent/tests -q`: 81 passed.
- `uv run --project services/adex-tools pytest services/adex-tools/tests -q`: 103 passed.
- `uv run python scripts/test_stack.py tests/integration/test_location_context.py tests/integration/test_chat_productivity.py -q`: 6 passed (69.53s), including
  owner isolation, coordinate erasure, prompt minimization and idempotency binding.
- `make test-client`: 22 passed. `pnpm --dir apps/web build`, `make check-style`,
  contract and secret checks passed. iOS signed build/install/launch succeeded.
- A public sample-coordinate Open-Meteo probe returned seven real forecast dates
  for 2026-10-18 through 2026-10-24. The sample was not a user location. Actual
  iPhone permission grant/fix must be verified by the user; no location is guessed.

No location history table, background tracking, new business service or second
scheduler. This feature provides query context; it does not claim confirmed hotel
star ratings, live inventory/prices, navigation distance, or booking capability.


## In-chat consent UX · 2026-10-18

For the first location-relevant message, render the question and an inline assistant
card with “使用当前位置” / “暂不授权”. No application dialog or city text field is
shown. Clicking the primary action records consent and requests an approximate
foreground fix; only the mandatory OS/browser permission sheet may appear. Legacy manual-location data remains readable at the API boundary, but the UI no
longer asks users to type a city; an old manual preference requests fresh device
consent on the next relevant chat. Navigating away while consent is pending cancels that unsent
request and releases the composer rather than authorizing a different conversation.
Denial/unavailable location must never become a guessed location. Real iPhone
permission behavior still requires a device check.
