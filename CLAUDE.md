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
Leaflet) that consumes this API — see "Frontend" below. Accounts live in the
backend's own PostgreSQL database (SQLAlchemy + Alembic; Supabase was removed).
Login is optional: the planning endpoints (`/plan`, `/route/*`, ...) never
*require* a user, but `/plan` and `/route/legs` verify the backend's own JWT if
one is sent, purely to tell a logged-in user apart from a guest for rate-limiting
purposes. Only the account/data endpoints (`/me`, `/plans`, `/favorites`,
`/visits`) require login (see "Security" below and "Database" under Commands).

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

### CI

`.github/workflows/ci.yml` runs on PRs and pushes to `main`: backend (`ruff`,
`pytest`, Python 3.11 and 3.12), migrations (real Postgres service:
`alembic upgrade head`, `alembic check`, downgrade/upgrade round-trip) and
frontend (`npm ci`, lint, `tsc`, `npm test`, build). Run the same commands locally before
pushing. Two things bit during setup: the frontend needs Node ≥ 20.19 (older
Node makes `npm ci` silently skip native bindings → "Cannot find native
binding"), and `app/services/planner.py` has `E501` ignored because its long
lines are LLM prompt text (wrapping would change the prompt).

### Frontend

All run from `frontend/`:
```
npm install
npm run dev      # Vite dev server at :5173, proxies /api/* to the backend at :8000
npm run build    # tsc -b && vite build
npm run lint      # oxlint
npm test          # Vitest (saf mantık: api.ts, prefs.ts, nav.ts, geo.ts, meta.ts, guestLimit.ts, authErrors.ts)
npx tsc -b --noEmit   # type-check without emitting
```
The frontend has a small Vitest suite (`src/*.test.ts`, `npm test`, also run in CI) that covers pure logic and `api.ts` with a stubbed `fetch`; there are no component/DOM tests (no jsdom) and `auth.ts` is covered by `auth.test.ts` (module reloaded per test with stubbed `localStorage`/`window`/`navigator`/`fetch` and fake timers; `getSession()`/`isAuthLoading()` exist so non-React code and tests can read the store). Vitest 5 needs Node ≥ 22: on an older local Node a failing test crashes the reporter with `Map.groupBy is not a function`. `meta.test.ts` also checks `THEME_TYPES` against `app/core/themes.py`, so editing one without the other fails the test. The frontend needs no env vars. The dev
proxy (`frontend/vite.config.ts`) means the backend must also be running
(`fastapi dev app/main.py`) for `/api/*` calls to resolve; account features
additionally need the database (see "Database" below).

### Database

```
docker compose up -d db          # Postgres 16 on 127.0.0.1:5433 (5432 was taken locally)
alembic upgrade head             # apply migrations
alembic revision --autogenerate -m "açıklama"   # after changing app/db/models.py; READ the result
alembic check                    # models and database agree?
```
Tests never need Postgres: they run against in-memory SQLite (the `client`
fixture in `tests/conftest.py`), which is why `app/db/models.py` uses a JSON
type with a JSONB variant. Anything Postgres-specific should also be checked
by hand against the real database.

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

- `JWT_SECRET` — required, ≥32 chars (validated), signs the backend's access tokens

Database/auth settings: `database_url` (optional at startup, but the DB-backed
endpoints fail without it; compose sets it for the `api` service),
`jwt_expire_minutes` (15), `refresh_token_expire_days` (30), `cookie_secure`
(default `true`; `.env` sets `false` for local http), `refresh_cookie_path`
(`/api/auth` — must match the path the *browser* sees, see "Security"),
`refresh_reuse_grace_seconds` (10), per-user caps `max_saved_plans_per_user` /
`max_favorites_per_user` / `max_visited_places_per_user`.

Other security-related settings are optional with safe defaults (see
"Security" below): `rate_limit_enabled` (default `true`, forced `false` in
tests), `guest_daily_plan_limit` (default `3`), `cors_origins` (default
`http://localhost:5173`).

## Architecture

Layering: `api/routes` → `services` → external APIs, with `schemas` (Pydantic
models) as the shared vocabulary between them. Routes only translate service
exceptions into `HTTPException`s; all real logic lives in services.

- [app/api/router.py](app/api/router.py) aggregates route modules
  (`health`, `auth`, `me`, `weather`, `places`, `geocoding`, `plan`, `route`,
  `plans`, `favorites`, `visits`) into one `api_router`, included by [app/main.py](app/main.py)'s `create_app()`.
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
  FastAPI dependency that verifies the backend's own access token (HS256 JWT
  signed with `JWT_SECRET`, `iss=rota-app`, `exp` and `sub` required —
  [app/core/security.py](app/core/security.py)) from the `Authorization: Bearer`
  header, returning the user id or `None`. It never raises — a missing or
  invalid token just means "treat as guest". `require_user_id` (same file)
  wraps it for login-required routes and raises `401`; use the `UserId` /
  `Session` aliases in [app/api/deps.py](app/api/deps.py) in route signatures.
  `UserId` also checks the account still exists (one PK lookup per request),
  so a deleted account's still-unexpired access token stops working at once
  instead of failing later on a foreign-key error. `DELETE /me` hard-deletes
  the user and every dependent row in one transaction (explicit deletes, so it
  doesn't depend on DB cascade settings; there is no soft delete — KVKK).
  **When you add a table with a `user_id`, add it to
  `services/users.py::delete_account`** or deletion will leave that data behind.
- **Observability** ([app/core/logging.py](app/core/logging.py),
  [app/core/request_id.py](app/core/request_id.py),
  [app/core/audit.py](app/core/audit.py)): every request gets an id
  (`RequestIdMiddleware`, `X-Request-ID` response header; an incoming one is
  accepted only if it matches `[A-Za-z0-9_-]{8,64}`, else a fresh uuid) that is
  stamped on every log line via a contextvar. `LOG_FORMAT=json` switches to one
  JSON object per line (exception *type* only, never the message — httpx errors
  can carry URLs with keys). User-supplied text must go through
  `logging.clean_log()` before being logged (strips newlines → no log
  injection; truncates), and coordinates / LLM reply text are not logged.
  Security events go to the `audit` logger via `audit(request, event)` (IP +
  path only, never a token, password or user id — logging identity is
  pending the KVKK decision): rate limit exceeded
  (`rate_limit.rate_limit_exceeded_handler`), guest quota exhausted, and
  invalid/expired access tokens (INFO, not WARNING: expiry is routine).
  `/health` is liveness only; `/health/ready` runs `SELECT 1` and answers
  `503 {"status":"unavailable"}` without detail.
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
  Logged-in users have their own daily caps, **per account and persisted in
  the DB** (`app/core/user_limit.py` + `app/services/usage.py`, table
  `daily_usage`, settings `user_daily_plan_limit` 30 / `user_daily_legs_limit`
  300); `/places/search` (free-text place search, one paid Google Text Search per call) has its own third counter `searches` (`guest_daily_search_limit` 20 / `user_daily_search_limit` 100), added by migration 0006: account creation is free, so a login alone must not unlock unlimited
  paid Google/Groq calls. The increment is a single conditional `UPDATE ... WHERE
  counter < limit` (atomic — concurrent requests can't overshoot), the day is
  Turkey time (fixed UTC+3), and the `429` carries `X-User-Limit-Reached`, not
  `X-Guest-Limit-Reached` (the frontend maps the latter to the "log in" screen,
  which makes no sense for someone already logged in). `/plan` and
  `/route/legs` therefore depend on a DB session even for guests (it's lazy —
  no connection is made unless a user id is present). Tests must not hit the
  real database: `tests/conftest.py` defaults `DATABASE_URL` to in-memory SQLite.
- [app/main.py](app/main.py)'s `create_app()` adds `CORSMiddleware`
  (origins from `cors_origins`) and only enables `/docs`, `/redoc`,
  `/openapi.json` when `settings.debug` is true — they're closed by default.
- **Ownership is enforced in code, not by the database**: with Supabase, RLS
  did it; now every query on a user's resource filters by `user_id` (see
  `app/services/{saved_plans,favorites,visits}.py`), and a resource that
  belongs to someone else returns the same `404` as one that doesn't exist.
  Keep that pattern for any new per-user table — there is no safety net below
  the service layer. `GET /shared/{id}` is the one deliberate exception: public,
  single-row-by-UUID lookup (never a listing), and it returns `is_owner`
  instead of the owner's `user_id`.
- **Refresh tokens** ([app/services/refresh_tokens.py](app/services/refresh_tokens.py),
  [app/api/cookies.py](app/api/cookies.py)): a long-lived opaque token in an
  `httpOnly`, `SameSite=Strict`, `Secure` cookie (`rota_refresh`); only its
  SHA-256 is stored. It rotates on every `/auth/refresh`; a revoked token
  replayed *after* `refresh_reuse_grace_seconds` revokes its whole family
  (theft detection), while a replay inside the grace window just returns `401`
  (two tabs refreshing at once). Changing the password revokes all of a user's
  tokens and issues a fresh one for the current device. The cookie `Path`
  (`refresh_cookie_path`, default `/api/auth`) must equal what the browser
  sees; if the `/api` prefix changes, the cookie silently stops being sent.
  Browser cookie `Secure` requires HTTPS in production (`cookie_secure=true`).
- **Password reset is shelved (KVKK): keep `SMTP_*` unset.** The code works but
  sending the address + reset link to a foreign mail provider is a cross-border
  transfer we don't want yet; with SMTP unset the feature is off (see below). Don't
  configure a provider before picking a domestic/EU one; see ROADMAP "Milestone 5".
- **Password reset** ([app/services/password_reset.py](app/services/password_reset.py)(app/services/password_reset.py),
  [app/services/email.py](app/services/email.py)): `POST /auth/forgot` always
  answers the same `202` whether or not the email has an account (no
  enumeration) and sends the mail in a background task so timing doesn't leak
  either; a per-account cooldown (`password_reset_cooldown_seconds`) stops mail
  bombing. The token is single-use, 1 hour, stored only as SHA-256, and sits in
  the link's **fragment** (`/#reset=...`) so it never reaches server logs or
  `Referer`; the frontend (`App.tsx::readResetToken`) reads it and strips it from
  the address bar. A successful reset revokes every session. Email is plain
  stdlib `smtplib` (no dependency) against any SMTP provider; with `smtp_host`/
  `smtp_from` unset the feature is **off** (`/auth/forgot` → 503,
  `/auth/capabilities` → `password_reset: false`, and the UI hides the link).
  Failures are swallowed and logged by exception *type* only — never the
  address or message, since the message holds the reset link. TLS uses
  `certifi`'s CA bundle (`email.py::_ssl_context`), not Python's default: a
  python.org macOS Python ships with *no* root certificates, so the default
  context fails every SMTP connection with "unable to get local issuer
  certificate" while httpx (which uses certifi) works fine on the same machine.
  `tests/conftest.py` forces `SMTP_*` blank so tests never see your real `.env`
  credentials (one test once tried to reach the real provider). Add any new
  user-keyed table to `services/users.py::delete_account`.
- **Migrations are the schema's source of truth** (`migrations/`, generated
  from `app/db/models.py`); `supabase/` no longer exists. Don't edit an applied
  migration — add a new one.
