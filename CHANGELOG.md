# Changelog

## [Unreleased]

## [0.4.0] - 2026-09-22

### Docs
- Update CHANGELOG.md
- Update README.md
- Update START.md
- Update THIRD_PARTY.md
- Update docs/ARCHITECTURE.md
- Update docs/CONFIGURATION.md
- Update docs/OSS_REUSE.md
- Update docs/PLANFILE.md
- Update docs/PUBLISHING.md
- Update docs/RELEASE-0.4.md
- ... and 22 more files

### Test
- Update tests/conftest.py
- Update tests/live/test_live_core.py
- Update tests/live/test_live_io.py
- Update tests/live/test_renderer_live.py
- Update tests/test_baseline_vision.py
- Update tests/test_collector_browser.py
- Update tests/test_compose.py
- Update tests/test_config.py
- Update tests/test_detectors.py
- Update tests/test_extensions.py
- ... and 78 more files

### Other
- Update .dockerignore
- Update .env.example
- Update .gitignore
- Update LICENSE
- Update MANIFEST.in
- Update Makefile
- Update RELEASE-MANIFEST.json
- Update VERSION
- Update compose.live-novnc.yaml
- Update compose.live.yaml
- ... and 82 more files


## 0.4.0 — 2026-09-22

- Consolidated source ZIP, wheel/sdist, offline build fallback and release manifest.
- Required-check plan and strict shared CLI/report/JUnit/suite gate. Single failure cannot become a pass.
- Explicit private authentication state, setup navigation, before-step evidence.
- Download event contract, safe metadata/payload policy, additional UI expectations.
- Independent bounded HTTP API runner with two-part approval for mutations.
- Optional CDP performance budgets and explicit pytest bridge.
- Packaged six-persona Clonerd profile, read-only scan/live and separated API/download/performance.
- New renderer/unit/HTTP tests; full Docker, upstream SDKs and actual Clonerd remain external validation gates.

## Historical notes



## 0.3.0 — 2026-09-22

Added continuous GUI monitoring, 92-class taxonomy, evidence-backed cause hypotheses,
read-only CSS provenance, resource-aware scheduler, bounded hot contexts, persistent
incidents/SSE dashboard, opt-in native region observation, local CV and budgeted
LiteLLM slow lane, immutable Planfile export, additive WUP integration, dedicated
Docker/noVNC live profiles and renderer/contract tests. Docker Playwright pin corrected
to the verified documentation pair 1.61.0. Existing batch, TestQL and terminal workflows
retained. This alpha does not claim complete GUI coverage or production validation.
