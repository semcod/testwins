# ticket-017 — Collector scrollable direct-text, modal/inert isolation, stability surfaces, and HiDPI frame screenshots

## Goal
Fix false-positive `TW-TEXT-CLIPPED` on direct text inside scrollable containers (`B12`), false-positive `TW-TEXT-OVERLAP` and `TW-OVERLAY-CONTRACT` on full-screen `role="dialog"` / `aria-modal="true"` overlays over `[inert]` backgrounds (`B05`), include `content_blocks` and `graphics` in `assess_stability` (`B07`), and unify `ux_probe.js` Shadow DOM / `innerText` measurement plus CSS-scaled `FrameSurface.screenshot()` (`B11`).

## Acceptance Criteria
1. Direct text inside `<pre style="overflow-y: auto">` nested in an `overflow: hidden` pane does not trigger false `TW-TEXT-CLIPPED`.
2. Full-screen `role="dialog"` / `aria-modal="true"` overlays over `[inert]` backgrounds pass `TW-OVERLAY-CONTRACT` and do not emit cross-layer `TW-TEXT-OVERLAP`.
3. `assess_stability` tracks `content_blocks` and `graphics` geometry and content signatures.
4. `ux_probe.js` traverses open `ShadowRoot`s and measures `innerText` consistently; `FrameSurface.screenshot()` defaults to `scale="css"`.
