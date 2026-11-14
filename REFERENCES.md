# References

Every dataset, API, library and tool SowSmart uses. NASA data is the core of every analysis; other sources are supplements.

## NASA data and services

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| Global Imagery Browse Services (GIBS), layer `BlueMarble_ShadedRelief_Bathymetry` | NASA ESDIS | https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml | NASA open data, no restrictions; credit NASA GIBS / ESDIS | Base map tiles for the world map (WMTS, EPSG:3857) |

## Backend libraries

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| FastAPI | Sebastián Ramírez and contributors | https://fastapi.tiangolo.com | MIT | Backend API |
| Uvicorn | Encode | https://www.uvicorn.org | BSD-3-Clause | Runs the FastAPI app |
| pydantic-settings | Pydantic | https://docs.pydantic.dev/latest/concepts/pydantic_settings/ | MIT | Loads config from `.env`; secrets kept as `SecretStr` |
| HTTPX | Encode | https://www.python-httpx.org | BSD-3-Clause | HTTP client for outside APIs (setup checks) |
| psycopg 3 | Psycopg team | https://www.psycopg.org/psycopg3/ | LGPL-3.0 | Postgres driver for TigerData |
| earthengine-api | Google | https://developers.google.com/earth-engine/guides/python_install | Apache-2.0 | Earth Engine Python client |
| pytest | pytest-dev | https://pytest.org | MIT | Backend tests |
| Ruff | Astral | https://docs.astral.sh/ruff/ | MIT | Python linter |

## Frontend libraries

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| React | Meta and contributors | https://react.dev | MIT | UI |
| Vite | VoidZero and contributors | https://vite.dev | MIT | Dev server and build |
| TypeScript | Microsoft | https://www.typescriptlang.org | Apache-2.0 | Typed frontend code |
| MapLibre GL JS | MapLibre | https://maplibre.org | BSD-3-Clause | Interactive map |
| Oxlint | Oxc project | https://oxc.rs/docs/guide/usage/linter | MIT | Frontend linter |

## Tools

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| Claude Code | Anthropic | https://claude.com/claude-code | Commercial | AI coding assistant used during development |
