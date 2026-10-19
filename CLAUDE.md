# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Rota App: a FastAPI backend that builds group activity/day-trip plans. Given a
location, duration, budget, and group type, it searches nearby places (Google
Places API), fetches current weather (Open-Meteo), and asks an LLM (Groq) to compose
2-3 alternative themed day plans using only the fetched places.

Code comments, docstrings, and log messages are written in Turkish; keep new
ones consistent with that convention unless told otherwise.

The repo also has a `frontend/` app (Vite + React + TypeScript + Tailwind +
Leaflet) that consumes this API — see "Frontend" below. Auth is Supabase,
and the backend only optionally knows about it: no endpoint *requires* a
user identity, but `/plan` will verify a Supabase JWT if one is sent, purely
to tell a logged-in user apart from a guest for rate-limiting purposes (see
"Security" below).

## Commands

### Backend

Install (editable, with dev deps):
```
pip install -e ".[dev]"
```

Run the dev server:
```
fastapi dev app/main.py
```

Lint:
```
ruff check .
```

Run all tests:
```
pytest
```

Run a single test file / test:
```
pytest tests/test_places_service.py
pytest tests/test_places_service.py::test_basarili_arama
```

Tests are async (`pytest-asyncio`, `asyncio_mode = "auto"` in [pyproject.toml](pyproject.toml)),
so `async def test_...()` functions run without extra decorators. HTTP calls are
mocked with `respx` rather than hitting real APIs — follow that pattern for new
service tests instead of mocking at the `httpx.AsyncClient` level.

### Frontend

All run from `frontend/`:
```
npm install
npm run dev      # Vite dev server at :5173, proxies /api/* to the backend at :8000
npm run build    # tsc -b && vite build
npm run lint      # oxlint
npx tsc -b --noEmit   # type-check without emitting
```
There is no frontend test suite. `frontend/.env` needs `VITE_SUPABASE_URL` /
`VITE_SUPABASE_ANON_KEY` (copy `frontend/.env.example`) for the Supabase Auth
feature to work; the rest of the app functions without it. The dev proxy
(`frontend/vite.config.ts`) means the backend must also be running
(`fastapi dev app/main.py`) for `/api/*` calls to resolve.

## Configuration

Settings are a pydantic-settings `Settings` object in [app/core/config.py](app/core/config.py),
loaded from a `.env` file and cached via `@lru_cache` (`get_settings()`). The
API keys have no default (`places_api_key`, `geocoding_api_key`,
`routes_api_key`, `groq_api_key`) — the app fails to start without them, by
design. Copy `.env.example` to `.env` and fill in:
- `PLACES_API_KEY` — Google Places (New) API key
- `GEOCODING_API_KEY` — Google Geocoding API key
- `ROUTES_API_KEY` — Google Routes API key
- `GROQ_API_KEY` — Groq API key (`GROQ_MODEL` optionally overrides the model)

Security-related settings are all optional with safe defaults (see
"Security" below): `rate_limit_enabled` (default `true`, forced `false` in
tests), `guest_daily_plan_limit` (default `3`), `supabase_jwt_secret`
(default `None` — JWT verification is skipped entirely until set),
`cors_origins` (default `http://localhost:5173`).

## Architecture

Layering: `api/routes` → `services` → external APIs, with `schemas` (Pydantic
models) as the shared vocabulary between them. Routes only translate service
exceptions into `HTTPException`s; all real logic lives in services.

- [app/api/router.py](app/api/router.py) aggregates route modules
  (`health`, `weather`, `places`, `geocoding`, `plan`, `route`) into one
  `api_router`, included by [app/main.py](app/main.py)'s `create_app()`.
- [app/services/orchestrator.py](app/services/orchestrator.py) is the
  entry point for the core feature (`build_day_plan`). Flow:
  1. Resolve themes: explicit `categories`, or LLM-resolved from
     `free_text` (`planner.resolve_themes`), or `DEFAULT_THEMES`.
  2. Fan out one `places.search_nearby` call per theme concurrently
     (`asyncio.gather`), de-dupe by `place_id`, cap the pool at
     `MAX_POOL_SIZE`. A theme search failing (returned as an exception by
     `gather(..., return_exceptions=True)`) is logged and skipped, not fatal.
  3. Fetch weather concurrently with the places pool; weather failure
     degrades to `"bilinmiyor"` rather than failing the request.
  4. Hand the place pool + weather summary to `planner.create_plan`.
