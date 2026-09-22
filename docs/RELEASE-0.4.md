# Kontrakty i zmiany Testwins 0.4.0

## Wspólna bramka

Runner planuje każdą obowiązkową asercję przed otwarciem przeglądarki. `report.json` przechowuje `check_plan`,
`checks`, `cell_plan`, `cells`, pokrycie i wynik `gate`. Brak kroku, duplikat, nieplanowany wynik, błąd wykonania
lub brak wymaganego dowodu oznacza niekompletność. Pojedyncze `failed` oznacza niepowodzenie niezależnie od
liczby powtórzeń i statusu kandydata w analizie GUI. Niekompletność ma pierwszeństwo przed kodem niepowodzenia.

```bash
testwins gate artifacts/run-id
testwins verify artifacts/run-id
```

Gate na katalogu najpierw sprawdza integralność artefaktów. Gate na samym `report.json` może sprawdzić wyłącznie
strukturę i wynik, nie obecność zewnętrznych plików. `verify` jest kontrolą hashy, nie kontrolą zachowania aplikacji.
Stare raporty bez planu kroków nie są automatycznie traktowane jako zaliczone w 0.4.

## Sesje i przygotowanie stanu

Sesja jest jawnym wejściem. Nie pobieramy automatycznie profilu ani cookies z hostowej przeglądarki.
Plik musi być regularny, niesymlinkowany, do 5 MB, na POSIX z uprawnieniami 0600. Originy i domeny cookies
muszą należeć do allowlisty konfiguracji. Oddzielne konta = oddzielne pliki i nazwane sesje.

```yaml
base_url: http://127.0.0.1:8080
allowed_origins: []
sessions:
  customer:
    storage_state: .auth/customer.storage-state.json
default_session: customer
journeys:
  - id: account
    path: /billing
    setup_path: /account
    session: customer
    steps:
      - id: invoice-list
        action: assert
        expect:
          kind: visible
          selector: '#invoice-list'
```

Fragment należy połączyć z konfiguracją utworzoną przez `testwins init`; `setup_path` i `path` są względne
wobec tego samego originu. Przygotowanie i właściwy widok działają w tym samym nowym kontekście. Kontekst nie
przecieka między scenami. Każdy wymagany warunek dotyczący przygotowania należy zapisać jako jawny krok —
`setup_path` jest nawigacją rozgrzewającą, a nie deklaracją sukcesu biznesowego.

```bash
testwins auth-save --config audit.yaml \
  --output .auth/customer.storage-state.json \
  --ready-selector '#signed-in-user'
```

Polecenie otwiera osobną przeglądarkę w trybie graficznym. Operator loguje się lokalnie; zapis następuje po
widoczności jawnego selektora. Nie ma tu uniwersalnego generatora danych logowania. Plik nie jest nadpisywany.
Ścieżki są liczone względem YAML. Nie publikuj plików sesji i nie przekazuj ich modelowi LLM.
Zapisywana kopia konfiguracji redaguje ścieżki, ale screenshot/DOM nadal może zawierać dane konta — stosuj maski,
izolowane dane i odpowiednią retencję. W Dockerze `AUTH_DIR=/lokalny/prywatny/folder` montuje pliki tylko do
labu read-only jako `/auth`; konfiguracja wskazuje wtedy `/auth/customer.storage-state.json`. Pliki nie trafiają do SUT.

## Dodatkowe akcje i oczekiwania

Akcje: istniejące click/fill/press/hover/check/uncheck/select/assert/wait oraz `goto`, `scroll`, `download`.
Mutujące akcje wymagają `allow_mutation: true`. `goto` musi być same-origin i mieć oczekiwanie.
Oczekiwania: visible/hidden/text/count/url/changed oraz contains_text/count_min/enabled/disabled/checked/unchecked/
focused/value/attribute/download. `attribute` ma `name` i `value`; count_min jest ograniczonym czasowo oczekiwaniem,
a nie pojedynczym pomiarem przed zakończeniem renderowania.

```yaml
journeys:
  - id: search
    path: /
    steps:
      - id: open
        action: press
        selector: body
        value: Control+k
        allow_mutation: true
        expect: {kind: visible, selector: '#palette'}
      - id: query
        action: fill
        selector: '#palette input'
        value: taskand
        allow_mutation: true
        expect: {kind: contains_text, selector: '#palette', value: taskand}
```

Przed krokiem zapisuje się dowód (`capture.before_steps: true`), a po nim rezultat. Nie klikamy wszystkich
przycisków ani nie uznajemy samej obecności kontrolki za wykonanie jej funkcji.

## Download

