# PLF-012 — Visually empty CSS clip paths

C2004's accessible runtime probe keeps a live announcement inside
`clip-path: inset(50%)`. DOM Range rectangles remain nonempty although no
text is painted, causing repeated false TW-TEXT-CLIPPED findings.

Recognize provably empty percentage inset shapes on elements and ancestors,
including shadow hosts. Retain node/style evidence, exclude unpainted visual
content, and block completeness when focused content remains fully clipped.
Partially clipped and unsupported shapes retain the existing checks; no
selector, class-name or ARIA-role suppression.

Regression coverage: real rendered positive/negative cases and a reporting
check for the focused-control gap. Required unit/browser CI and independent
Validator approval precede merge. C2004 PLF-2556 resumes source-bound audits
and publication after this dependency; production deployment is separate.
