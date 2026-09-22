PYTHON ?= python3
# Variables are passed as environment data, never interpolated into a host shell command.
export AUTH_DIR
export APP APP_IMAGE APP_INSTALL APP_COMMAND APP_PORT CONFIG MATRIX INSTANCE
export VNC_PORT REPORT_PORT APP_ALLOW_NETWORK SUT_ENV_FILE STARTUP_TIMEOUT COMPOSE_OVERRIDE
export LAB_UID LAB_GID LAB_MEMORY APP_MEMORY LAB_CPUS APP_CPUS
export PLANFILE_PROJECT PLANFILE_REF APPLY READY INCLUDE_CANDIDATES TICKET_LIMIT TICKET_OFFSET
.DEFAULT_GOAL := help
.PHONY: help demo up check audit down logs status report doctor prepare publish vnc-password install test smoke smoke-offline conformance vision
help:
	@echo 'make bootstrap | test | test-browser | clonerd-init | clonerd-check | package-final'
	@echo 'make live-novnc | live-docker — continuous GUI monitoring + local dashboard'
	@echo 'make live-watch WATCH_CONFIG=/path PROJECT_ROOT=/repo | wup-integrate WUP_ROOT=/repo [APPLY=1]'
	@echo 'make landing-check — standalone landing Docker + Testwins CDP matrix + TestQL scenarios'
	@echo 'make scenario-demo | terminal-demo | desktop-demo — disposable worker'
	@echo 'make install [EXTRAS=llm,cv,terminal,dev] | build-dist | release-check'
	@echo 'make demo [MATRIX=cdp|engines|chromium] — build isolated seeded demo and audit it'
	@echo 'make up APP=/path APP_IMAGE=node:22-bookworm-slim APP_INSTALL="npm ci" APP_COMMAND="__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS=sut npm run dev -- --host 0.0.0.0 --port 8080"'
	@echo 'make check APP=/path APP_COMMAND=... — build, start and audit your own application'
	@echo 'make audit | report | logs | status | vnc-password | down'
	@echo 'make publish PLANFILE_PROJECT=/path [APPLY=1] [PLANFILE_REF=reviewed_commit]'
	@echo 'make install | test | smoke | conformance LOGS_ROOT=/path RUN=/path'
demo up check audit down logs status report doctor prepare publish vnc-password:
	$(PYTHON) tools/lab.py $@
install:
	$(PYTHON) tools/manage.py install
test:
	$(PYTHON) -m pytest -q -m 'not browser'
smoke:
	$(PYTHON) tools/smoke.py
smoke-offline:
	$(PYTHON) tools/smoke.py --offline-fixture
# RUN and LOGS_ROOT are read from the environment, not shell-expanded.
export RUN LOGS_ROOT
conformance:
	$(PYTHON) tools/standards.py
vision:
	$(PYTHON) tools/vision.py

# Testwins 0.2 workflow. Python CLI extras install into the active virtualenv.
export TESTQL_REF
EXTRAS ?= live,terminal,dev
export EXTRAS
.PHONY: landing-up landing-down landing-check worker-build scenario-demo terminal-demo desktop-demo install-testql-source build-dist release-check
landing-up:
	$(PYTHON) tools/landing.py up
landing-check:
	$(PYTHON) tools/landing.py check
landing-down:
	$(PYTHON) tools/landing.py down
worker-build:
	$(PYTHON) tools/manage.py worker-build
scenario-demo: worker-build
	$(PYTHON) -m testwins task --file scenarios/shell.task.yaml --project .
terminal-demo: worker-build
	$(PYTHON) -m testwins task --file scenarios/terminal.task.yaml --project .
desktop-demo: worker-build
	$(PYTHON) -m testwins task --file scenarios/desktop.task.yaml --project .
install-testql-source:
	$(PYTHON) tools/manage.py install-testql-source
build-dist:
	$(PYTHON) tools/manage.py build
release-check:
	$(PYTHON) -m twine check dist/*.whl dist/*.tar.gz

# Testwins 0.3 live GUI monitoring. No external model enabled by default.
export WATCH_CONFIG PROJECT_ROOT LIVE_OUTPUT WUP_ROOT
.PHONY: live-install live-watch live-once live-landing live-docker live-docker-down wup-integrate live-test
live-install live-watch live-once live-landing live-docker live-docker-down wup-integrate:
	$(PYTHON) tools/live_manage.py $@
live-test:
	$(PYTHON) -m pytest -q tests/live

.PHONY: live-novnc live-novnc-down
live-novnc live-novnc-down:
	$(PYTHON) tools/live_manage.py $@

# Consolidated 0.4 release and Clonerd profile. Values are argv/env data, not shell code.
export WORKSPACE CLONERD_URL
.PHONY: bootstrap test-browser test-final clonerd-init clonerd-check package-final
bootstrap:
	$(PYTHON) tools/release.py bootstrap
test-browser:
	$(PYTHON) -m pytest -q -m browser
test-final:
	$(PYTHON) tools/release.py check
clonerd-init clonerd-check package-final:
	$(PYTHON) tools/release.py $@
