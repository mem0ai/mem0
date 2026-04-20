.PHONY: install-dev run run-worker run-worker-once test test-unittest lint format smoke test-e2e preflight pilot-smoke pilot-scenarios quality-eval lifecycle-eval continuity-benchmark compare-eval reset-pilot snapshot-pilot restore-pilot show-pilot-snapshots inspect-memories inspect-memory-lifecycle explain-recall show-last-smoke show-last-quality-eval

PYTHON ?= python3
PORT ?= 8080

install-dev:
	$(PYTHON) -m pip install -e '.[dev]'

run:
	uvicorn app.main:app --reload --host 0.0.0.0 --port $(PORT)

run-worker:
	$(PYTHON) -m app.workers.main

run-worker-once:
	$(PYTHON) -m app.workers.main --once

test:
	$(PYTHON) -m pytest tests

test-e2e:
	$(PYTHON) -m pytest tests/e2e

preflight:
	bash scripts/openclaw_preflight.sh

pilot-smoke:
	bash scripts/openclaw_pilot_smoke.sh

pilot-scenarios:
	bash scripts/openclaw_pilot_scenarios.sh

quality-eval:
	bash scripts/openclaw_quality_eval.sh

lifecycle-eval:
	$(PYTHON) -m app.lifecycle_eval

continuity-benchmark:
	$(PYTHON) -m app.continuity_benchmark

compare-eval:
	bash scripts/compare_eval_reports.sh "$(BEFORE)" "$(AFTER)"

reset-pilot:
	bash scripts/openclaw_reset_pilot.sh

snapshot-pilot:
	bash scripts/openclaw_snapshot_pilot.sh "$(NAME)"

restore-pilot:
	bash scripts/openclaw_restore_pilot.sh "$(SNAPSHOT)"

show-pilot-snapshots:
	bash scripts/show_pilot_snapshots.sh

inspect-memories:
	bash scripts/inspect_memories.sh $(ARGS)

inspect-memory-lifecycle:
	bash scripts/inspect_memory_lifecycle.sh $(ARGS)

explain-recall:
	bash scripts/explain_recall.sh $(ARGS)

show-last-smoke:
	bash scripts/show_last_report.sh smoke

show-last-quality-eval:
	bash scripts/show_last_report.sh quality

test-unittest:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

smoke:
	$(PYTHON) -m unittest discover -s tests -p 'test_*.py' -v

migrate:
	.venv/bin/alembic upgrade head
