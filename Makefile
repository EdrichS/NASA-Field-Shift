# SowSmart dev commands. Run from the repo root.

PYTHON ?= /opt/homebrew/bin/python3.13
VENV   := .venv
PY     := $(VENV)/bin/python
API    ?= http://localhost:8000
WEB    ?= http://localhost:5173

.PHONY: setup dev-backend dev-frontend check check-setup check-db migrate smoke

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
	$(VENV)/bin/pytest -q
	cd frontend && npm run lint && npm run typecheck && npm run build

# Live check of every outside service (free calls only, never prints secrets)
check-setup:
	$(PY) scripts/check_setup.py

# Apply new SQL migrations to TigerData (safe to re-run: applied files are skipped)
migrate:
	cd backend && ../$(PY) -m db.migrate

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
