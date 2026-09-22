# Testwins 0.4.0

**Jedna paczka do testów GUI, scenariuszy TestQL, shell/terminala, osobnych kontraktów API i ciągłej obserwacji.**
To scalone wydanie wcześniejszych Testwins 0.2/0.3 oraz migracji `twin_ux` / Clonerd.
Nazwa dystrybucji Python: `testwins`. Landing dla `testwins.com` jest w osobnym `landing/`.
ZIP zawiera kod, wheel, sdist, Docker/noVNC, Makefile, profile i dokumentację.
**Paczka nie została opublikowana na PyPI, domena nie została wdrożona, repozytoria WUP/Planfile nie zostały zmienione zdalnie.**

## Start w Dockerze

Wymagania hosta: Docker z Compose v2, Python 3.11–3.13 i GNU Make. Potrzebny dostęp do sieci do pobrania obrazów i zależności.
Nie potrzebujesz lokalnego pulpitu ani zainstalowanych przeglądarek.

```bash
cp .env.example .env
make landing-check MATRIX=chromium
# Osobny nginx + Testwins: Chromium x desktop/tablet/mobile + scenariusz TestQL.
make report INSTANCE=landing
make vnc-password INSTANCE=landing
make landing-down
```

`http://127.0.0.1:8090/` — landing, `http://127.0.0.1:6080/vnc.html` — pulpit,
`http://127.0.0.1:8088/` — raporty. noVNC pokazuje wykonywany przebieg, nie zachowuje otwartych kart po jego zakończeniu.

```bash
# Pełne macierze 3 x 3, wykonywane przez runner:
make landing-check MATRIX=cdp       # Chrome, Edge, Brave; Linux amd64
make landing-check MATRIX=engines   # Chromium, Firefox, WebKit

# Ciągła obserwacja własnego landing + SSE/SQLite i kontrola zasobów:
make live-novnc
# Panel: http://127.0.0.1:9067/ ; desktop: http://127.0.0.1:6080/vnc.html
make live-novnc-down
```

Przed drugim środowiskiem zatrzymaj pierwsze: oba mogą zajmować te same porty.
Chrome/Edge/Brave współdzielą silnik. Firefox i WebKit nie używają transportu CDP.
Emulacja viewportu/touch nie jest fizycznym urządzeniem ani rzeczywistym Safari na iOS.
Przykład live domyślnie obserwuje **3 trasy x 3 profile x Chromium**, nie trzy silniki.

## Lokalna instalacja

```bash
make bootstrap
. .venv/bin/activate
# Alternatywa bez bootstrap, po utworzeniu i aktywowaniu venv:
python -m pip install './dist/testwins-0.4.0-py3-none-any.whl[live,terminal]'
python -m playwright install chromium

testwins --version
testwins doctor
testwins init moja-aplikacja
```

Podstawa nie instaluje LLM, YOLO ani TestQL niejawnie. Instaluj potrzebny backend:

```bash
python -m pip install '.[testql]'           # dystrybucja TestQL z PyPI
make install-testql-source TESTQL_REF=main # jawny wariant źródłowy + kontrola publicznego SDK
python -m pip install '.[llm,cv]'           # LiteLLM i OpenCV
python -m pip install '.[desktop,terminal]' # przechwytywanie GUI / PTY
python -m pip install '.[yolo]'             # opcjonalne Ultralytics; osobna analiza licencji
```

`main` to ruchoma referencja, nie lockfile. Przed wdrożeniem przypnij `TESTQL_REF` i `PLANFILE_REF` do przejrzanych commitów.
Obrazy pełnego labu nadal instalują i sprawdzają API TestQL przy budowaniu; obraz live nie potrzebuje tego SDK.
`doctor` raportuje dostępność backendów, nie wykonuje testów i nie jest bramką poprawności aplikacji.

## Migracja Clonerd bez drugiego silnika twin_ux

```bash
testwins init ./clonerd-tests --profile clonerd
cd clonerd-tests
make configure BASE_URL=http://127.0.0.1:8891
make validate
make scan       # 9 wejściowych tras x 3 profile; GUI tylko do odczytu
make personas   # 6 deklaratywnych person x 3 profile + osobny GET /v1/menu
make watch      # monitoring wejściowych widoków, nie niejawne klikanie person
```

Aplikacja musi już działać. Dla Dockerowego wykonawcy użyj originu osiągalnego z jego sieci, nie hostowego `127.0.0.1`.
Z katalogu źródeł można też użyć `make clonerd-init` / `make clonerd-check CLONERD_URL=http://127.0.0.1:8891`.

Profil zawiera wykonywalne YAML person, nie bibliotekę legacy. Zachowuje `layout=desktop` dla desktop/tablet i
`layout=onepage` dla mobile. Nowe kontrakty nie przemilczają brakującej kontrolki. Przykłady dla PDF, budżetu heap i
mutującego API są **oddzielne i nie uruchamiają się w domyślnym skanie**.
Selektory pochodzą z przesłanych testów: nie zostały sprawdzone na rzeczywistej aplikacji Clonerd.
W `scope.json` wskazano granice: płatności, semantyka faktury, egzekwowanie RBAC, połączenie noVNC i aktualność danych
nie stają się zweryfikowane od samej obecności elementu. Szczegóły: [integrations/clonerd/README.md](integrations/clonerd/README.md).

## Własny folder aplikacji w izolacji

```bash
make check APP=/sciezka/do/aplikacji \
  APP_IMAGE=php:8.3-cli \
  APP_COMMAND='php -S 0.0.0.0:8080 -t public' \
  MATRIX=chromium CONFIG=configs/audit.yaml
```

