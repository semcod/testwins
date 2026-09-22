# Wykonawcy i kontrakty zadań

## Trzy zakresy

`backend: testql` uruchamia publiczny SDK TestQL dla plików `.oql` lub innych formatów
rozpoznawanych przez zainstalowany TestQL. `backend: terminal` korzysta z Pexpect/PTY.
`backend: desktop` robi screenshoty MSS, dopasowania OpenCV i jawne wejście PyAutoGUI.
Są to uzupełnienia, a nie twierdzenie, że Python może bez konfiguracji testować dowolny OS.

```yaml
schema: testwins.task/v1
id: smoke-cli
backend: testql
files: [scenarios/shell.oql]
timeout_seconds: 120
step_timeout_ms: 10000
dry_run: false
```

Przykładowy TestQL:

```text
SHELL "python -m testwins --version" 10000
ASSERT_EXIT_CODE 0
ASSERT_STDOUT_CONTAINS "testwins 0.2.0"
```

Adapter tworzy `VerificationRequest(file_specs=..., project_dir=..., url=..., dry_run=...,
quiet=True, timeout=..., allow_semantic_events=False)` i wywołuje `run_verification`.
Oryginalne request/result/hash są zachowane. Walidowany jest publiczny schema SDK,
zgodność z requestem, hashe, liczba plików i liczniki. Wyjście CLI nie jest kontraktem.
Źródło: https://github.com/autogrammar/testql/blob/main/testql/verification.py

Statusy: `passed` = wykonany scenariusz; `failed` = niespełnione sprawdzenie;
`incomplete` = brak zależności, timeout, pominięte/niewykonane kroki lub brak scenariuszy;
`validated` = sprawdzenie dry-run bez wykonania. Kody procesu: 0/1/2; `validated` ma kod0,
więc bramka CI wymagająca wykonania musi również sprawdzić status JSON. Suite z mieszaniną
wykonanych i tylko zwalidowanych kroków jest niekompletna.

## Interaktywny terminal

```yaml
schema: testwins.task/v1
id: prompt
backend: terminal
command: python
args: [examples/terminal/prompt.py]
max_output_bytes: 262144
expected_exit_code: 0
steps:
  - {action: expect, value: 'Name: '}
  - {action: send, value: Testwins}
  - {action: expect, value: 'Hello, Testwins!'}
  - {action: eof}
```

Nie ma implicit shell; command i argv przekazywane są osobno. `expect` używa regex.
Wymagaj `eof`, aby sprawdzić kod wyjścia procesu; bez niego wynik dotyczy tylko
sprawdzonych interakcji. Limit odczytu obejmuje także niedopasowane dane. Zapisywane są
liczniki/statusy, nie pełny transcript. POSIX PTY wymaga systemu Unix/Linux.
Scenariusze regex i uruchamiany kod są zaufaną treścią operatora, nie piaskownicą języka.

## GUI desktop

```yaml
schema: testwins.task/v1
id: calculator
backend: desktop
command: xcalc
steps:
  - {action: wait, seconds: 1}
  - {action: assert_template, template: fixtures/display.png, threshold: 0.94}
  - {action: click_template, template: fixtures/button-7.png, threshold: 0.94}
  - {action: assert_template, template: fixtures/display-7.png, threshold: 0.94}
```

To schemat konfiguracji: **własne wzorce należy dostarczyć**, dopasowane do motywu,
DPI i aplikacji. Paczka nie udaje, że zawiera te konkretne obrazy. `desktop-demo` jest
wyłącznie smoke uruchomienia xmessage, screenshotu i klawisza — nie ma asercji poprawności.
Akcje: capture/click/click_template/assert_template/press/write/wait. Wpisywanie przez
PyAutoGUI nie gwarantuje dowolnego Unicode/układu klawiatury. Worker ma świeży Xvfb,
bez hostowego socketu X11. Własne zależności zainstaluj w obrazie potomnym:

```dockerfile
FROM testwins-worker:local
USER root
RUN apt-get update && apt-get install -y x11-apps && rm -rf /var/lib/apt/lists/*
USER 1000:1000
```

Domyślny ekran jest jeden, 1440×1000. Nie deklarujemy obsługi wielomonitorowych
współrzędnych pulpitu, Wayland bez uprawnień ani uruchamiania natywnego Windows/iOS w Linux Docker.
Dla takich celów rozważ osobnego workera/VM i właściwy driver Appium/Airtest; nie są
one wbudowanymi backendami tej wersji.

## Polityka wykonania

`testwins task --file ... --project ...` domyślnie wymaga obrazu z `make worker-build`.
`--network none` jest domyślne. `--network projekt_audit` dołącza do określonej sieci SUT;
adres `localhost` wewnątrz workera nie wskazuje hosta. `--trusted-local` jest jawnym
zezwoleniem na uruchamianie własnego kodu na hoście, z jego uprawnieniami.
Kopiowana jest ograniczona zawartość folderu (do 512MiB i 50000 plików), bez wzorców sekretów.
Nie jest analizowana semantyka źródeł. Worker może wykonać kod z tej kopii zgodnie ze scenariuszem.

`testwins suite --file example.suite.yaml` łączy zadania i audyty WWW kolejno, z raportem
odnośników do wyników. Nie prowadzi nieskończonej pętli ani samodzielnego naprawiania.
Każdy krok ma jawny zakres. Raporty są dowodami z testu, nie instrukcjami dla LLM.