- [frontend/vite.config.ts](frontend/vite.config.ts)'s `cspPlugin` injects a
  `Content-Security-Policy` meta tag into `index.html`, but only for
  `npm run build` (`apply: 'build'`), not `npm run dev`: the dev server's
  Fast Refresh preamble needs an inline `<script>` that a strict
  `script-src` would block. `script-src` itself has no `'unsafe-inline'`
  (defense-in-depth against the same inline-event-handler vector the
  Leaflet pin XSS fix above closed); `style-src` does, for
  Tailwind/React's inline styles. `img-src` allows
  `https://*.tile.openstreetmap.org` (Leaflet tiles), `connect-src` is
  `'self'` only (the API is same-origin under `/api`). It was verified with a
  Playwright smoke test against a real `npm run build` output (zero CSP
  console violations) when Supabase was still an external origin — re-verify
  in a real browser if you touch this plugin or add a new external resource.

## Adding a new endpoint/service

1. Define request/response models in `app/schemas/`.
2. Implement the external call in `app/services/`, raising a dedicated
   `*ServiceError` on failure (see [app/services/weather.py](app/services/weather.py)
   for the smallest example).
3. Add a route in `app/api/routes/`, catching the service error and
   mapping it to an `HTTPException`.
4. Register the router in [app/api/router.py](app/api/router.py).
5. Test the service with `respx`-mocked HTTP responses, not the route.

