# Testwins Live — uruchomienie i praca z setkami stron

## Jeden komputer, Docker i noVNC

W katalogu projektu:

```bash
make live-novnc
# Panel incydentów: http://127.0.0.1:9067/
# Pulpit noVNC:     http://127.0.0.1:6080/vnc.html
# Landing:         http://127.0.0.1:8090/
cat .testwins-live-secret/vnc_password
make live-novnc-down
```

To nowy ciągły obserwator, inny od jednorazowego `make landing-check`.
Przykład ma 3 trasy × 3 profile × Chromium = 9 komórek, a NIE 3 przeglądarki
w jednym przebiegu. Manifest pozwala włączyć dodatkowe przeglądarki. W obrazie
`engines` dostępne są Chromium/Firefox/WebKit; marki Chrome/Edge/Brave wymagają
obrazu `cdp`. W obu przypadkach profile są emulacją. Nowa pętla może wykonywać
komórki równolegle, stary runner `run` zachowuje dotychczasową kolejność.

Headless bez noVNC:

```bash
make live-docker
make live-docker-down
```

Domyślne limity kontenera obserwatora: 3 GiB, 3 CPU, 512 MiB pamięci współdzielonej;
128 MiB dla statycznej strony. Są punktem startowym, nie benchmarkiem ani obietnicą,
że każda aplikacja zmieści się w takiej pamięci. Profile i site allowlist są w
`configs/live/`. Dowody są w nazwanym wolumenie `live-artifacts`, nie na źródłowym
folderze aplikacji. `down` nie usuwa wolumenu. Eksport potwierdzonych dowodów przed
usunięciem danych; nie usuwaj aktywnego wolumenu bez świadomej decyzji.

## Lokalny proces deweloperski, bez Dockera obserwatora

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e '.[live]'
python -m playwright install chromium

# Docker służy tu tylko do uruchomienia dołączonej strony; skaner jest lokalny.
make live-landing
# Ctrl+C zatrzymuje skaner, a nie stronę. Stronę zatrzymaj osobno:
make landing-down
```

Własna już uruchomiona aplikacja: utwórz `testwins.watch.yaml` w jej katalogu,
opierając się na `configs/live/landing.watch.yaml`. Dostosuj `base_url`, trasy,
`watch.paths`, selektory i maski. Przykład:

```bash
testwins watch --config /repo/app/testwins.watch.yaml --root /repo/app --serve
# Albo z Makefile Testwins:
make live-watch WATCH_CONFIG=/repo/app/testwins.watch.yaml PROJECT_ROOT=/repo/app
```

`watch` nie uruchamia sam dowolnego backendu. Do uruchomienia testowanej usługi
z kopii folderu nadal służy istniejące `make up APP=... APP_IMAGE=... APP_COMMAND=...`.
Skanowanie wielu usług wymaga wielu jawnych `sites`, nie odczytu Twojej historii
przeglądarki i nie automatycznego przeszukiwania Internetu.

## Inwentaryzacja setek tras

Plik `paths.txt` zawiera jedną autoryzowaną ścieżkę na linię, np. `/`, `/orders/`,
`/orders/new/`. Nie umieszczaj tokenów ani akcji destrukcyjnych w URL.

```bash
python scripts/make_live_inventory.py \
  --paths paths.txt --base-url http://127.0.0.1:8080 \
  --output /repo/app/testwins.watch.yaml

testwins capacity --config /repo/app/testwins.watch.yaml \
  --seconds-per-cell 2 --workers 6 --interval 60

