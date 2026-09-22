# Architektura Testwins 0.2

```text
operator / Makefile / pojedyncze .env
  ├─ Docker SUT: kopia wybranego APP, własne zależności i środowisko
  ├─ Docker browser lab: Xvfb + Fluxbox + noVNC
  │    └─ testwins.run: CDP/Playwright → screenshot + rendered DOM → detektory
  ├─ disposable worker: testwins.task
  │    ├─ TestQL public verification SDK → shell / WWW / inne DSL
  │    ├─ Pexpect → PTY + explicit expectations
  │    └─ MSS + PyAutoGUI + OpenCV → desktop actions + templates
  ├─ controller analysis: OpenCV / lokalne YOLO / LiteLLM
  │    └─ kandydaci + przejrzany później draft TestQL; brak tools modelu
  └─ osobny publisher: Planfile TicketProposalV1 → SDK deduplication
```

Observer WWW używa tylko wyrenderowanego DOM, geometrii, screenshotów i zachowania UI.
Nie czyta źródeł aplikacji, bazy ani backend logs. Szersze zadania shell/API/desktop to
**osobno włączany zakres**; nie są opisywane jako DOM-only. Runner TestQL dostaje folder
ze scenariuszami/aplikacją i może wykonać jego kod zgodnie z zezwoleniem operatora.

Granice: backendy nie dostają kluczy LLM; provider działa na kontrolerze.
LLM nie dostaje narzędzi, a publisher nie jest dostępny w przeglądarce/workers.
Żaden wynik LLM nie staje się automatycznie potwierdzonym ticketem ani poleceniem.

DOM auditor jest specjalizowaną warstwą obok TestQL, nie forkowaniem jego silnika.
TestQL służy do wykonania zadań w swoim języku i kontraktu wynikowego, a Testwins dodaje
izolację, semantykę incomplete/validated, audyt geometrii i artefakty.

Główne moduły: `integrations/testql.py`, `tasks.py`, `task_worker.py`, `suite.py`,
`llm.py`, `drafting.py`, `cv.py`, `integrations/desktop.py`, `integrations/terminal.py`.
Zachowane warstwy: `runner.py`, `collector.js`, `detectors.py`, `proposals.py`,
`verification.py`, `events.py`, `baseline.py`, `reporting.py`.

Zadania suite są sekwencyjne i mają limity czasu. Timeout kończy grupę procesu workera;
Docker jest sprzątany. Brak runtime/dependency nie jest zielonym testem.
Macierz browser/device dotyczy audytu WWW, nie screenshotu aplikacji shell.
Etykiety `confirmed` oznaczają powtarzalne naruszenie danej reguły/kontraktu, nie dowód
przyczyny w kodzie ani kompletność całego programu.

Zmiana nazwy obejmuje dystrybucję, moduł, CLI, środowisko TW_ i prefiksy reguł TW-.
Nowe schematy mają `testwins.*`; nie dodano automatycznej migracji archiwalnych raportów
UXMatrix. Zachowaj oryginalny audytor do weryfikacji starych archiwów.