For a DB-backed, per-user resource instead: add the model in `app/db/models.py`
and generate a migration; write a service that filters every query by
`user_id`; use `UserId`/`Session` from `app/api/deps.py`; cap per-user rows;
and test the routes through the `client` fixture (in-memory SQLite) including
"another user can't see/delete it" cases — see `tests/test_saved_plans_routes.py`.

## Frontend

`frontend/src/App.tsx` is a hand-rolled state machine: a single `view`
union (`{ name: 'location' | 'prefs' | 'loading' | 'limit' | 'clarify' |
'error' | 'results' | 'detail' | 'navigate' | 'account' }`) drives which
screen under `frontend/src/screens/` renders inside `components/Shell.tsx`;
there is no router library. `plan: DayPlan | null` is the one source of
truth for the current plan and is lifted to `App.tsx`; screens receive it
and report changes back up via callbacks (e.g. `DetailScreen`'s
`onAlternativesChange`) rather than owning their own copy.

- **Auth is the backend's own** (`auth.ts`), and login is optional — a
  guest can use the app without an account. `auth.ts` is a module-level
  session store read via `useSession()` / `useAuthLoading()` (no context
  provider): the short-lived access token lives in `localStorage`, the
  refresh token is an `httpOnly` cookie JS can't see. It refreshes silently
  60 s before expiry, on page load (if a login hint is set), when a hidden tab
  becomes visible, and on a `401`; across tabs it uses Web Locks plus the
  `storage` event. Only a `401` from `/auth/refresh` ends the session — network
  or `5xx` errors keep it and retry. `signIn`/`signUp`/`signOut`/
  `updateUsername`/`changePassword`/`deleteAccount`/`requestPasswordReset`/
  `resetPassword` are plain exported functions that update the store. The
  password-reset link (`/#reset=<token>`) is read once by
  `App.tsx::readResetToken` (pure, StrictMode-safe), the token is stripped from
  the address bar in an effect, and `AccountScreen` shows the new-password form
  before anything else; "Şifremi unuttum" only renders if
  `fetchAuthCapabilities()` says the server has SMTP configured. The frontend's
  own `guestLimit.ts` (a `localStorage` counter) is just UX: it shows the
  "limit reached" screen before even making a request. The backend enforces
  the real cap server-side (see "Security" above) and learns the user's
  identity from the `Authorization` header that `createPlan()` / `fetchLegs()`
  attach (`session.access_token`).
