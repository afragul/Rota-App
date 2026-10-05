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
Leaflet) that consumes this API — see "Frontend" below. The backend has no
knowledge of the frontend's auth (Supabase): no endpoint verifies a user
identity today.

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
- Each service module defines its own `*ServiceError` exception; routes
  catch these and convert to `502` responses. Follow this pattern for new
  external integrations.

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
union (`{ name: 'location' | 'prefs' | 'loading' | 'clarify' | 'error' |
'results' | 'detail' | 'navigate' | 'account' }`) drives which screen under
`frontend/src/screens/` renders inside `components/Shell.tsx`; there is no
router library. `plan: DayPlan | null` is the one source of truth for the
current plan and is lifted to `App.tsx`; screens receive it and report
changes back up via callbacks (e.g. `DetailScreen`'s
`onAlternativesChange`) rather than owning their own copy.

- **Auth is Supabase-only and frontend-only** (`supabase.ts`, `auth.ts`).
  The backend never sees a user identity — no endpoint checks a JWT. Login
  is optional; a guest can use the app without an account, soft-limited by
  `guestLimit.ts` (a `localStorage` counter, not a real quota — the comment
  in that file is explicit that real enforcement would need backend JWT
  checks, which don't exist yet).
- `savedPlans.ts` wraps `supabase.from('saved_plans')` for the
  save/favorite/share-by-link feature. The privacy model is a hard-to-guess
  UUID as the row id, not an ACL — the table is readable by anyone with the
  link, deletable only by the owner. `AccountScreen.tsx` and
  `SharedPlanScreen.tsx` are the two screens that touch this table.
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
  constraint unless told otherwise.
- `screens/NavigationScreen.tsx` + `nav.ts` + `components/NavMap.tsx`
  implement live turn-by-turn navigation using `watchPosition`, computing
  progress against the already-fetched route polyline client-side; it only
  calls the backend again (`POST /route/approach`) when the user strays far
  enough off-route to need a recompute.
