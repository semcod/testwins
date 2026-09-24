# PLF-004 / ticket-004 — Scroll-aware touch-target geometry

Allocated by the local Planfile SDK on 2026-09-24. One writer owns
`ticket/004-touch-target-geometry` and the matching canonical worktree/lease.

User continuation: repair remaining audit defects after UX publication.
C2004 PLF-2545/2546 already fixed the application layout and touch controls;
the remaining Testwins defect measures scroll-edge fragments as target size.

Scope: collector target geometry, TW-TARGET-SMALL assessment, rendered
regression fixtures, documentation and read-only C2004 reruns. Preserve
occlusion tests and incomplete-observation gates. Small controls, hard CSS
clipping and scroll ports too small to expose a target must remain findings.
Do not modify C2004 or resume its separate hardware investigation PLF-2503.

Canonical result: [UX strategies](../../docs/information/ux-strategies.md).
Publication retains unit/browser checks and the independent Validator path.
