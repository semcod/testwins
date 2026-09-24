# PLF-001 / ticket-001 — UX strategies and evidence-bound repair guidance

Allocated by the local Planfile SDK on 2026-09-23 as **PLF-001**. The worktree
layout alias is `ticket-001`, branch `ticket/001-ux-strategies`.

Accepted user scope: application-specific UX strategies, simulated habits,
functional/visual/information/feedback/motion contracts, and repair proposals
through subactor/subllm. One implementation writer in the dedicated worktree.

Acceptance: explicit strategy selection; measured input-to-outcome observations;
required contracts fail on violations and missing evidence; unchanged feedback
cannot acknowledge a new action; model advice stays bound to report evidence;
existing configurations remain compatible; real browser regressions and package
build succeed. No source-file guesses or automatic execution of model output.

Canonical result: [UX strategies](../../docs/information/ux-strategies.md).
Operational lease, fencing and continuation checkpoints live in the primary
checkout's ignored `.subactor` state. Planfile/GitHub synchronization is not
configured for this repository. Publication requires independent Validator
coverage; no direct merge is authorized by this ticket.
