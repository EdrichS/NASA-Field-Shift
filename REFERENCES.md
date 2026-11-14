# References

Every dataset, API, library and tool SowSmart uses. NASA data is the core of every analysis; other sources are supplements.

## NASA data and services

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| Global Imagery Browse Services (GIBS), layer `BlueMarble_ShadedRelief_Bathymetry` | NASA ESDIS | https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml | NASA open data, no restrictions; credit NASA GIBS / ESDIS | Base map tiles for the world map (WMTS, EPSG:3857) |
| NASA POWER API v2.10 (Agroclimatology community), accessed 2026/11/14 | NASA Langley Research Center | https://power.larc.nasa.gov/docs/services/api/ (parameters: https://power.larc.nasa.gov/api/system/manager/parameters?community=AG&temporal=daily) | NASA data, free. Credit: "The data was obtained from National Aeronautics and Space Administration (NASA) Langley Research Center's Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division." | Daily temperature (mean/max/min), dew point, rainfall, humidity, solar radiation and wind for each field, plus 1991–2020 monthly climatology (0.5° x 0.625° meteorology, 1° x 1° solar) |
| FIRMS (Fire Information for Resource Management System) Area API | NASA LANCE | https://firms.modaps.eosdis.nasa.gov/api/ | NASA data, free with a MAP_KEY | Active-fire detections near saved fields for alerts (step 4.2); key checked by `scripts/check_setup.py` |
| SRTM Digital Elevation 30m (`USGS/SRTMGL1_003`) | NASA / USGS | https://developers.google.com/earth-engine/datasets/catalog/USGS_SRTMGL1_003 | NASA data, public domain | Elevation and slope per field (erosion risk); accessed through Earth Engine |

## Platforms and services

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| Google Earth Engine (project `sowsmart-ee`, noncommercial) | Google | https://earthengine.google.com | Earth Engine terms of service (noncommercial use) | Fetches and reduces NASA satellite data and SoilGrids over each field |
| TigerData (Tiger Cloud free service: Postgres + TimescaleDB + PostGIS) | TigerData (sponsor) | https://www.tigerdata.com | Free tier, TigerData terms | The app's only database: daily climate in a TimescaleDB hypertable, field geometries and region-wide alert matching with PostGIS, users' saved fields, analyses, reports and alerts. Only the backend connects. |
| Auth0 (free plan) | Okta / Auth0 (sponsor) | https://auth0.com | Free plan, Auth0 terms | Sign-up and login: SPA app "SowSmart Web" in the browser, API "SowSmart API" (RS256) whose tokens the backend validates. Guests can analyze without it; an account saves fields and gets alerts. |
| Grok API | xAI (sponsor) | https://docs.x.ai | xAI API terms (paid per token, sponsor credits) | Writes the plain-language Tier 1 and Tier 2 reports from the engine's JSON results, with structured outputs. Explains only; never decides or adds numbers. |

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
| Auth0 CLI | Auth0 (Okta) | https://github.com/auth0/auth0-cli | MIT | Creates the Auth0 SPA app and API from the terminal instead of the dashboard |
