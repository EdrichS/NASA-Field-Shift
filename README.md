# SowSmart

**Crop-rotation advice for any field on Earth, from NASA satellite data, in the farmer's own language.**

Built for the NASA Space Apps Challenge 2026 · Challenge: *Adapting Farms with NASA Data*

> SowSmart supports farmer judgment and local agricultural expertise. It never replaces them.

## Try it

| | |
|---|---|
| **Demo farms (no login, works anytime)** | https://sowsmart-8zm.pages.dev · [Tagum City rice](https://sowsmart-8zm.pages.dev/#/demo/tagum-rice) · [Iowa corn-soybean](https://sowsmart-8zm.pages.dev/#/demo/iowa-corn-soybean) |
| **Demo deck** | [link] |
| **Full app (sign-in, live analysis, alerts)** | Runs during local judging through a Cloudflare Tunnel link |

## What it does

1. **Find your land:** use your location, tap a point, draw the field boundary, or browse NASA satellite layers by date.
2. **See what the satellites see:** when the field sits bare, the driest soil months, rain, heat, frost, slope and soil, from years of NASA data. The farmer can correct any card, and the scores follow.
3. **Answer up to five questions:** current crops, water, equipment, top goal, crops you won't grow. Every question accepts "I don't know".
4. **Compare rotations:** your current rotation vs. four alternatives (fill the bare months with legumes or green manure, break the pest cycle, save water, add a cash crop such as a fruit or vegetable) on a 12-month calendar, with benefits, risks, information gaps and questions for a local expert. Every alternative fills each bare window a local crop fits (and names the other crops that fit); a window nothing fits says why and how to protect the soil. Fruit trees that suit the field's climate all year are suggested for bunds and field edges.
5. **Read it your way:** a plain-language report in up to two languages (e.g. English and Tagalog), technical details only on request, and a printable PDF.
6. **Get warned (with an account):** storms and other natural events, fires, heavy rain, dry soil and pest-favoring weather near your saved fields, in the app, by email and as phone notifications. One storm alerts every farmer in its path.

Suggestions only include crops actually grown in the field's country (FAO statistics), so seed, know-how and buyers exist locally.

## How it works

```
NASA + partner data  ──►  12-month field features  ──►  Scoring engine  ──►  AI writes plain words  ──►  App · PDF · alerts
(per field, with             (each value keeps its         (decides: 7 scores,      (explains only; every
 dataset, resolution,         source)                       weighted by goals)       number is checked)
 period)
```

- **The engine decides:** deterministic Python filters crops with FAO EcoCrop ranges and the country's crop list, builds four alternatives and scores water, soil building, erosion, pest cycle, weather risk, income (FAOSTAT national yield × farm-gate price, where known) and labor.
- **AI only explains:** Grok (xAI) turns the engine's results into a report per language. Any number not in the engine's output is rejected; the ranking never changes.
- **Alerts:** NASA EONET events are matched with PostGIS against every saved field; FIRMS fires, JAXA GSMaP heavy rain, SMAP dry soil and cited pest-weather rules are checked per field.

## Data

| Source | Used for |
|---|---|
| NASA POWER | Daily weather and 30-year normals; crop water demand; pest-risk weather |
| NASA SMAP L4 | Soil moisture; dry-soil alerts |
| NASA MODIS (NDVI, ET, land surface temperature) | When fields are bare or green; water use; heat |
| NASA GPM IMERG | Rainfall |
| NASA GRACE / GRACE-FO | Regional water-storage trend |
| NASA SRTM | Slope and erosion risk |
| NASA EONET · NASA FIRMS | Natural-event and fire alerts |
| NASA GIBS (incl. HLS 30 m, Blue Marble) | Browse maps; PDF locator map |
| JAXA GSMaP · ESA WorldCover | Heavy-rain alerts · land cover |
| FAOSTAT (area, yield, producer prices) · FAO EcoCrop · ISRIC SoilGrids | Crops each country grows and what a hectare is worth · crop ranges · soil |

Every dataset, library and tool, with licenses: [REFERENCES.md](REFERENCES.md).

## Tech stack

Python 3.13 · FastAPI · Google Earth Engine · TigerData (Postgres + TimescaleDB + PostGIS) · xAI Grok · Auth0 · React + TypeScript + Vite · MapLibre GL JS · Terra Draw · Turf · Web Push · Cloudflare Tunnel and Pages

## Repository layout

```
backend/    FastAPI app: data fetching, features, engine, AI reports, alerts, accounts, tests
frontend/   React app (mobile-first)
data/       crop traits, pest rules, country crop table, demo farms
scripts/    demo-farm precompute, storm simulation (admin), data builders, checks
```

## Run it locally

Needs Python 3.13, Node, a Google Earth Engine project and the keys listed in `.env.example` (copy it to `.env`, and `frontend/.env.example` to `frontend/.env.local`).

```bash
make setup          # Python venv + frontend packages
make migrate        # database tables (TigerData)
make load-crops     # crop climate ranges (FAO EcoCrop) and traits into the database
make dev-backend    # API on http://localhost:8000
make dev-frontend   # app on http://localhost:5173
make check          # lint, tests, data checks, frontend build
```

| Command | What it does |
|---|---|
| `make showcase` | Recompute the demo farms (with AI reports) and bundle them into the app |
| `make showcase-engine` | Re-run only the engine on the saved demo-farm data (offline, no AI reports) |
| `make tunnel` | Public HTTPS link to the running app |
| `make pages` | Deploy the static demo copy to Cloudflare Pages |
| `make simulate-storm` | Admin only: simulate a storm near a demo farm (`make clear-simulations` removes it) |
| `make regional-crops` | Rebuild the country crop table from FAOSTAT |
| `make vapid` | Create web-push keys |
| `make check-db` | Live database tests |


## AI disclosure

AI was used to help build SowSmart, and AI writes the plain-language reports inside the app (labeled in the app and PDF). Full statement: [disclosure.txt](disclosure.txt).

## Limits

Weather is a ~55 km regional average and soil moisture 9 km (shown as confidence in the details; farmers can correct any estimate). Pest alerts mean the weather favors a pest, not a confirmed outbreak. Reports in languages other than English are less reliable.

## License

MIT, see [LICENSE](LICENSE). Data credits and licenses in [REFERENCES.md](REFERENCES.md).
