# PLF-008 / ticket-008 — C2004 and DisplayNet validation

Allocated by the Planfile SDK on 2026-09-24 for the user's explicit request
to run tests against maskservice/c2004 and DisplayNet.

One writer owns this Testwins report worktree and its fenced lease. The
C2004 checkout remains read-only; PLF-2503/2537 hardware work and foreign
changes retain their owners. No hardware commands, restart or deployment.

Scope: current endpoint observations, existing C2004 responsive/iframe
regressions, bounded HTTP reads, and Testwins UX, keyboard and four-route
audits against local and DisplayNet frontends. Preserve failures, missing
coverage and exact evidence manifests. Do not infer runtime source identity
from the local application checkout.

Canonical result: [C2004 / DisplayNet tests](../../docs/analysis/c2004-displaynet-tests.md).
Feature requests PLF-006 (intentional overlays) and PLF-007 (frame interiors)
remain separate queued work. Publication retains the independent Validator.
