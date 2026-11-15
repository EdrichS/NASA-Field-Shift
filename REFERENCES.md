# References

Every dataset, API, library and tool SowSmart uses. NASA data is the core of every analysis; other sources are supplements.

## NASA data and services

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| Global Imagery Browse Services (GIBS): WMTS layers `MODIS_Terra_CorrectedReflectance_TrueColor`, `HLS_S30_Nadir_BRDF_Adjusted_Reflectance`, `MODIS_Terra_NDVI_8Day`, `SMAP_L4_Analyzed_Root_Zone_Soil_Moisture`, `IMERG_Precipitation_Rate`; WMS GetMap (EPSG:4326) layer `BlueMarble_NextGeneration` | NASA ESDIS | https://gibs.earthdata.nasa.gov/wmts/epsg3857/best/1.0.0/WMTSCapabilities.xml (layer IDs and tile matrix sets checked Nov 15, 2026) | NASA open data, no restrictions; credit NASA GIBS / ESDIS | "Browse NASA maps" mode: pick a layer and a date, then tap a spot; the PDF cover's locator inset (NASA Blue Marble, a cloud-free composite, WMS GetMap) |
| Harmonized Landsat Sentinel-2 (HLS) S30, via GIBS | NASA (LP DAAC), with ESA Sentinel-2 | https://www.earthdata.nasa.gov/data/projects/hls | NASA open data | 30 m "field detail" browse layer (clear days only) |
| EONET (Earth Observatory Natural Event Tracker) API v3 | NASA | https://eonet.gsfc.nasa.gov/docs/v3 (category IDs checked at /api/v3/categories, Nov 15, 2026) | NASA open data | Open severe storms/typhoons, floods, wildfires, drought, landslides, volcanoes and temperature extremes; stored in TigerData and matched with PostGIS against every saved field for region-wide alerts (storm tracks also tell whether a storm is moving closer) |
| NASA POWER API v2.10 (Agroclimatology community), accessed 2026/11/14 | NASA Langley Research Center | https://power.larc.nasa.gov/docs/services/api/ (parameters: https://power.larc.nasa.gov/api/system/manager/parameters?community=AG&temporal=daily) | NASA data, free. Credit: "The data was obtained from National Aeronautics and Space Administration (NASA) Langley Research Center's Prediction Of Worldwide Energy Resources (POWER) project funded through the NASA Earth Science Division." | Daily temperature (mean/max/min), dew point, rainfall, humidity, solar radiation and wind for each field, plus 1996–2025 (latest 30 complete years) monthly climatology (0.5° x 0.625° meteorology, 1° x 1° solar) |
| FIRMS (Fire Information for Resource Management System) Area API, sources `VIIRS_NOAA20_NRT` and `VIIRS_NOAA21_NRT` | NASA LANCE | https://firms.modaps.eosdis.nasa.gov/api/ | NASA data, free with a MAP_KEY | Active-fire detections within 5 km of a saved field in the last 2 days (fire alerts). VIIRS S-NPP NRT is not used: its data stopped on 2026-11-02 per FIRMS `data_availability` |
| SRTM Digital Elevation 30m (`USGS/SRTMGL1_003`) | NASA / USGS | https://developers.google.com/earth-engine/datasets/catalog/USGS_SRTMGL1_003 | NASA data, public domain | Elevation and slope per field (erosion risk); accessed through Earth Engine |
| SMAP L4 Global 3-hourly 9 km Surface and Root Zone Soil Moisture v8 (`NASA/SMAP/SPL4SMGP/008`) | NASA (NSIDC DAAC) | https://developers.google.com/earth-engine/datasets/catalog/NASA_SMAP_SPL4SMGP_008 | NASA data, public domain | Monthly root-zone (0–100 cm) and surface (0–5 cm) soil moisture per field, 2015–present; drought-stress anomalies. Chosen over SMAP L3 enhanced v006, whose record only starts Dec 2023; v007 is deprecated. |
| MODIS Terra Vegetation Indices 16-Day 250 m v6.1 (`MODIS/061/MOD13Q1`) | NASA (LP DAAC) | https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD13Q1 | NASA data, public domain | Monthly NDVI per field, 2001–present: bare-field months and vegetation stress |
| MODIS Terra Net Evapotranspiration 8-Day 500 m v6.1, gap-filled (`MODIS/061/MOD16A2GF`) and standard (`MODIS/061/MOD16A2`) | NASA (LP DAAC) | https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD16A2GF | NASA data, public domain | Monthly water use (mm/day): gap-filled 2001–2025, newest months from the standard 8-day product |
| MODIS Terra Land Surface Temperature 8-Day 1 km v6.1 (`MODIS/061/MOD11A2`) | NASA (LP DAAC) | https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MOD11A2 | NASA data, public domain | Monthly daytime land surface temperature per field: heat stress |
| GPM IMERG Final Run V07, monthly (`NASA/GPM_L3/IMERG_MONTHLY_V07`) | NASA (GES DISC) | https://developers.google.com/earth-engine/datasets/catalog/NASA_GPM_L3_IMERG_MONTHLY_V07 | NASA data, public domain | Monthly satellite-gauge rainfall (mm/day), 2001–present (lags a few months); heavy-rain context |
| GRACE & GRACE-FO Monthly Mass Grids, JPL mascons RL06.3 v4 CRI (`NASA/GRACE/MASS_GRIDS_V04/MASCON_CRI`) | NASA JPL (GRACE with DLR/GFZ, GRACE-FO with GFZ) | https://developers.google.com/earth-engine/datasets/catalog/NASA_GRACE_MASS_GRIDS_V04_MASCON_CRI | NASA data, public domain | Long-term regional water storage trend (regional context only, 3° mascons) |

