# Konfiguracja

Plik YAML jest własnością operatora. Strona ani odpowiedź LLM nie mogą go modyfikować. Nieznane pola są odrzucane. `python -m testwins validate --config ...` sprawdza konfigurację przed audytem.

## Uruchamianie aplikacji

| Zmienna hosta | Znaczenie |
|---|---|
| `APP` | Folder aplikacji; ścieżki ze spacjami działają po zacytowaniu |
| `APP_IMAGE` | Jawny obraz bazowy zawierający runtime i potrzebne pakiety systemowe |
| `APP_INSTALL` | Opcjonalna, zaufana komenda instalacyjna podczas budowania obrazu |
| `APP_COMMAND` | Komenda startu procesu SUT; powinna słuchać na 0.0.0.0 |
| `APP_PORT` | Port wewnętrzny usługi, domyślnie 8080 |
| `CONFIG` | Plik YAML audytu, kopiowany do kontrolowanego katalogu konfiguracji |
| `INSTANCE` | Niezależne środowisko, obrazy SUT, stan Compose i artefakty |
| `MATRIX` | `cdp`, `engines` albo `chromium` |
| `APP_ALLOW_NETWORK` | Domyślnie 0; wartość 1 wyłącza izolację egress przez `internal` |
| `SUT_ENV_FILE` | Opcjonalny osobny plik wyłącznie testowych zmiennych SUT |
| `COMPOSE_OVERRIDE` | Jawny, zaufany plik rozszerzający Compose, np. o bazę danych |
| `VNC_PORT`, `REPORT_PORT` | Porty hosta dostępne wyłącznie przez 127.0.0.1 |
| `LAB_UID`, `LAB_GID` | Dodatnie identyfikatory użytkownika kontenerów |
| `APP_MEMORY`, `LAB_MEMORY` | Domyślne limity 2g i 6g |
| `APP_CPUS`, `LAB_CPUS` | Domyślne limity 2 i 4 CPU |
| `STARTUP_TIMEOUT` | Limit oczekiwania na port SUT; domyślnie 120 s |

Dane można podawać jako parametry Make lub zapisać w `.env`. Parser `.env` nie wykonuje substytucji `$()` i nie jest shellem. Nie wspiera wieloliniowych wartości ani interpolacji zmiennych; używaj pojedynczych, kompletnych wartości. Istniejące niepuste zmienne procesu mają pierwszeństwo.

Nie jest montowany folder hosta jako zapisywalny volume SUT. Kopia do budowania pomija `.git`, `.planfile`, `.env*`, typowe katalogi poświadczeń, pliki kluczy oraz cache zależności. Symlinki w projekcie są odrzucane, aby nie wciągnąć plików spoza zakresu. Granica domyślna wynosi 512 MiB i 50 000 plików. To filtr pomocniczy, nie gwarancja rozpoznania każdego sekretu w dowolnie nazwanym pliku. Monorepo należy zawęzić do przygotowanego folderu builda, bez symlinków.

### Baza danych / aplikacja wielousługowa

Przykładowy, **operator-owned** plik `/pełna/ścieżka/test-db.compose.yaml`:

```yaml
services:
  db:
    image: postgres:17
    environment:
      POSTGRES_USER: test
      POSTGRES_PASSWORD: disposable-test-only
      POSTGRES_DB: app_test
    networks: [audit]
    tmpfs:
      - /var/lib/postgresql/data
    healthcheck:
      test: [CMD-SHELL, 'pg_isready -U test -d app_test']
      interval: 2s
      timeout: 2s
      retries: 30
  sut:
    environment:
      DATABASE_URL: postgres://test:disposable-test-only@db:5432/app_test
    depends_on:
      db:
        condition: service_healthy
```

```bash
make check APP=/projekty/panel APP_IMAGE=<twoj-obraz-runtime> \
  APP_COMMAND='<start-uslugi>' COMPOSE_OVERRIDE=/pełna/ścieżka/test-db.compose.yaml
```

Wartości w nawiasach wymagają zastąpienia. Override jest konfiguracją uprzywilejowaną operatora: może zmienić zabezpieczenia Compose. Narzędzie nie zatwierdza bezpieczeństwa dowolnego override. Korzystaj z jawnych ścieżek; nie montuj tam hostowego Docker socketu ani profili przeglądarek. Przykład bazy jest przepisem wdrożeniowym, nie wykonanym tutaj testem integracyjnym.

## Zakres UI

`project` powinien być stabilnym, unikatowym identyfikatorem produktu, np. `goethe`. Zmiana tej nazwy zmienia przestrzeń deduplikacji Planfile. `routes` ma pary `id` + `path`. `journeys` zawierają `id`, `path`, `steps`. Identyfikatory tras, scenariuszy i kroków muszą być stabilne i jednoznaczne.

Nawigacja początkowa musi pozostawać w originie `base_url`. Przeglądarka przepuszcza żądania do tego originu oraz jawnych `allowed_origins`; pozostałe są blokowane. CDNy fontów i skryptów trzeba albo dostarczyć lokalnie, albo jawnie dopuścić i włączyć sieć na poziomie Compose. Samo `allowed_origins` nie otwiera egress w sieci Docker `internal`.

```yaml
allowed_origins:
  - https://static.example.test
locale: pl-PL
timezone: Europe/Warsaw
color_scheme: dark
headless: false
sandbox: false
```

`headless: false` jest potrzebne do obserwowania sesji w noVNC. Domyślne `sandbox: false` dotyczy Chromium i jest kompromisem kompatybilności dla zaufanej, lokalnie przygotowanej aplikacji. Nie oznacza bezpiecznego uruchamiania wrogich stron; zobacz SECURITY.md.