```yaml
downloads:
  enabled: true
  max_bytes: 10485760
  retain: false
journeys:
  - id: invoice
    path: /invoices
    steps:
      - id: download-invoice
        action: download
        selector: '#download-pdf'
        allow_mutation: true
        expect:
          kind: download
          filename_regex: '.*\.pdf'
          min_bytes: 5
          max_bytes: 10485760
          starts_with_hex: '255044462d'
```

Krok czeka na prawdziwe zdarzenie pobrania. Sprawdza rozmiar, nazwę, opcjonalny prefix i `sha256`.
Prefix `%PDF-` nie dowodzi poprawności danych faktury ani kompletności PDF. Podane oczekiwania są kontraktem,
nie ekstrakcją semantyczną dokumentu. Domyślnie zapisuje się tylko metadane z zredagowaną nazwą i hash.
`retain: true` zachowuje plik pod kontrolowaną nazwą `payload.bin`, nigdy pod ścieżką narzuconą przez serwer.
**Limit bytes sprawdzany jest po zakończeniu pobrania**, nie ogranicza transferu w przeglądarce ani jego zapisu
przejściowego. Twardą ochronę dysku/pamięci realizuj limitem kontenera/tmpfs; używaj zaufanego środowiska testowego.

## Osobne kontrakty HTTP

```yaml
schema: testwins.api/v1
id: menu
base_url: http://127.0.0.1:8080
requests:
  - id: menu-readable
    method: GET
    path: /v1/menu
    expect:
      status: 200
      json_min_length: {'/searchIndex': 15}
      json_any:
        - {path: '/searchIndex', field: endpointId, contains: taskand}
```

```bash
testwins api --config api.yaml --output artifacts/api
# Nie wykonuj poniższego bez przeglądu środowiska i skutków:
testwins api --config api/mutations.review.yaml --output artifacts/api --approve-mutations
```

POST/PUT/PATCH/DELETE wymagają jednocześnie `allow_mutation: true` w żądaniu i `--approve-mutations`.
Domyślna suite nie udziela tej zgody. Same-origin, bez automatycznych przekierowań i bez odziedziczonego proxy.
Opcjonalne `header_env` mapuje nazwę nagłówka do zmiennej środowiskowej, nie sekretu w YAML. Domyślnie limit
odpowiedzi 1 MB, konfigurowalny do 10 MB. Raport nie zachowuje nagłówków ani body, ale hash/rozmiar też należy
traktować jako metadane testowe, nie dowód anonimizacji. Każde żądanie ma wymagany jawny status.

API wykonuje się raz w suite, a nie raz na urządzenie. Nie jest częścią skanera ograniczonego do DOM/obrazów.

## Metryki CDP

```yaml
performance:
  enabled: true
  required: true
  budgets:
    JSHeapUsedSize: 104857600
```

To jawne maksima wybranych liczników Chromium. Brak wymaganej metryki daje niekompletność, przekroczenie —
niepowodzenie. Liczniki czasowe/counters są kumulatywne, nie automatycznymi deltami działania i nie Core Web Vitals.
Konfigurację stosuj w oddzielnym zakresie Chromium. Firefox/WebKit nie dostają fikcyjnych pomiarów CDP.

## pytest i istniejące repozytorium

```python
# tests/test_gui.py
from pathlib import Path

def test_portal(testwins_run):
    report = testwins_run(Path('testwins/audit.yaml'))
    assert report['gate']['exit_code'] == 0
```

```bash
pytest -p testwins.pytest_plugin tests/test_gui.py
```

Plugin jest ładowany jawnie. `testwins_assert_report(path)` pozwala bramkować istniejący raport; dla katalogu
sprawdza też hashe. Nie rejestruje niejawnych hooków skanujących i nie zastępuje specjalistycznych testów API.

## Weryfikacja obowiązkowa na docelowym środowisku

```bash
make test
make test-browser
make install-testql-source TESTQL_REF=PRZEJRZANY_COMMIT
make test-final
make landing-check MATRIX=engines
```

Dwa testy integracyjne w aktualnym środowisku utknęły na ograniczeniach zarządzanej przeglądarki: pełne storage_state
z localStorage oraz download. Pozostają aktywne, nie są oznaczone jako poprawne. Testy renderer-only można uruchomić
`pytest -m 'browser and not integration'`; nie należy mylić tego podzbioru z pełnym testem instalacji.

## Źródła kontraktów zewnętrznych

Przygotowanie: 2026-09-22. Dokumentacja Playwright: [auth](https://playwright.dev/python/docs/auth),
[download](https://playwright.dev/python/docs/downloads), [Docker](https://playwright.dev/python/docs/docker).
Weryfikacja API zależności nie zastępuje lokalnego testu po przypięciu konkretnej wersji. Pełne ograniczenia: `verification/STATUS.md`.