## Other data (not NASA)

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| FAO EcoCrop database (`EcoCrop_DB.csv`, 2,568 crops), via the OpenCLIM/ecocrop repository, commit `ea43ecd` | UN FAO (data); OpenCLIM (repository) | https://gaez.fao.org/pages/ecocrop · https://github.com/OpenCLIM/ecocrop | Repository under the UK Open Government Licence v3 ("please cite this repository"); credit FAO EcoCrop | Temperature, rainfall and pH ranges, growing-season length, drainage and killing-frost temperatures for our 35 rotation crops and 8 fruit trees (crop suitability in the engine; fruit-tree ranges copied into `data/perennials.csv` by `scripts/build_perennials.py`) |
| Crop traits (`data/crops_traits.csv`, generated by `scripts/fill_crop_traits.py` with documented rules) | SowSmart team (Claude Code), from FAO-56 Table 22 (root depth), FAO Irrigation Water Management Training Manual 3 Table 14 + ch. 4 (water need, drought sensitivity, paddy rice), FAO EcoCrop (heat, drainage, forage), SARE (cover-crop roles), PROSEA (sesbania as a green manure for lowland rice), FAO-56 Table 11 (watermelon growing period, missing in EcoCrop); labor is a flagged team estimate | https://www.fao.org/4/x0490e/x0490e0e.htm · https://www.fao.org/4/x0490e/x0490e0b.htm · https://www.fao.org/4/s2022e/s2022e07.htm · https://www.fao.org/4/s2022e/s2022e08.htm · https://www.sare.org/resources/managing-cover-crops-profitably-3rd-edition/ · https://uses.plantnet-project.org/en/Sesbania_rostrata_(PROSEA) | Each row cites its sources; estimates flagged in notes | Legume, plant family, root depth, water need, heat/drought/waterlogging tolerance, cover-crop role, forage, labor (engine scoring) |
| Pest-risk weather rules (`data/pest_rules.csv`) | SowSmart team (Claude Code), from IRRI rice biotic stress manual (bacterial leaf blight), TNAU Agritech citing IRRI (sheath blight), ResearchersLinks review (mungbean Cercospora leaf spot), Crop Protection Network (corn gray leaf spot; frogeye overview), NC State Extension (soybean frogeye leaf spot) | URLs per row in the CSV | Each rule cites its source | "Conditions favor…" pest-risk alerts; daily mean humidity stands in for hourly thresholds (noted per rule) |
| ESA WorldCover 10 m v200 (2021) | ESA (2026 Space Agency Partner) | https://developers.google.com/earth-engine/datasets/catalog/ESA_WorldCover_v200 | CC BY 4.0 | Verified the showcase points sit in 100% cropland (Philippines) and 0% trees/buildings/water (Iowa) |
| USDA NASS Cropland Data Layer 2021–2025 | USDA NASS | https://developers.google.com/earth-engine/datasets/catalog/USDA_NASS_CDL | Public domain (US government) | Found an Iowa field that alternated soybean and corn every year 2021–2025 |
| MODIS Land Cover Type (MCD12Q1 v6.1) | NASA | https://developers.google.com/earth-engine/datasets/catalog/MODIS_061_MCD12Q1 | NASA data, public domain | Confirmed the Philippines showcase point is classified Croplands (2025) |
| Showcase-farm rotation sources | PhilRice / Daily Tribune, DA Bureau of Plant Industry, DA AMIA (rice-rice-mungbean), AGRIS/UPLB, PAGASA, USDA NASS Iowa Crop Progress 2024, Iowa State University Extension | listed in `data/showcase_farms.json` | Cited per claim | Typical rotations and months for the two demo farms |
| JAXA GSMaP v8 operational, hourly (`JAXA/GPM_L3/GSMaP/v8/operational`, band `hourlyPrecipRate`) | JAXA (2026 Space Agency Partner), via Google Earth Engine | https://developers.google.com/earth-engine/datasets/catalog/JAXA_GPM_L3_GSMaP_v8_operational | JAXA G-Portal terms: free use with credit to JAXA | Rain in the last 24 hours at each saved field for heavy-rain alerts (near real time, newest image about half a day old; IMERG Final Run lags months) |
| FAOSTAT Crops and livestock products, "Area harvested" and "Production" (bulk file of Dec 23, 2025; years 2022–2024) | UN FAO | https://www.fao.org/faostat/en/#data/QCL | CC BY 4.0 (FAO open data) | `data/regional_crops.csv` (built by `make regional-crops`): which of our crops and fruit trees each country harvests (suggestions are limited to crops grown on at least 1,000 ha in the field's country; more widely grown crops rank slightly higher) and the national yield |
| FAOSTAT Producer prices, USD/tonne, annual values (bulk file of Oct 9, 2025; latest 3 years, none older than 6 years) | UN FAO | https://www.fao.org/faostat/en/#data/PP | CC BY 4.0 (FAO open data) | National yield × farm-gate price = typical gross value per hectare before costs, used by the income score and in the "Add a cash crop" explanation |
| FAO GAUL 2024, level 0 (`projects/sat-io/open-datasets/FAO/GAUL/GAUL_2024_L0`, Earth Engine community catalog) | UN FAO | https://gee-community-catalog.org/projects/gaul/ | FAO terms (non-commercial, with credit) | Finds which country a field is in, to pick its locally grown crops |
| Heavy-rain terms ("heavy" 64.5-115.5 mm in 24 h, "very heavy" 115.6-204.4 mm) | India Meteorological Department (RSMC New Delhi terminology) | https://rsmcnewdelhi.imd.gov.in/images/pdf/terminology.pdf | Public reference | Thresholds for heavy-rain alert severity |
| Esri World Imagery and World Light Gray Canvas basemaps | Esri (Maxar, Earthstar Geographics) | https://www.arcgis.com/home/item.html?id=10df2279f9684e4a9f6a7f08febac2a9 | Esri terms of use; attribution shown on every map | Close-up satellite view so a farmer can recognize the field (NASA imagery is 30 m-250 m, too coarse to see one field) and the street map for finding a place; the PDF cover's field photo (MapServer `export`, a cloud-free mosaic, with the analyzed area drawn on top) |
| SoilGrids 2.0, 250 m (`projects/soilgrids-isric/{clay,sand,silt,soc,phh2o,bdod}_mean`) | ISRIC – World Soil Information | https://gee-community-catalog.org/projects/isric/ (Poggio et al. 2021, SOIL 7, 217–240) | CC BY 4.0 | Estimated 0–30 cm clay/sand/silt (→ USDA texture class), organic carbon, pH and bulk density per field; farmer's soil test values override it |

