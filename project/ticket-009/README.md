# PLF-009 / ticket-009 — Auth form standards and credential manager heuristics

Allocated for detecting authentication form standards (TW-AUTH-FORM-*)
preventing browser credential managers from prompting to save passwords.

Scope:
- testwins/collector.js: extract inputType, autocomplete, and formDetails (hasForm, method, action, selector)
- testwins/detectors.py: implement TW-AUTH-FORM-NO-PARENT, TW-AUTH-FORM-METHOD, TW-AUTH-FORM-ACTION, and TW-AUTH-FORM-AUTOCOMPLETE
- testwins/live/scanner.py & catalog.json: register rules in BASE_RULES and forms catalog
- testwins/resources/clonerd/journeys/: add auth login journey for clonerd
- tests/test_detectors.py: regression and conformance unit tests
