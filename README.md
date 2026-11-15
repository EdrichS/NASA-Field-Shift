# SowSmart

**Compare crop rotations for your field with NASA satellite data.** Built for the NASA Space Apps Challenge 2026, challenge *"Adapting Farms with NASA Data"*.

Point at a field, check what the satellites see, answer up to five questions (each accepts "I don't know"), and compare your current rotation with three alternatives on a 12-month calendar: fill the bare window, break the pest cycle, or save water. Every option explains why, shows its evidence, benefits, information gaps and risks, and lists questions for a local expert, in plain language and in up to two languages, with a printable PDF. Signed-in farmers get alerts for storms, fires, heavy rain, dry soil and pest-favoring weather near their saved fields.

> SowSmart supports farmer judgment and local agricultural expertise. It never replaces them.

- **Demo deck:** [link]
- **Try the demo farms:** [Cloudflare Pages link] (works without our server; open `#/demo/tagum-rice` or `#/demo/iowa-corn-soybean`)
- **Project page and details:** `docs/PROJECT_PAGE.md`; every dataset, library and tool: [`REFERENCES.md`](REFERENCES.md)

## How it works

1. **NASA data, per field:** NASA POWER weather and 30-year normals, SMAP soil moisture, MODIS greenness, water use and land-surface temperature, GPM IMERG rain, GRACE/GRACE-FO water storage and SRTM slope are reduced over the field (Google Earth Engine), plus SoilGrids soil and ESA WorldCover land cover. Every value keeps its dataset, resolution and period.
2. **The engine decides:** deterministic Python filters crops with FAO EcoCrop ranges, builds three alternatives and scores water, soil building, erosion, pest cycle, weather risk, income and labor, weighted by the farmer's goals. The farmer's corrections to the satellite cards replace the estimates.
3. **AI only explains:** Grok (xAI) turns the engine's results into a plain-language report per language. Every number it writes is checked against the engine's output; the ranking never changes.
4. **Alerts:** NASA EONET events are matched with PostGIS against every saved field; NASA FIRMS fires, JAXA GSMaP heavy rain, SMAP dry soil and cited pest-weather rules are checked per field. Delivery: in the app, by email, and as web push.

## Stack

FastAPI (Python 3.13) · Google Earth Engine · TigerData (Postgres + TimescaleDB + PostGIS) · xAI Grok · Auth0 · React + TypeScript + Vite · MapLibre GL JS + Terra Draw + Turf · Web Push · Cloudflare Tunnel and Pages.

## Run it locally

Needs Python 3.13, Node, a Google Earth Engine project, and the keys listed in `.env.example` (copy it to `.env`; `frontend/.env.example` to `frontend/.env.local`).

```bash
make setup          # venv + backend and frontend dependencies
make migrate        # database tables (TigerData)
make dev-backend    # API on http://localhost:8000
make dev-frontend   # app on http://localhost:5173 (forwards /api to the backend)
make check          # lint, tests, data validation, frontend build
```

Other targets: `make showcase` (pre-compute the demo farms), `make vapid` (web-push keys), `make tunnel` (public HTTPS link), `make pages` (static copy on Cloudflare Pages), `make check-db` (live database tests).

## Use of Super Intelligence (SI) / AI disclosure

- **Code and data:** much of this repository's code, tests, documentation and data-preparation scripts was written with **Claude Code (Anthropic)**, directed and reviewed by the team. The crop-trait and pest-rule tables in `data/` were compiled with its help from cited sources (each row lists its source). The idea and product decisions are the team's.
- **In the product:** reports are written by **Grok (xAI)** from the engine's results and are labeled "Written by AI" in the app and the PDF; the AI-suggested idea is labeled as not scored.
- **Images:** no AI-generated images or video. No NASA logos or branding.

## Data credits

NASA POWER, SMAP, MODIS, GPM IMERG, GRACE/GRACE-FO, SRTM, EONET, FIRMS and GIBS (NASA); JAXA GSMaP (JAXA); ESA WorldCover (ESA, CC BY 4.0); SoilGrids (ISRIC, CC BY 4.0); FAO EcoCrop and FAO-56 (FAO); basemaps © Esri. Details and licenses in [`REFERENCES.md`](REFERENCES.md).

## License

MIT, see [LICENSE](LICENSE).