- **Reload persistence** (`planStorage.ts`): the current plan, preferences and open
  screen (`results` or `detail`+index; everything else falls back to `results`) are
  mirrored to `localStorage` (`rota.lastPlan`) by an effect in `App.tsx` and restored
  by a pure lazy initializer. Records expire 12 h after the plan was *generated*
  (`createdAt`, held in a ref — re-saving or reloading must not extend it), are
  version-tagged and shape-checked (anything doubtful is ignored → home screen).
  An explicit sign-out or account deletion (`AccountScreen` → `onLoggedOut`) clears
  both the stored copy and the in-memory plan/prefs; an *expired* session does not
  (that would wipe the plan mid-use). It is device-local, never sent to the server,
  and is mentioned in `PrivacyScreen`.
- `savedPlans.ts`, `favoritePlaces.ts` and `visitedPlaces.ts` are thin
  wrappers over `apiRequest` (`api.ts`) for `/plans` + `/shared/{id}`,
  `/favorites` and `/visits`. They return `{ data, error }` via `settle()` and
  take the access token as an argument (not a user id: the backend derives the
  user from the token). The privacy model for shared plans is a hard-to-guess
  UUID plus single-row lookup (`/shared/{id}`), never a listing; `is_owner` in
  the response decides whether `SharedPlanScreen` shows the "remove" star.
  `favoritePlaces.ts` backs the heart icon on each stop in `DetailScreen.tsx`
  and the "Favori Mekanlarım" list in `AccountScreen.tsx`.
  `visitedPlaces.ts::recordVisit` is called (fire-and-forget, non-critical)
  whenever `DetailScreen.tsx`'s "Ulaşıldı" toggle transitions a stop to done —
  the server increments a per-place counter atomically, which
  `LocationScreen.tsx` reads to show "Sık Gidilen Yerlerin" on the home
  screen. Tapping one of those sets `Preferences.anchorPlace` and jumps
  straight to `prefs` (see `PlanRequest.anchor_place` above) via a dedicated
  `onPickFrequent` callback in `App.tsx` — deliberately not composed from the
  existing `onChange`+`onContinue` pair, since calling both synchronously
  would read `onContinue`'s stale `prefs` closure before React re-renders.
- `api.ts` holds thin `fetch('/api/...')` wrappers (one per backend
  endpoint) that throw `ApiError` on non-2xx or network failure; screens
  call these instead of using `fetch` directly. `ApiError` carries two distinct limit flags: `guestLimit` (`X-Guest-Limit-Reached` → "log in" screen) and `userLimit` (`X-User-Limit-Reached` → "daily quota used" message, no retry button). `apiRequest()` is the shared
  helper for the account/data endpoints: it surfaces the backend's (Turkish)
  `detail` as the error message and calls the registered unauthorized
  handler on a `401` with a token. The `/api` prefix is
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
