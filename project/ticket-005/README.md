# PLF-005 / ticket-005 — Observation stability and coherent retries

Allocated by the Planfile SDK on 2026-09-24. One writer owns
`ticket/005-observation-stability` and its canonical worktree/lease.

User continuation: implement the recommendations and test them. PLF-004 is
already merged. A read-only C2004 probe reproduced an unstable observation
where only `#bottom-time` text changed; all collected geometry was identical.

Scope: distinguish geometry, detector state and content changes; preserve
real movement/clipping/occlusion detection; bind screenshot retries to the
latest DOM and masks; apply the same assessment to batch and live scans.
Include unit/rendered regressions, C2004 read-only reruns and documentation.
Frame interiors and intentional popup coverage remain separate future work.
Preserve unrelated primary-checkout changes and C2004 hardware work.

Canonical result: [UX strategies](../../docs/information/ux-strategies.md).
Publication requires unit/browser checks and independent Validator approval.
