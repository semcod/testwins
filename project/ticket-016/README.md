# PLF-016 — Offer content & visual duplication analysis + Chromium launcher resolution

## Scope
1. Extend `testwins/collector.js` to capture full-document rendered `content_blocks` (distinct visible DOM elements outside shared landmarks `header`, `nav`, `footer`, `select`, `option`) and `graphics` (`svg`, `img`, `canvas`, `[data-visual]` with normalized geometry/source signatures) without conflating multi-line `Range.getClientRects()` fragments of a single element.
2. Add `TW-TEXT-DUPLICATE` and `TW-GRAPHIC-DUPLICATE` rules in `testwins/detectors.py`, `testwins/config.py`, `testwins/live/diagnosis.py`, and `testwins/live/scanner.py` to detect duplicated text copy and duplicated graphical forms on offer/product pages.
3. Fix `testwins/browser.py` Chromium binary resolution to honor `CHROMIUM_EXECUTABLE` and prefer native `/usr/bin/google-chrome` over Snap-confined `/snap/bin/chromium` so CDP startup with `/tmp` `user-data-dir` does not fail with `incomplete`.
4. Add unit and browser regression tests in `tests/test_detectors.py` and `tests/test_collector_browser.py`.