- [app/core/themes.py](app/core/themes.py) maps theme keywords (Turkish,
  e.g. `"tarihi"`, `"kafe"`) to Google Places `included_types`. Adding a
  theme means adding an entry to `THEME_TYPES` here — the planner's LLM
  prompt for free-text theme resolution restricts its choices to this
  dict's keys.
- [app/services/places.py](app/services/places.py) wraps the Google Places
  "searchNearby" v1 API. `_FIELD_MASK` restricts the response to only the
  fields the `Place` schema needs — extend both together when adding fields.
  All HTTP/parsing failures are normalized to `PlacesServiceError`.
- [app/services/planner.py](app/services/planner.py) calls Groq
  (`groq`, `AsyncGroq`) in `json_object` mode. Groq does not enforce a schema,
  so the Pydantic JSON schema (`DayPlan`/`_ThemeSelection`) is embedded in the
  prompt (`_schema_instruction`, system-filled fields are stripped by
  `_llm_schema`) and the reply is validated with Pydantic. After parsing,
  `_validate_and_enrich_stops` strips any stop whose `place_id` isn't in the
  input place pool (the model is instructed not to invent places, but
  responses are still validated defensively) and fills each stop's
  name/latitude/longitude from the pool.
  `PlannerServiceError` covers both call failures and empty/invalid results.
- [app/services/routes.py](app/services/routes.py) wraps the Google Routes
  API (`computeRoutes`) for distance/duration/polyline and turn-by-turn
  steps. [app/api/routes/route.py](app/api/routes/route.py) exposes it two
  ways: `POST /route/approach` (user location → first stop, used once by
  the frontend's live navigation mode) and `POST /route/legs` (recomputes
  legs for an arbitrary ordered stop list — used whenever the frontend
  deletes/reorders/swaps a stop, so the route line stays in sync without
  regenerating the whole plan).
- `DayPlan.place_pool` (set in `orchestrator.py` right after `create_plan`
  returns, from the same `pool` variable already fetched for the LLM) ships
  the *entire* fetched place pool, not just the places the LLM used. This
  is intentional: it lets the frontend offer stop-swap/add features by
  reusing already-paid-for data, with no new Places or Groq call.
- `PlanRequest.anchor_place` (set when the frontend's "frequent places"
  home-screen tap seeds a plan around one specific place) is *not* trusted
  to the LLM alone: `orchestrator.py::_ensure_anchor_stop` runs right after
  `create_plan` and appends the anchor as a stop to every alternative that
  doesn't already contain it. The anchor's own coordinates are used as the
  plan's `latitude`/`longitude` client-side (see `prefs.ts::toRequest`), so
  geocoding is skipped entirely when an anchor is set.
- `PlanRequest.start_time` ("HH:MM", optional) is appended to the LLM
  prompt as a plain instruction line in `planner.py::_build_prompt`
  ("ilk durağın varış saati bu saatte ya da hemen sonrasında olsun") —
  there's no separate enforcement step like the anchor place has; it's
  trusted to the LLM. Omitted entirely from the prompt when not set.
- Each service module defines its own `*ServiceError` exception; routes
  catch these and convert to `502` responses. Follow this pattern for new
  external integrations.

## Security

Every public-facing route is rate-limited and input-bounded, since `/plan`
fans out to several paid Google calls plus a Groq call per request:

- [app/core/rate_limit.py](app/core/rate_limit.py) exports a single shared
  `slowapi` `Limiter` (IP-keyed, `60/minute` default). Each route adds its
  own `@limiter.limit(...)` decorator on top of that default — see
  [app/api/routes/plan.py](app/api/routes/plan.py) (`10/minute`, the
  priciest route) for the pattern. A route decorated this way needs a
  `request: Request` parameter; `/health` is `@limiter.exempt`. Tests set
  `RATE_LIMIT_ENABLED=false` (`tests/conftest.py`) so the shared `Limiter`
  (constructed once at import time) doesn't accumulate a rate-limit count
  across the whole test run and start rejecting later tests.
- [app/core/auth.py](app/core/auth.py)'s `get_optional_user_id` is a
  FastAPI dependency that verifies a Supabase JWT (`aud=authenticated`) from
  the `Authorization: Bearer` header if `supabase_jwt_secret` is configured,
  returning the user id or `None`. Supabase projects expose either a legacy
  shared secret (HS256) or, newer ones, an asymmetric "Signing Keys" public
  key (ES256/RS256, PEM-formatted) — the code picks the algorithm by
  sniffing whether the configured value starts with `-----BEGIN`, so either
  one can be dropped into the same setting. It never raises — a missing or
  invalid token just means "treat as guest," consistent with login being
  optional everywhere else. This needs the `cryptography` package (pulled
  in via `pyjwt[crypto]`) for the ES256/RS256 path.
