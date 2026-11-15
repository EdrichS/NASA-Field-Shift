# SowSmart dev commands. Run from the repo root.

PYTHON ?= /opt/homebrew/bin/python3.13
VENV   := .venv
PY     := $(VENV)/bin/python
API    ?= http://localhost:8000
WEB    ?= http://localhost:5173

.PHONY: setup dev-backend dev-frontend check check-setup check-db migrate features smoke \
	ecocrop validate-data load-crops test-email contracts showcase

# FAO EcoCrop database, via the OpenCLIM/ecocrop repo, pinned to a fixed commit
ECOCROP_URL := https://raw.githubusercontent.com/OpenCLIM/ecocrop/ea43ecd418fd1a1ea08d32c7dce64b7fae02dec4/EcoCrop_DB.csv
ECOCROP_CSV := data/raw/EcoCrop_DB.csv

# Create .venv if missing, install backend and frontend dependencies
setup:
	test -x $(PY) || $(PYTHON) -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r backend/requirements.txt
	cd frontend && npm install

# FastAPI on :8000, reloads on code changes
dev-backend:
	cd backend && ../$(VENV)/bin/uvicorn app.main:app --reload --port 8000

# Vite on :5173
dev-frontend:
	cd frontend && npm run dev

# Offline only: lint, tests, typecheck, build. No network, no paid APIs.
check:
	$(VENV)/bin/ruff check backend scripts
	$(PY) scripts/validate_data.py
	$(VENV)/bin/pytest -q
	cd frontend && npm run lint && npm run typecheck && npm run build

# Live check of every outside service (free calls only, never prints secrets)
check-setup:
	$(PY) scripts/check_setup.py

# Apply new SQL migrations to TigerData (safe to re-run: applied files are skipped)
migrate:
	cd backend && ../$(PY) -m db.migrate

# 12-month feature table for the Philippines test point: timings, table, chart, stored in TigerData
features:
	$(PY) scripts/feature_table.py

# Download the FAO EcoCrop database (once; data/raw/ is gitignored)
ecocrop: $(ECOCROP_CSV)
$(ECOCROP_CSV):
	mkdir -p data/raw
	curl -fsSL -o $(ECOCROP_CSV) $(ECOCROP_URL)

# Check the team's CSVs (crop traits, pest rules). Add STRICT=1 to also fail on TODO sources.
validate-data:
	$(PY) scripts/validate_data.py $(if $(STRICT),--strict,)

# Load EcoCrop ranges + crop traits into the crops table and pest rules into pest_rules
load-crops: $(ECOCROP_CSV)
	$(PY) scripts/load_crops.py

# Send one test alert email: make test-email TO=you@example.com
test-email:
	$(PY) scripts/send_test_email.py --to $(TO)

# Live database tests: schema, constraints, delete-my-data cascade, cache (needs DATABASE_URL)
check-db:
	$(VENV)/bin/pytest -q -m db

# Against the running servers
smoke:
	@curl -fsS $(API)/health | grep -q '"status":"ok"' \
		&& echo "✅ backend /health" || { echo "❌ backend /health at $(API)"; exit 1; }
	@curl -fsS $(WEB)/ | grep -q 'id="root"' \
		&& echo "✅ frontend serves the app" || { echo "❌ frontend at $(WEB)"; exit 1; }
	@$(MAKE) --no-print-directory check-db
	@$(PY) scripts/smoke_api.py --api $(API)

# OpenAPI schema + live request/response samples for the frontend (backend must be running)
contracts:
	$(PY) scripts/export_openapi.py
	$(PY) scripts/smoke_api.py --api $(API) --save

# Pre-compute both showcase farms with Tier 1 reports (~3 Grok calls, about $0.025).
# For the demo recording: make showcase XAI_MODEL=grok-4.7
showcase:
	$(if $(XAI_MODEL),XAI_MODEL=$(XAI_MODEL) )$(PY) scripts/precache_showcase.py