testwins watch --config /repo/app/testwins.watch.yaml --root /repo/app --serve
```

Generator tworzy Chromium × desktop/tablet/mobile. Dodanie przeglądarek do
`browsers` zwiększa iloczyn. Manifest dopuszcza do 10 000 komórek. To limit
walidacji, NIE przetestowana zdolność renderowania 10 000 stron naraz.

Dla N komórek, średniego czasu t i C workerów idealny pełny obieg wynosi:

```
T_cycle >= N * t / C
N = liczba tras × liczba przeglądarek × liczba profili
```

300 × 3 × 3 = 2700 komórek. Przy założeniu t=2 s i C=6 otrzymujemy 900 s,
czyli 15 minut, zanim uwzględnimy rozruch, limity origin, ogony opóźnień i modele.
To rachunek pojemności, nie uzyskany benchmark. Przy `per_origin: 1` cała pojedyncza
witryna pozostaje sekwencyjna: dla 2700 komórek i 2 s byłoby co najmniej 5400 s.
Podnoszenie limitu obciąża także testowaną aplikację i wymaga pomiarów.

„Near real time” dotyczy małego gorącego zbioru i zmian konkretnych tras.
Kilka gorących kontekstów obserwuje DOM/resize/scroll; pozostałe cele są odświeżane
okresowo i po zmianach przypisanych plików. Tylko jawnie oznaczone `hot: true`
i limit `max_hot_pages` pozwalają utrzymywać stronę otwartą. Nie twórz setek kart.

Próg 1 s debounce nie oznacza 1 s gwarantowanego czasu alertu. Na opóźnienie
składają się wykrycie zmiany, debounce, kolejka, nawigacja, stabilizacja i pomiar;
potwierdzenie domyślnie wymaga dwóch skanów. Panel pokazuje wiek ostatniego skanu,
a `health.json` oraz zdarzenia heartbeat pokazują zaległości i maksymalne spóźnienie.

## Regulator zasobów i degradacja

psutil monitoruje hostowe CPU i wolną pamięć/dysk. Uwzględniane są affinity,
limity CPU oraz pozostała pamięć cgroup v2. Odczyt procentowego obciążenia CPU
jest hostowy, nie pełny pomiar procentu wykorzystania limitu cgroup. Rezerwa RAM,
założony koszt workera, limit równoległości i histereza ograniczają nowe zadania.
To kontrola przyjęcia, nie gwarancja RSS procesu; twarde ograniczenia nakłada Docker.

Przy presji CPU najpierw spada równoległość i sufit analizy do L1. Przy braku
rezerwy RAM/dysku nowe skany są wstrzymywane, nie zaliczane. Agent emituje
`resource_paused`/`resource_resumed`. Maksymalnie jeden proces danej przeglądarki
jest współdzielony, ale każdy cel ma oddzielny kontekst. Workerzy CV/LLM działają
w osobnej kolejce (16 oczekujących; jeden wykonywany), nie blokując alertów DOM.
YOLO używa domyślnie CPU; automatyczny dobór GPU ani rozproszony scheduler nie
są zaimplementowane. Można ręcznie podzielić manifest pomiędzy niezależne agenty
z osobnymi katalogami i portami. Nie dziel SQLite po NFS.

Co 15 s agent przestaje przyjmować nowe pomiary na czas opróżnienia bieżącej
partii i sprawdzenia retencji. Usuwa stare, nieprzypięte pakiety screenshotów
i analiz, chroni aktywne incydenty, najnowsze pomiary i źródła analiz w toku.
Gdy same chronione dowody przekraczają limit, zatrzymuje nowe skany. Limit dowodów
jest miękki: partia skanów i pojedyncza inferencja mogą go chwilowo przekroczyć;
SQLite/metadane są ograniczane oddzielnie. Retencja zdarzeń to domyślnie 20 000,
historia czasu 64 pomiary/cel, historia zakończonych incydentów 30 dni.

## Gradacja LLM i CV

Najpierw przetestuj L1/L2 bez modeli. W tym samym środowisku Python:

```bash
python -m pip install -e '.[live,llm,cv]'
cp .env.example .env
```

Wybierz rzeczywisty model obsługujący obrazy w `.env`. Wysyłanie do zewnętrznego
operatora wymaga `LLM_ALLOW_REMOTE=1`. Brak tej zgody blokuje transfer; nie ma
przykładowego działającego klucza. Lokalny operator również musi być poprawnie
skonfigurowany w istniejącym kliencie LiteLLM.

W manifeście:

```yaml
resources:
  max_workers: 3
  max_tier: 3
  reserve_mb: 1024
llm:
  enabled: true
  env_file: .env
  calls_per_hour: 4
  cooldown_s: 900
  max_inflight: 1
cv:
  enabled: true
  backend: opencv