Podaj obraz, instalację zależności (`APP_INSTALL`), port i komendę odpowiednie dla swojej aplikacji.
Folder jest kopiowany do osobnego obrazu SUT; audytor GUI go nie dostaje. Wykluczane są standardowe katalogi sekretów,
`.env`, `.auth`, pliki `*.storage-state.json`, repozytorium Git, zależności i cache. To filtr nazw, nie gwarancja wykrycia każdego sekretu.
Domyślnie sieć runtime jest wewnętrzna. Dodatkowe usługi dodaj w `COMPOSE_OVERRIDE`.

## Jednoznaczna bramka wykonania

W wydaniu 0.4 plan wszystkich obowiązkowych kroków powstaje **przed uruchomieniem przeglądarki**.
Jedna nieudana asercja blokuje sukces, nawet przy `repeats: 1`, bez potwierdzonych naruszeń wizualnych i bez udziału LLM.
Nie wolno zamienić timeoutu, braku przeglądarki lub pominiętego kroku na wynik pozytywny.

```bash
testwins run --config konfiguracja.yaml --output artifacts
testwins gate artifacts/KONKRETNY-RUN
testwins verify artifacts/KONKRETNY-RUN
```

Dla `run` / `gate`: **0** = wszystkie zaplanowane kontrakty zaliczone i kompletny zadeklarowany zakres bez potwierdzonych naruszeń;
**1** = nieudana obowiązkowa asercja, przekroczony jawny budżet albo potwierdzone naruszenie;
**2** = niekompletność, brak wymaganego dowodu lub błąd konfiguracji. Kandydat wizualny nie jest automatycznie potwierdzony.
Kod 0 nie dowodzi poprawności wszystkich niewidzianych stanów aplikacji.
`verify` sprawdza integralność, a nie poprawność UI. `vision` raportuje analizę kandydatów, a nie zaliczenie produktu.

Raport zawiera `report.json`, plan kroków, ich statusy, screenshoty przed/po, DOM, `junit.xml`, macierz CSV,
manifest plików i propozycje Planfile. JUnit, HTML, CLI i suite używają tej samej bramki.

## Sesje, pliki, API, pytest

- Nazwane sesje są prywatnym `storage_state`, ładowanym do nowego kontekstu; bez automatycznego odczytu profilu hosta.
- `download` czeka na rzeczywiste zdarzenie pobrania i sprawdza nazwę, rozmiar, opcjonalny prefix i SHA-256. Payload domyślnie nie jest zachowywany.
- `testwins api` wykonuje jawne kontrakty HTTP raz, niezależnie od macierzy urządzeń. POST wymaga `allow_mutation` i `--approve-mutations`.
- `pytest -p testwins.pytest_plugin` udostępnia `testwins_run` i `testwins_assert_report` bez automatycznego skanowania.

Przykłady: [docs/RELEASE-0.4.md](docs/RELEASE-0.4.md). API i metryki CDP są oddzielone od diagnozy opartej na obrazie/DOM.

## WUP, LLM i tickety

```bash
make wup-integrate WUP_ROOT=/repo/wup             # podgląd
make wup-integrate WUP_ROOT=/repo/wup APPLY=1     # lokalny zapis + backup
wup gui watch /repo/aplikacja --config testwins.watch.yaml
```

WUP integruje live-monitor jako `wup gui`, nie zmienia działania `wup watch`. Nie wykonujemy push/PR.
[Dokumentacja WUP](integrations/wup/README.md).

Konfiguracja LiteLLM jest w jednym `.env`. Model musi obsługiwać obrazy; nazwy modelu nie zgadujemy.
Transfer zdalny wymaga `LLM_ALLOW_REMOTE=1`. YOLO wymaga lokalnych przejrzanych wag i jawnego zaufania modelowi.
LLM nie wykonuje zmian ani poleceń, a jego wnioski pozostają kandydatami. Live ogranicza kolejkę, równoległość,
CPU/pamięć, retencję, liczbę wywołań i stosuje gradację L0–L3; nie gwarantuje obserwacji wszystkich stron co sekundę.
[Vision](docs/VISION.md), [live](docs/live/OPERATIONS.md), [92 klasy GUI](docs/live/GUI_TAXONOMY.md).

```bash
testwins live-export .testwins/live --output exports/review --project moja-aplikacja
testwins publish exports/review/proposals.json --project /repo/aplikacja
# --apply dopiero po przeglądzie; .planfile musi istnieć.
```

## Weryfikacja i wydanie

```bash
make test                         # jednostkowe + lokalne HTTP/PTY/CV, bez przeglądarki
make test-browser                 # wszystkie testy przeglądarkowe, także wymagające normalnej polityki sieci
make test-final                   # dodatkowo wymaga rzeczywistego SDK TestQL
make package-final               # wheel + sdist + kompletny ZIP + SHA256SUMS
```

**Dokładne wykonane testy i ograniczenia środowiska są w [verification/STATUS.md](verification/STATUS.md).**
Nie zastępuj ich historycznymi liczbami z dokumentacji poprzednich wersji. Dwa testy integracyjne (pełne odtworzenie
localStorage i browser download) pozostają wymagane na docelowym komputerze; w środowisku przygotowania istnieje
administracyjna blokada URL. Nie wyłączano ani nie omijano tej polityki. Pełny Docker i zewnętrzne SDK nie były tu uruchomione.
Ciężkie dowody z rendererów są w osobnym archiwum weryfikacyjnym; ZIP projektu zawiera podsumowania i testy do odtworzenia.

MIT obejmuje własny kod Testwins. Warunki zależności i modeli są oddzielne: [THIRD_PARTY.md](THIRD_PARTY.md).


## License

Licensed under Apache-2.0.
