PYTHON ?= python3
BASE_URL ?= http://127.0.0.1:8891
MATRIX ?= chromium

.PHONY: help configure validate scan watch capacity journey-example
help:
	@printf '%s\n' 'make configure BASE_URL=http://127.0.0.1:8891' 'make validate' 'make scan MATRIX=chromium' 'make watch' 'make capacity' 'make journey-example (reviewed demo environment only)'
configure:
	$(PYTHON) tools/manage.py configure --url "$(BASE_URL)"
validate:
	$(PYTHON) tools/manage.py validate
scan:
	$(PYTHON) tools/manage.py scan --matrix "$(MATRIX)"
watch:
	$(PYTHON) -m testwins watch --config testwins.watch.yaml --root . --serve
capacity:
	$(PYTHON) -m testwins capacity --config testwins.watch.yaml --seconds-per-cell 2 --workers 2 --interval 120
journey-example:
	$(PYTHON) -m testwins run --config journeys/developer.desktop.yaml --output artifacts/journeys

.PHONY: personas api performance download-review
personas:
	$(PYTHON) -m testwins suite --file personas.suite.yaml --output artifacts/personas
api:
	$(PYTHON) -m testwins api --config api/readonly.yaml --output artifacts/api
performance:
	$(PYTHON) -m testwins run --config audit/performance.yaml --output artifacts/performance
download-review:
	$(PYTHON) -m testwins run --config journeys/download.review.yaml --output artifacts/downloads