```

Wywołanie LLM następuje tylko po lokalnej obserwacji i przejściu kontroli zasobów,
cache, cooldown oraz trwałego limitu. Nie jest to semantyczne sprawdzenie każdego
screenshotu. Błędy requestów też zużywają limit; restart nie zeruje bazy. Model,
obraz, DOM i zakres wpływają na cache. Wynik tworzy `vision_candidate`, a nie
`incident_confirmed`; nie jest automatycznie dołączany do potwierdzonych ticketów.

`.env` ogranicza także tokeny odpowiedzi i timeout. Limit czterech requestów na
agentogodzinę NIE jest limitem wydatku w USD ani współdzielonym budżetem całej
firmy. Kontrolę kosztu finansowego skonfiguruj u operatora lub w LiteLLM Proxy.
Dołączone obrazy live nie instalują CV/LLM/YOLO automatycznie; aby ich używać
w Dockerze, rozbuduj obraz o te extras, zamontuj plik `.env` tylko do odczytu
oraz przemyśl kontrolę sieci i sekretów. Nie przekazuj kluczy do SUT.

YOLO jest osobnym extra i wymaga przejrzanych lokalnych wag oraz `trust_model`.
Detekcja regionów nie jest rozpoznaniem błędów; licencja modelu jest niezależna.

## Lokalny fragment pulpitu

```bash
python -m pip install -e '.[live,desktop,cv]'
testwins watch --config configs/live/desktop.watch.yaml --root . --serve
```

Dostosuj prostokąt i maski PRZED uruchomieniem. `allow_desktop_capture: true`
jest obowiązkowe, monitor nie pobiera całego pulpitu bez zgody. Wymagane są
uprawnienia systemowe do zrzutu ekranu. MSS nie zapewnia identycznego działania
w każdym compositorze Wayland; preferuj kontrolowany X11/noVNC lub właściwy
sterownik systemowy. W kontenerze widzi pulpit kontenera, nie hosta.

Zmiana pikseli daje kandydata. Dopiero jawny kontrakt obrazu referencyjnego,
lokalnie zatwierdzonego przez operatora, może potwierdzić niespełnienie wzorca.
Wynik pozostaje `partial`: brak DOM i testu logiki aplikacji jest widoczny.
Obsługa MSS jest zaimplementowana, ale w środowisku wydania testowano ją na
wstrzykniętych obrazach, nie na rzeczywistym przechwyceniu pulpitu.

## API, CI, eksport i Planfile

```bash
testwins live-status .testwins/live
testwins live-serve .testwins/live --port 9067
curl -N http://127.0.0.1:9067/events
curl http://127.0.0.1:9067/api/status

testwins watch --config testwins.watch.yaml --root . --once
# 0: zadeklarowany zakres kompletny, bez niekandydackich naruszeń
# 1: naruszenie kontraktu/reguły
# 2: niekompletność / błąd wykonania; nie jest PASS
```

`--once` wykonuje jeden pomiar każdej komórki. Nowy incydent może pozostać
`observed`, mimo że kod CI to 1. Do potwierdzenia potrzeba dwóch kolejnych skanów;
ciągła pętla realizuje to naturalnie. Zatrzymanie Ctrl+C pętli to kod 0 procesu,
nie deklaracja poprawności aplikacji.

Panel jest read-only i domyślnie loopback. SSE obsługuje Last-Event-ID i zgłasza
lukę retencji. Panel pokazuje do 500 aktywnych incydentów (limit jest widoczny),
CLI do 5000, a eksport wybiera wszystkie. To nie usuwanie nadmiarowych wyników.
Nie ma tu uwierzytelnionego, publicznego SaaS ani skonfigurowanych Slack/webhooków.

```bash
testwins live-export .testwins/live --output exports/review-001 --project portal
# Podgląd publikacji z istniejącym SDK Planfile i .planfile:
testwins publish exports/review-001/proposals.json --project /repo/portal
# Jawny zapis:
testwins publish exports/review-001/proposals.json --project /repo/portal --apply
```

Eksport wymaga nowego katalogu poza folderem live. Kopiuje dowody i weryfikuje
integralność. Stare zakresy konfiguracji nie są automatycznie publikowane;
`needs-human` pozostaje domyślne. Dostępny jest świadomy `--include-candidates`,
ale nie zmienia kandydata w błąd. Polecenie publikacji ani naprawy nie działa
samoczynnie po wykryciu obrazu. Proces SDK Planfile nie został uruchomiony
w środowisku tego wydania.