## Platforms and services

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| Google Earth Engine (project `sowsmart-ee`, noncommercial) | Google | https://earthengine.google.com | Earth Engine terms of service (noncommercial use) | Fetches and reduces NASA satellite data and SoilGrids over each field |
| TigerData (Tiger Cloud free service: Postgres + TimescaleDB + PostGIS) | TigerData (sponsor) | https://www.tigerdata.com | Free tier, TigerData terms | The app's only database: daily climate in a TimescaleDB hypertable, field geometries and region-wide alert matching with PostGIS, users' saved fields, analyses, reports and alerts. Only the backend connects. |
| Auth0 (free plan) | Okta / Auth0 (sponsor) | https://auth0.com | Free plan, Auth0 terms | Sign-up and login with Auth0 Universal Login (passwords never touch our app): SPA app "SowSmart Web" (Auth0 React SDK) and API "SowSmart API" (RS256). The backend checks every token against the tenant's JWKS, audience and issuer, filters all user data by the token's `sub`, and reads the verified email from `/userinfo` for alert emails. Guests can analyze without it; an account saves fields, keeps history and gets alerts. |
| Cloudflare: Quick Tunnel (`cloudflared`) and Pages | Cloudflare (sponsor) | https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/do-more-with-tunnels/trycloudflare/ · https://pages.cloudflare.com | Free, Cloudflare terms | Quick Tunnel gives the live app (and its API, through one origin) a public HTTPS link for phones, judges and browser push during the event (`make tunnel`). Pages hosts a static copy that keeps the two demo farms working after the event without our server (`make pages`). |
| Gmail SMTP (App Password) | Google | https://support.google.com/accounts/answer/185833 | Google terms | Sends alert emails when SMTP_* is set in `.env` (optional; alerts always show in the app) |
| Web Push (VAPID, RFC 8292) | IETF / browser push services | https://datatracker.ietf.org/doc/html/rfc8292 | Open standard | Phone and browser notifications for alerts; keys made by `make vapid` |
| Grok API | xAI (sponsor) | https://docs.x.ai | xAI API terms (paid per token, sponsor credits) | Writes the plain-language Tier 1 and Tier 2 reports from the engine's JSON results through the Chat Completions endpoint with structured outputs (JSON schema). Model: `grok-4.20-0309-non-reasoning` (the showcase reports, reviewed by the team in English and Tagalog, were written with it and are kept for the demo). Explains only; never decides; every number is checked against the input. |