## Scenariusze

Działania: `click`, `fill`, `press`, `hover`, `check`, `select`, `assert`. Zmieniające stan działania wymagają `allow_mutation: true`. Nie ma akcji wykonującej shell, pobierającej pliki aplikacji ani wykonującej dowolny kod JavaScript.

Oczekiwania: `visible`, `hidden`, `text` (dokładny tekst), `count`, `url` (wyrażenie regularne), `changed` (zmiana tekstu body, tylko heurystyka). Każdy krok wymaga oczekiwania. Oczekiwanie jest oceniane po wykonaniu działania, zanim zostanie zebrany kolejny pakiet dowodów.

```yaml
journeys:
  - id: filtr-katalogu
    path: /catalog
    steps:
      - id: wpisz-filtr
        action: fill
        selector: '[data-testid="filter"]'
        value: testowy produkt
        allow_mutation: true
        expect:
          kind: visible
          selector: '[data-testid="result-row"]'
      - id: otworz-szczegoly
        action: click
        selector: '[data-testid="result-row"]'
        allow_mutation: true
        expect:
          kind: url
          value: '/products/[0-9]+$'
      - id: otworz-podpowiedz
        action: hover
        selector: '[data-testid="help"]'
        expect:
          kind: visible
          selector: '[role="tooltip"]'
      - id: zamknij-podpowiedz
        action: press
        selector: body
        key: Escape
        allow_mutation: true
        expect:
          kind: hidden
          selector: '[role="tooltip"]'
```

Gdy nie uda się wykonać działania, wynik jest `blocked`, a nie fałszywie potwierdzona awaria funkcji. Kolejne kroki są `not_run`; komórka ma niepełne wykonanie. Gdy działanie się wykonało, ale jawne oczekiwanie nie zaszło w limicie, powstaje naruszenie kontraktu UI. Nie ma automatycznego „naprawiania” scenariusza przez LLM, które mogłoby zamaskować błąd.

Scenariusz nie może zakładać, że `cart-count` zawsze startuje od zera na współdzielonym backendzie. Używaj sesyjnych danych testowych lub poprzedź przypadek jawnie opisanym resetem przez UI. Produkcyjne płatności, usuwanie kont, wysyłki wiadomości i zewnętrzne integracje powinny być zastąpione środowiskiem testowym.

## Przechwytywanie i prywatność

```yaml
capture:
  repeats: 2
  scroll_tiles: 4
  settle_ms: 250
  timeout_ms: 10000
  max_cell_seconds: 240
  max_elements: 2500
  max_text_rects: 5000
  max_html_bytes: 2000000
  ready_selector: '[data-testid="app-ready"]'
  freeze_animations: true
  mask_selectors:
    - input
    - textarea
    - '[contenteditable=true]'
    - '[data-private]'
    - '.user-email'
```

Maski są nakładane na kopię obrazu i serializację, bez zmiany układu mierzonej strony. Tekst w zamaskowanych elementach nie jest wejściem do detekcji tekstu. axe-core pomija te selektory w tej implementacji: to jawny kompromis prywatności, który ogranicza pokrycie dostępności. Na w pełni syntetycznej aplikacji można podać węższe maski.

Dwa odczyty DOM otaczające screenshot pozwalają rozpoznać zmianę geometrii/tekstu podczas przechwycenia. Nie są testem identyczności każdego piksela canvas lub wideo. Przekroczenie limitu kolektora albo wymaganego detektora skutkuje niekompletnością, nie PASS.

## Kontrolowany crawl

```yaml
crawl:
  enabled: true
  allow_paths: ['/docs/*', '/products/*']
  max_pages: 10
```

Crawler zbiera href z DOM, działa w obrębie originu, ma limit liczby stron i odrzuca typowe destrukcyjne ścieżki. Nie klika arbitralnych formularzy i nie generuje zgód na mutację. Nawet GET może mieć skutki uboczne w źle zaprojektowanej aplikacji; allowlista nie zastępuje środowiska testowego. Trasy odkryte w danym audycie trafiają do `route-inventory.json`.

## Wykluczenia

```yaml
suppressions:
  - rule: TW-TEXT-OVERLAP
    selector: '#decorative-heading'
    route: 'home--*'
    reason: 'Świadomy efekt typograficzny; zaakceptowany w przeglądzie UI.'
    owner: frontend-team
    expires: '2026-12-31'
```

Wykluczenie ma właściciela, powód i termin. Nie usuwa dowodu; zmienia status na `suppressed` i nie produkuje ticketa. Po terminie przestaje działać. Unikaj globalnego `rule: '*'` służącego wyłącznie wyciszeniu CI.

## Baseline

```yaml
baseline:
  directory: /baselines
  threshold: 0.005
  color_delta: 24
  fail_on_difference: false
```

```bash
python -m testwins baseline artifacts/lab/<run-id> --directory baselines --approve
```

Wymagane jest świadome zatwierdzenie kompletnego audytu po obejrzeniu obrazów. Brak baseline ma status `missing`, a nie `matched`. Zmiana wersji przeglądarki albo fingerprintu środowiska renderowania unieważnia porównanie. Fingerprint obejmuje platformę, Playwright i inwentarz fontów; nie jest pełnym SBOM ani dowodem niezmienności wszystkich bibliotek rasteryzacji.

Zatwierdzenie wadliwego obrazu może utrwalić wadę — narzędzie nie uznaje samego baseline za prawdę o projekcie. `fail_on_difference: true` to jawny kontrakt operatora, że przekroczenie progu jest naruszeniem regresji.
