.PHONY: help setup data check test test-ui lint format web serve experiments e1 e2 e3 e4 e5 results timelines screenshots smoke clean

help: ## List targets
	@grep -E '^[a-z0-9-]+:.*##' $(MAKEFILE_LIST) | awk -F':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

setup: ## Install Python (uv) and console (npm) dependencies
	uv sync --locked
	npm --prefix web ci

data: ## Download the ExtraSensory features archive (225 MB) and verify its SHA-256 (data/raw/, not committed)
	uv run behavlab fetch

check: data ## Data card: counts, sensor coverage, timezone check, anomaly prevalence (docs/generated/data_check.json)
	uv run behavlab check

experiments: data ## THE one command: data card, E1-E5 on all 60 people, results, timelines
	uv run behavlab check
	OMP_NUM_THREADS=1 uv run behavlab experiment all
	uv run behavlab results
	uv run behavlab timelines

e1: data ## E1 modality ablation (A, B, C, + time, + location) x 3 detectors
	OMP_NUM_THREADS=1 uv run behavlab experiment e1
e2: ## E2 detection by anomaly kind (reads E1)
	uv run behavlab experiment e2
e3: data ## E3 false-positive error analysis
	OMP_NUM_THREADS=1 uv run behavlab experiment e3
e4: data ## E4 alarm threshold and persistence rule against latency
	OMP_NUM_THREADS=1 uv run behavlab experiment e4
e5: data ## E5 robustness of the ablation's answer
	OMP_NUM_THREADS=1 uv run behavlab experiment e5

results: ## Render docs/generated/results.md from results/*/LATEST
	uv run behavlab results

timelines: data ## Per-minute timelines of the primary model for the console (var/timelines, not committed)
	OMP_NUM_THREADS=1 uv run behavlab timelines

smoke: data ## E1-E5 on 6 people with smoke configs into results/scratch (checks the pipeline; not a result)
	BEHAVLAB_USERS=6 uv run behavlab experiment all --configs configs/smoke --results results/scratch

test: ## Unit and API tests (synthetic people; the data test runs when the archive is present)
	uv run pytest

test-ui: web ## Browser, keyboard and axe accessibility tests (needs Chromium and the data)
	uv run pytest -m ui

lint: ## Ruff, mypy, ESLint and TypeScript checks
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy src tests scripts
	npm --prefix web run lint
	npm --prefix web run typecheck

format: ## Auto-format Python
	uv run ruff format .
	uv run ruff check --fix .

web: ## Build the console into web/dist
	npm --prefix web run build

serve: web ## Serve the console and API on http://127.0.0.1:8000 (reads .env if present)
	set -a; [ -f .env ] && . ./.env; set +a; uv run behavlab serve

screenshots: web ## Capture docs/screenshots from the running console (needs timelines and results)
	uv run python scripts/screenshots.py

clean: ## Remove build output, caches and smoke runs (keeps data/, results/ and var/)
	rm -rf web/dist results/scratch .pytest_cache .mypy_cache .ruff_cache