## Backend libraries

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| FastAPI | Sebastián Ramírez and contributors | https://fastapi.tiangolo.com | MIT | Backend API |
| Uvicorn | Encode | https://www.uvicorn.org | BSD-3-Clause | Runs the FastAPI app |
| pydantic-settings | Pydantic | https://docs.pydantic.dev/latest/concepts/pydantic_settings/ | MIT | Loads config from `.env`; secrets kept as `SecretStr` |
| HTTPX | Encode | https://www.python-httpx.org | BSD-3-Clause | HTTP client for NASA POWER, xAI, EONET, FIRMS and Auth0 `/userinfo` |
| PyJWT (+ cryptography) | José Padilla and contributors; Python Cryptographic Authority | https://pyjwt.readthedocs.io · https://cryptography.io | MIT; Apache-2.0/BSD | Verifies Auth0 RS256 access tokens with the tenant's JWKS; makes the VAPID key pair |
| pywebpush (+ py-vapid) | Mozilla Services and contributors | https://github.com/web-push-libs/pywebpush | MPL-2.0 | Sends browser push notifications for alerts |
| psycopg 3 | Psycopg team | https://www.psycopg.org/psycopg3/ | LGPL-3.0 | Postgres driver for TigerData |
| earthengine-api | Google | https://developers.google.com/earth-engine/guides/python_install | Apache-2.0 | Earth Engine Python client |
| pytest | pytest-dev | https://pytest.org | MIT | Backend tests |
| Ruff | Astral | https://docs.astral.sh/ruff/ | MIT | Python linter |
| Matplotlib | Matplotlib Development Team | https://matplotlib.org | Matplotlib License (PSF-based, BSD-compatible) | Feature-table chart; charts in the PDF report |

## Frontend libraries

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| React | Meta and contributors | https://react.dev | MIT | UI |
| Vite | VoidZero and contributors | https://vite.dev | MIT | Dev server and build |
| TypeScript | Microsoft | https://www.typescriptlang.org | Apache-2.0 | Typed frontend code |
| MapLibre GL JS | MapLibre | https://maplibre.org | BSD-3-Clause | Every map: locate, satellite preview, field drawing in detailed mode, alert maps |
| Terra Draw (+ MapLibre adapter) | James Milner and contributors | https://terradraw.io | MIT | "Draw the field" mode (polygon boundary) |
| Turf (`@turf/area`, `@turf/circle`) | Turf.js contributors | https://turfjs.org | MIT | Field area in hectares; the 250 m circle shown around a point |
| Auth0 React SDK (`@auth0/auth0-react`) | Auth0 | https://github.com/auth0/auth0-react | MIT | Login, sign-up and access tokens in the browser |
| Google Fonts: Fraunces, Outfit, Noto Sans Devanagari | Google Fonts (font authors) | https://fonts.google.com | SIL Open Font License 1.1 | Typography (teammate's screen designs) |
| Oxlint | Oxc project | https://oxc.rs/docs/guide/usage/linter | MIT | Frontend linter |

## Tools

| Name | Provider | URL | License | How it's used |
|---|---|---|---|---|
| Claude Code | Anthropic | https://claude.com/claude-code | Commercial | AI coding assistant used during development |
| Auth0 CLI | Auth0 (Okta) | https://github.com/auth0/auth0-cli | MIT | Creates the Auth0 SPA app and API from the terminal instead of the dashboard |
| cloudflared and Wrangler | Cloudflare | https://github.com/cloudflare/cloudflared · https://developers.cloudflare.com/workers/wrangler/ | Apache-2.0; MIT/Apache-2.0 | Quick Tunnel and the Pages deploy |
| Cursor | Anysphere (sponsor) | https://cursor.com | Commercial | The team's editor, with Claude Code running in its terminal |