- [app/core/guest_limit.py](app/core/guest_limit.py)'s
  `enforce_guest_plan_limit` is the server-side backstop for `/plan`'s free
  usage cap (the frontend's `guestLimit.ts` localStorage counter is
  client-side only and trivially bypassed). It's an in-memory per-IP daily
  counter, skipped entirely when `get_optional_user_id` returns a user id.
  On rejection it raises `429` with an `X-Guest-Limit-Reached` header so the
  frontend (`api.ts`'s `ApiError.guestLimit`) can tell this apart from a
  generic `slowapi` rate-limit `429` and route the user to the right screen
  instead of a generic error. `enforce_guest_legs_limit` is the same pattern
  for `POST /route/legs` with its own counter and setting
  (`guest_daily_legs_limit`, default 20, higher than the plan limit since
  stop-editing happens far more often per session than full plan
  generation) — needed because a single `TRANSIT`-mode call to this
  endpoint can trigger up to `MAX_LEG_STOPS - 1` separate Routes API calls
  (`app/schemas/plan.py::MAX_LEG_STOPS`, 12 — deliberately lowered from 25
  for this reason). For this guest/logged-in distinction to work correctly
  here, the frontend's `fetchLegs` (`api.ts`) must be passed an
  `accessToken`, same as `createPlan` — `DetailScreen.tsx` passes
  `session?.access_token` into every `fetchLegs` call.
- [app/main.py](app/main.py)'s `create_app()` adds `CORSMiddleware`
  (origins from `cors_origins`) and only enables `/docs`, `/redoc`,
  `/openapi.json` when `settings.debug` is true — they're closed by default.
- [supabase/schema.sql](supabase/schema.sql) is the source of truth for
  all four Supabase tables (`profiles`, `saved_plans`, `favorite_places`,
  `visited_places`), their RLS policies, the `handle_new_user` trigger, and
  the `get_shared_plan` function — apply it in the Supabase SQL Editor
  rather than clicking it together in the dashboard, and keep it in sync
  with whatever the dashboard ends up with. `favorite_places`/
  `visited_places` are private (select scoped to `auth.uid() = user_id`) —
  there's no sharing concept for a single favorited/visited place.
  `saved_plans`'s select is *also* owner-only now (fixed 2026-10-19): it
  used to be `using (true)` on the theory that the row id (an unguessable
  UUID) was itself the access control, but that only holds if a row can
  only be looked up one at a time — anyone with the anon key could `select
  *` the whole table and enumerate every user's plans. The share-link flow
  (`?shared=<id>`) now goes through `get_shared_plan(plan_id uuid)`, a
  `SECURITY DEFINER` function (fixed `search_path`) that intentionally
  bypasses RLS but only for a single row by id — `savedPlans.ts::fetchSharedPlan`
  calls it via `supabase.rpc(...)` instead of a raw `.from('saved_plans').select()`.
- [frontend/vite.config.ts](frontend/vite.config.ts)'s `cspPlugin` injects a
  `Content-Security-Policy` meta tag into `index.html`, but only for
  `npm run build` (`apply: 'build'`), not `npm run dev`: the dev server's
  Fast Refresh preamble needs an inline `<script>` that a strict
  `script-src` would block. `script-src` itself has no `'unsafe-inline'`
  (defense-in-depth against the same inline-event-handler vector the
  Leaflet pin XSS fix above closed); `style-src` does, for
  Tailwind/React's inline styles. `img-src` allows
  `https://*.tile.openstreetmap.org` (Leaflet tiles), `connect-src` allows
  `https://*.supabase.co`. Verified with a Playwright smoke test against a
  real `npm run build` output (map + a live Supabase fetch, zero CSP
  console violations) — re-verify the same way if you touch this plugin or
  add a new external resource.

## Adding a new endpoint/service

1. Define request/response models in `app/schemas/`.
2. Implement the external call in `app/services/`, raising a dedicated
   `*ServiceError` on failure (see [app/services/weather.py](app/services/weather.py)
   for the smallest example).
3. Add a route in `app/api/routes/`, catching the service error and
   mapping it to an `HTTPException`.
4. Register the router in [app/api/router.py](app/api/router.py).
5. Test the service with `respx`-mocked HTTP responses, not the route.

## Frontend

`frontend/src/App.tsx` is a hand-rolled state machine: a single `view`
union (`{ name: 'location' | 'prefs' | 'loading' | 'limit' | 'clarify' |
'error' | 'results' | 'detail' | 'navigate' | 'account' }`) drives which
screen under `frontend/src/screens/` renders inside `components/Shell.tsx`;
there is no router library. `plan: DayPlan | null` is the one source of
truth for the current plan and is lifted to `App.tsx`; screens receive it
and report changes back up via callbacks (e.g. `DetailScreen`'s
`onAlternativesChange`) rather than owning their own copy.

- **Auth is Supabase** (`supabase.ts`, `auth.ts`), and login is optional —
  a guest can use the app without an account. The frontend's own
  `guestLimit.ts` (a `localStorage` counter) is just UX: it shows the
  "limit reached" screen before even making a request. The backend enforces
  the real cap server-side (see "Security" above) and only ever learns
  the user's identity when `App.tsx` passes
  `session.access_token` into `createPlan()`, which attaches it as a
  Bearer token — this happens for `/plan` only, not for every request.
- `savedPlans.ts` wraps `supabase.from('saved_plans')` for the
  save/favorite/share-by-link feature. The privacy model is a hard-to-guess
  UUID as the row id, not an ACL — the table is readable by anyone with the
  link, deletable only by the owner. `AccountScreen.tsx` and
  `SharedPlanScreen.tsx` are the two screens that touch this table.
- `favoritePlaces.ts` and `visitedPlaces.ts` mirror `savedPlans.ts`'s thin
  wrapper style (no error wrapping, just return the Supabase query builder)
  for the two single-place tables. `favoritePlaces.ts` backs the heart icon
  on each stop in `DetailScreen.tsx` and the "Favori Mekanlarım" list in
  `AccountScreen.tsx`. `visitedPlaces.ts::recordVisit` is called
  (fire-and-forget, non-critical) whenever `DetailScreen.tsx`'s "Ulaşıldı"
  toggle transitions a stop to done — it upserts a per-place visit counter,
  which `LocationScreen.tsx` reads to show "Sık Gidilen Yerlerin" on the
  home screen. Tapping one of those sets `Preferences.anchorPlace` and
  jumps straight to `prefs` (see `PlanRequest.anchor_place` above) via a
  dedicated `onPickFrequent` callback in `App.tsx` — deliberately not
  composed from the existing `onChange`+`onContinue` pair, since calling
  both synchronously would read `onContinue`'s stale `prefs` closure before
  React re-renders.
- `api.ts` holds thin `fetch('/api/...')` wrappers (one per backend
  endpoint) that throw `ApiError` on non-2xx or network failure; screens
  call these instead of using `fetch` directly. The `/api` prefix is
  rewritten by the dev proxy (`vite.config.ts`) to the backend's `http://
  localhost:8000`.
- `meta.ts` mirrors several backend constants client-side so the frontend
  doesn't need a round trip to use them: `THEME_TYPES` mirrors
  `app/core/themes.py::THEME_TYPES` (used to category-filter
  `plan.place_pool` when swapping/adding a stop, entirely client-side), and
  `mapsUrl()` builds a Google Maps deep link from a stop's `place_id`
  (no API call — used as a free stand-in for place photos/reviews, which
  would require paid Places calls).
- `screens/DetailScreen.tsx` is the largest screen: stop reorder/delete
  (calls `POST /route/legs` to keep the route line in sync), stop
  swap/add/transfer-between-alternatives (client-side only, using
  `plan.place_pool` — never calls Places or the LLM again), and the
  "Ulaşıldı" (arrived) toggle, which only dims a stop, never removes it.
  Keep new stop-editing features here consistent with that zero-extra-cost
  constraint unless told otherwise. `arrived` itself is still purely local
  `useState` (resets on stop edits/alternative switch) — only the
  false→true transition has a side effect (`visitedPlaces.ts::recordVisit`),
  so don't assume the set reflects any server state.
- `screens/NavigationScreen.tsx` + `nav.ts` + `components/NavMap.tsx`
  implement live turn-by-turn navigation using `watchPosition`, computing
  progress against the already-fetched route polyline client-side; it only
  calls the backend again (`POST /route/approach`) when the user strays far
  enough off-route to need a recompute.
