# Testwins 0.4.0 — rzeczywisty stan weryfikacji

Data: **22 września 2026**. To scalone, dystrybuowalne wydanie alpha, a nie poświadczenie uruchomienia wszystkich
integracji. Kod źródłowy i raportowane testy przygotowano w tej sesji. Nie wykonano publikacji PyPI, wdrożenia domeny,
push/PR ani zmian zdalnych repozytoriów. Status dotyczy wyłącznie jawnie określonego zakresu.

## Wykonane

| Zakres | Wynik i źródło |
|---|---|
| Jednostkowe i lokalne integracyjne | **254 passed**, 8 testów browser poza tym przebiegiem; `unit-tests.xml` / `.log` |
| Rzeczywisty renderer Chromium/CDP, podzbiór | **6 passed**, dwa pełne testy integration wyłączone tylko z tego podzbioru; `renderer-tests.xml` |
| Landing w 3 profilach | **24/24 checks**, **98 snapshotów**, 3/3 komórki; `landing-result.json` |
| Integralność kontrolnego landing | **100 zdarzeń, 596 plików** sprawdzonych; w zadeklarowanym zakresie 0 potwierdzonych naruszeń i 0 kandydatów |
| Wheel | Instalacja bez zależności w nowym venv, import spoza drzewa źródeł, console script, init minimal/Clonerd, parsery profilu |
| Terminal z zainstalowanego wheel | **4/4 kroki**, EOF i poprawny kod zakończenia; `wheel-smoke.json` / `wheel-terminal.log` |
| Składnia | Python compileall, collector.js i app.js przez `node --check`, entrypoint przez `sh -n` |

254 testy zawierają m.in. rzeczywisty lokalny HTTPServer/urllib, Pexpect/PTY, OpenCV, algorytmy i atrapy kontraktów
zewnętrznych. **Nie wszystkie są pełnymi testami zewnętrznych narzędzi.** Test suite/pytest bridge używa również
kontrolowanego raportu. Nie sumuj historycznych liczb testów z wersji 0.2/0.3 z wynikami tego wydania.

Renderer-only sprawdza m.in. pojedynczą nieudaną asercję przy `repeats: 1`, brak przeglądarki z zachowanym planem,
rzeczywiste oczekiwania UI, import cookies, geometrię, wykrycie/potwierdzenie/ustąpienie defektów live,
dopasowane CSS i rzeczywisty `JSHeapUsedSize`. To dowód działania konkretnych ścieżek, nie wszystkich możliwych scen.

## Dwa niezaliczone testy integracyjne

Próba pełniejszych funkcji zakończyła się **2 failed, 3 passed**. Te trzy sukcesy są już ujęte w późniejszym
podzbiorze i nie są liczone drugi raz. Oryginalny log i JUnit zachowano jako `integration-attempt.*`.

1. Odtworzenie `storage_state` z localStorage: `ERR_BLOCKED_BY_ADMINISTRATOR` przy wewnętrznej nawigacji
   przeglądarki. Sprawdzenie cookies działało osobno, ale nie zastępuje tego testu.
2. Prawdziwy browser download: timeout oczekiwania na zdarzenie. Środowisko ma `DownloadRestrictions=1`;
   sam timeout nie dowodzi wyłącznie tej przyczyny. Walidator pobranego pliku przeszedł testy jednostkowe,
   ale pełne zdarzenie i zapis w rzeczywistej przeglądarce wymagają ponowienia na docelowym komputerze.

Testy pozostają aktywne w `make test-browser` i zadaniu CI. Nie nadano im `xfail`, nie zmieniono ich na sztuczne
sukcesy. `pytest -m 'browser and not integration'` świadomie wykonuje tylko podzbiór.

## Ograniczenie administracyjne i stos przeglądarki

Zarządzany Chromium ma `URLBlocklist: ["*"]`. **Nie modyfikowano ani nie omijano polityki.**
Kontrolowany własny HTML/CSS/JS jawnie wczytano do pustej strony. Dalej pracował rzeczywisty renderer, CDP,
zrzuty i interakcje. Nie jest to test HTTP, CSP nginx, routingu, ciasteczek rzeczywistego portalu lub kontenera noVNC.
W raportach znajduje się `fixture_mode`, nie fikcyjne `none`.

Lokalnie: Chromium **144.0.7559.96**, Playwright **1.57.0**, Python **3.13.5**, Linux.
Kontrolne fixture używały `sandbox_enabled: false` w tym izolowanym środowisku renderowania; nie walidują
sandboxu docelowego Docker. Dockerfile/requirements deklarują Playwright **1.61.0**, czego tutaj nie uruchomiono.
Wersje pozostałych bibliotek są w `environment.json`.

## Instalacja i pakowanie

Wheel zainstalowano `--no-deps` do nowego venv. Wykorzystano istniejące biblioteki kontenera przez lokalny `.pth`,
ponieważ odziedziczenie system-site-packages nie obejmowało nadrzędnego venv. To **nie jest czysta instalacja
zależności z sieci**. Import i terminal pochodziły z zainstalowanego wheel, nie z katalogu źródeł. Źródła i wheel
sprawdzono pod kątem zgodności modułów, metadanych, zasobów, archiwum i hashy. Setuptools budował bez frontendów
`build`/`wheel`/`twine` dostępnych jako osobne dystrybucje; nie twierdzimy, że wykonano `twine check`.

Wagi modeli, przeglądarki, obrazy Docker ani fonty nie są dołączone do paczki. Instalacja zależności wymaga
odpowiedniego repozytorium/sieci. Zakresy zależności nie są kompletnym zamrożonym lockfile.

## Niewykonane zewnętrznie

Pełny Docker/noVNC i 9-komórkowe macierze, rzeczywisty portal Clonerd, SDK TestQL/Planfile, pełny upstream WUP,
LiteLLM inference, wagi YOLO, przechwytywanie MSS, workflow GitHub CI. Kontrakty/instalatory mają testy lokalne,
a konfiguracje są dostarczone; to nie zastępuje tych integracji. Nie deklarujemy też pełnej zgodności
`wellmanifest/docs`; zachowane manifesty wskazują własny schemat/ograniczony profil logów i brak authority.

Profil Clonerd: **6 person x 3 urządzenia**, osobny read-only API, 27 wejściowych celów skanu/live.
Przeszły parsery i walidacja; selektory i zachowanie na rzeczywistej aplikacji nie były sprawdzone.
Szczegółowy brakujący parytet biznesowy jest w `integrations/clonerd/scope.json`.

## Odtworzenie na autoryzowanym komputerze

```bash
make bootstrap
. .venv/bin/activate
make test
make test-browser
make install-testql-source TESTQL_REF=PRZEJRZANY_COMMIT
make test-final
make landing-check MATRIX=engines
```

Do prawdziwych testów browser ustaw `CHROMIUM_EXECUTABLE`, gdy binarium nie jest dostępne jako `chromium`.
Przykład: ścieżka z `sync_playwright().start().chromium.executable_path` po instalacji Playwright browsers.
Pełne CI ma osobny job ustawiający tę ścieżkę i niewyciszający testów integracyjnych.

Dowody screenshot/DOM są w osobnym archiwum weryfikacyjnym. ZIP projektu zawiera podsumowania i testy.
Hashes wykrywają zmianę plików, ale nie stanowią podpisu wydawcy ani dowodu autentyczności wobec złośliwego przepisania całości.
