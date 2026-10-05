# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

Rota App: a FastAPI backend that builds group activity/day-trip plans. Given a
location, duration, budget, and group type, it searches nearby places (Google
Places API), fetches current weather (Open-Meteo), and asks Gemini to compose
2-3 alternative themed day plans using only the fetched places.

Code comments, docstrings, and log messages are written in Turkish; keep new
ones consistent with that convention unless told otherwise.

## Commands

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

## Configuration

Settings are a pydantic-settings `Settings` object in [app/core/config.py](app/core/config.py),
loaded from a `.env` file and cached via `@lru_cache` (`get_settings()`). Two
keys have no default (`places_api_key`, `gemini_api_key`) — the app fails to
start without them, by design. Copy `.env.example` to `.env` and fill in:
- `PLACES_API_KEY` — Google Places (New) API key
- `GEMINI_API_KEY` — Groq API Key

## Architecture

Layering: `api/routes` → `services` → external APIs, with `schemas` (Pydantic
models) as the shared vocabulary between them. Routes only translate service
exceptions into `HTTPException`s; all real logic lives in services.

- [app/api/router.py](app/api/router.py) aggregates route modules
  (`health`, `weather`, `places`, `plan`) into one `api_router`, included by
  [app/main.py](app/main.py)'s `create_app()`.
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
- [app/services/planner.py](app/services/planner.py) calls Gemini
  (`google-genai`) with `response_schema=DayPlan`/`_ThemeSelection` for
  structured JSON output. After parsing, `_validate_stops` strips any stop
  whose `place_id` isn't in the input place pool (the model is instructed
  not to invent places, but responses are still validated defensively).
  `PlannerServiceError` covers both call failures and empty/invalid results.
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
