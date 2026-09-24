---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "ux-strategies",
  "kind": "information",
  "version": 6,
  "title": "Strategie UX, reakcje interfejsu i naprawy z subllm",
  "status": "implemented",
  "owner": "semcod/testwins",
  "created": "2026-09-23",
  "updated": "2026-09-24",
  "review_after": "2026-12-23",
  "source_revision": "c87ff5a93953994140800f75e1e10564349748c1",
  "affected_repositories": [
    "semcod/testwins"
  ],
  "evidence": [
    "repo://semcod/testwins/tests/test_ux.py",
    "repo://semcod/testwins/tests/test_ux_browser.py",
    "repo://semcod/testwins/testwins/ux.py",
    "repo://semcod/testwins/testwins/ux_probe.js",
    "repo://semcod/testwins/testwins/ux_review.py",
    "repo://semcod/testwins/tests/test_target_geometry_browser.py",
    "repo://semcod/testwins/tests/test_observation.py",
    "repo://semcod/testwins/tests/test_observation_browser.py",
    "repo://semcod/testwins/testwins/overlays.py",
    "repo://semcod/testwins/tests/test_overlays.py",
    "repo://semcod/testwins/tests/test_overlays_browser.py",
    "repo://semcod/testwins/testwins/frames.py",
    "repo://semcod/testwins/tests/test_frames_browser.py",
    "repo://semcod/testwins/configs/c2004/frames.yaml"
  ]
}
---

# Strategie UX, reakcje interfejsu i naprawy z subllm

<!-- docs:section purpose -->
## Cel

Testwins łączy wybraną strategię aplikacji z jawnym kontraktem przejścia:
**wejście użytkownika → informacja zwrotna → oczekiwany wynik**.
Wykrywa naruszenia zadeklarowanych wymagań i przygotowuje propozycje napraw.
Profile symulują wybrane nawyki; nie wykrywają intencji prawdziwego człowieka.

<!-- docs:section scope -->
## Zakres

`testwins strategies` wyświetla cztery strategie: `dashboard`, `form`,
`commerce`, `content`, wraz z wzorcami do uwzględnienia w scenariuszu.
Operator wybiera strategię i konkretne wymagania produktu. Profile nie
stwierdzają automatycznie, czy proces zakupowy lub model biznesowy jest poprawny.

Nawyki: `standard`, `deliberate` (500 ms namysłu przed działaniem), `keyboard`
(kontrakty używają press/fill/select), `reduced-motion` (preferencja przeglądarki
`reduce`, domyślny budżet ruchu 0 ms). Dotyk nadal wynika z `devices.*.touch`
i istniejącego mechanizmu wejścia CDP. Dla pozostałych profili UX przeglądarka
stosuje `no-preference`; stare konfiguracje zachowują dotychczasowe zachowanie.

<!-- docs:section evidence -->
## Podstawa i dowody

Punktem wyjścia implementacji jest rewizja Testwins wskazana w metadanych.
Publiczne API `subllm.complete` / `configured_routes` sprawdzono w lokalnym
`subactor/subllm` na rewizji `356c91986ba1c815f2447c5e320c97ea0bb6c6fa`
(dystrybucja `subactor-subllm` 1.14.0). Testy adaptera używają jawnych doubles;
nie są dowodem wywołania płatnego providera.

Wzorce bazują na [W3C: komunikaty statusu](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html),
[W3C: animacja po interakcji](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)
i [NN/g: czas reakcji](https://www.nngroup.com/articles/response-times-3-important-limits/).
Wbudowane budżety są konfigurowalnymi wartościami startowymi Testwins, nie progami
zgodności WCAG ani uniwersalną oceną UX. Sprawdzenie `role`/`aria-live` nie
zastępuje testu czytnika ekranu. Ocena estetyki i przyczyn w kodzie pozostaje hipotezą.

<!-- docs:section content -->
## Użycie

```bash
python -m http.server 8080 --directory examples/ux-lab
# W drugim terminalu, z katalogu projektu:
python -m testwins strategies
python -m testwins validate --config configs/ux.yaml
python -m testwins run --config configs/ux.yaml --output artifacts/ux
```

Przykład działa lokalnie. Aby zobaczyć błędy, skopiuj konfigurację i zmień
`journeys[0].path` na `/?broken=1`: aplikacja nie zaznaczy wyboru, nie przeniesie
fokusu i pozbawi status semantyki. Powrót do `/` przywraca prawidłowe zachowanie.
Sprawdź oba raporty; to odtwarzalny przykład regresji i jej usunięcia.

```yaml
ux:
  strategy: dashboard
  habit: standard
  budgets: {response_ms: 3000, feedback_ms: 700, motion_ms: 500}
# Fragment pojedynczego kroku journeys[].steps[]:
# action: click
# selector: '#choose'
# allow_mutation: true
# expect: {kind: text, selector: '#result', value: Active projects}
# ux:
#   feedback: {kind: text, selector: '#status', value: Filter applied}
#   announce: true
#   focus: '#result'
#   visual_change: '#choose'
#   motion: '#choose'
```

Każdy krok z `ux: {}` sprawdza czas osiągnięcia zwykłej asercji `expect`.
Jeśli wynik pasował już przed wejściem i nie zaobserwowano nowego dopasowania,
kontrakt zgłasza `TW-UX-OUTCOME-UNCHANGED`.
Pozostałe pola rozszerzają zakres. Budżety kroku nadpisują globalne, a globalne
nadpisują strategię. Muszą mieścić się w `capture.timeout_ms`.
Wybór strategii wymaga przynajmniej jednego kroku UX. Profil klawiaturowy wymaga
odpowiednich działań, np. `press` z `key: Enter`, zamiast kliknięć.

| Warstwa | Kontrakt / obserwacja | Przykładowy błąd |
|---|---|---|
| Funkcjonalność | istniejący `expect`, `response_ms` | brak wyniku lub za późny wynik |
| Grafika | `visual_change`, istniejące detektory geometrii | brak widocznej zmiany wyboru, overlap, clipping |
| Informacja | `focus`, `announce` | niewłaściwy fokus, status bez semantyki |
| Przekaz informacji | `feedback`, `feedback_ms` | brak nowego komunikatu, zbyt późny komunikat |
| Animacja | `motion`, `motion_ms` | długa lub nieskończona animacja CSS/Web Animation |

`feedback` obsługuje `visible`, `text`, `contains_text`, `attribute`; element
musi być widoczny. Stan pasujący już przed wejściem nie jest nowym potwierdzeniem.
`visual_change` porównuje tekst, geometrię i wybrane style, więc sama klasa CSS
bez efektu nie wystarczy. `motion` wymaga `capture.freeze_animations: false`.
Brak elementu do pomiaru lub utrata dokumentu daje `incomplete`, nie sukces.

W `report.json` i osobnym `ux.json` są pomiary, budżety, naruszenia i nieobserwowane
warstwy. HTML i Markdown pokazują wyniki oraz odnośniki do dowodów. Bramka
wymaga kontraktów UX także przy jednym powtórzeniu; status LLM nie wpływa na nią.
Brak pomiaru wymaganego przez plan blokuje zaliczenie. Zmiana dokumentu podczas
kroku (pełna nawigacja) nie jest obsługiwana przez ten próbnik.

### Propozycje poprawek przez subactor/subllm

```bash
python -m pip install '.[subllm]'
# Ustaw w prywatnym .env lub środowisku; klucze przechowuje konfiguracja subllm:
# SUBLLM_PROVIDER_ORDER=zai,openrouter
# SUBLLM_APPLICATION=repair-agent
# SUBLLM_FUNCTION=repair-plan
# LLM_ALLOW_REMOTE=1
# LLM_TIMEOUT=60
python -m testwins ux-review artifacts/ux/KONKRETNY-RUN \
  --output artifacts/ux-review --env .env --limit 10
python -m testwins publish artifacts/ux-review/proposals.json \
  --project /repo/aplikacji --include-candidates
```

Przykład korzysta z istniejącej publicznej trasy `repair-agent/repair-plan`.
Inną parę application/function musi znać polityka subllm. Nie dodajemy potajemnie
trasy `testwins` w drugim repozytorium. Modele, kolejność i failover pochodzą
z subllm; raport zapisuje rzeczywiście zwrócony model i providera. Jeżeli
korzystasz z `SUBLLM_POLICY_FILE`, eksportuj go do środowiska procesu zgodnie
z API subllm 1.14.0; samo `--env` Testwins nie zastępuje konfiguracji SDK.

Klient wykonuje jedno logiczne wywołanie z ograniczonym czasem. Liczbę prób
providerów i budżety modelu kontroluje polityka subllm. Wymagana jest jawna
kolejność providerów oraz zgoda na transfer zdalny. Trasy uruchamiające lokalnych
agentów CLI/Cursor są odrzucane; ten konsument tworzy wyłącznie dane o naprawie.
Przekazuje ograniczony pakiet naruszeń i liczników, bez screenshotów, pełnego DOM
lub kodu źródłowego. Selektory i komunikaty też mogą zawierać dane aplikacji.

Wynik: `ux-review.json` i `proposals.json`. Każda propozycja ma znany identyfikator
dowodu, hipotezę przyczyny, zmianę UI, sposób regresji i wymóg przeglądu. Nieznane
pola, pominięte dowody i wymyślone identyfikatory są odrzucane. Raport wejściowy
jest sprawdzany pod kątem integralności i pozostaje niezmieniony. Wybór ograniczony
przez `--limit` jest jawny w `scope`. Brak naruszeń nie uruchamia modelu i nie
zmienia wyniku niekompletnego audytu na pozytywny.

Przekaż zaakceptowaną propozycję wykonawcy posiadającemu kod aplikacji, po czym
uruchom ten sam scenariusz ponownie. Black-box nie zna ścieżek plików, więc
`files` pozostaje puste. Polecenie `publish` powyżej jest podglądem istniejącego
adaptera Planfile; rzeczywisty zapis wymaga jego jawnego `--apply`.

<!-- docs:section limitations -->
## Ograniczenia

Pomiary biegną od zaobserwowanego zdarzenia wejścia; obejmują próbkowanie i narzut
automatyzacji. Nie są metryką INP. Powiązanie czasowe nie dowodzi przyczynowości:
niezależny timer strony może spełnić ten sam selektor. Używaj izolowanych danych
oraz jednoznacznych stanów. Krótsze niż próbkowanie zmiany mogą zostać pominięte.
Próbnik nie mierzy klatek canvas/video ani percepcji człowieka. Animacje są
sprawdzane w ograniczonym oknie, nie przez cały czas życia aplikacji.

To nie jest automatyczna ocena całej architektury informacji, rozumienia tekstu,
przyzwyczajeń wszystkich odbiorców ani kompletności wzorca biznesowego. Raport
pozostawia niebadane warstwy jawne; LLM nie może ich dopisać jako zaliczonych.
Nie wykonuje patchy źródłowych. Istniejąca ścieżka `vision` nadal używa LiteLLM;
nowa ścieżka `ux-review` korzysta z subllm.

<!-- docs:section next_actions -->
## Weryfikacja i dalsze użycie

```bash
python -m pytest -q
CHROMIUM_EXECUTABLE=/sciezka/do/playwright/chrome python -m pytest -q -m browser
```

Testy obejmują negatywne kontrakty konfiguracji, pominięte pomiary, rzeczywiste
zdarzenia Chromium, status, fokus, ruch, raporty HTTP oraz eksport propozycji.
Dobierz własne selektory, budżety i scenariusze person przed użyciem na aplikacji.
Rozszerzenie zakresu o kolejne ekrany wymaga zadeklarowania ich w podróżach;
jeden udany scenariusz nie świadczy o reszcie produktu.

### Historia weryfikacji: wersja 1

Pierwsza weryfikacja (2026-09-23, baza `60a99dd`): 277 testów jednostkowych zaliczonych,
3 pominięte z powodu opcjonalnych integracji; 18 testów przeglądarkowych
zaliczonych, 1 timeout pobrania pliku. Ten sam timeout odtworzono na niezmienionej
rewizji bazowej `60a99ddc180f19225e951acd158ae7590360267e`; kontynuacja: PLF-002.
Wszystkie 37 nowych testów UX zaliczono (26 jednostkowych i 11 przeglądarkowych).
Przykład `examples/ux-lab` przez HTTP wykazał 3 naruszenia dla `?broken=1`
i 0 dla poprawnego wariantu; manifesty obu przebiegów zweryfikowano.
Zbudowano wheel/sdist i sprawdzono ich metadane przez Twine. Kontrola dokumentu
przypiętym checkerem wellmanifest/docs 0.1.0 przeszła lokalnie.

W tej pierwszej weryfikacji pełny zestaw nie był zielony z powodu timeoutu. Lokalna konfiguracja
chronionego Validatora nie zawiera `semcod/testwins`, a repozytorium nie deklaruje
OneDev. Przypięcie dokumentacji i lokalne testy nie oznaczają wdrożonej bramy
CI ani zgody na samodzielne scalenie.

### Ponowna weryfikacja przed publikacją: wersja 2

Dołączono istniejące poprawki lokalnego `main` do `ea1be8b`, w tym poprawę
stabilizacji zrzutów oraz test pobrania z jednoznacznym `window.URL`.
Po połączeniu na rewizji wskazanej w metadanych wszystkie 19 testów
przeglądarkowych przeszło; timeout zapisany w PLF-002 już nie występuje.

Przebieg GitHub Actions `35916094359` wykazał trzy błędy `ModuleNotFoundError:
cv2`. Workflow instalował zależności bez dodatku `cv`, choć wykonywał testy
OpenCV. Krok instalacji jednostkowej teraz jawnie obejmuje `cv`, a kontrola
JavaScript sprawdza również `ux_probe.js`. Zachowano wszystkie testy i bramki.

Po uzupełnieniu zależności w odizolowanym środowisku zaliczono wszystkie
280 testów jednostkowych bez pominięć. Rzeczywiście zainstalowany TestQL 1.2.66
wykonał trzy kroki scenariusza `shell-smoke` z wynikiem `passed`.
Wheel/sdist, Twine i kontrole składni również przeszły. To dowody lokalne;
wyniki GitHub i zatwierdzenie publikacji należy obserwować dla wypchniętego HEAD.

Chroniony preflight nadal zwraca `PUBLICATION_PROFILE_MISSING`; watchdog
publikacji również klasyfikuje PR #2 jako `unregistered`. Wymagane jest
niezależne przyjęcie profilu, a następnie walidacja dokładnego HEAD i wyniku
scalenia. Lokalny sukces testów nie usuwa tej blokady (kontynuacja PLF-003).

### Geometria celów dotykowych: wersja 3

Publikację wersji 2 zakończono 2026-09-24: niezależny Validator scalił
[profil #582](https://github.com/subactor/validator-agent/pull/582) i
[Testwins #2](https://github.com/semcod/testwins/pull/2). Profil wymaga
`unit` i `browser`; zastosowano go w osobnym wywołaniu z przypiętym hashem.
Nie oznacza to wdrożenia aplikacji ani usunięcia luk w audycie.

PLF-004 poprawia `TW-TARGET-SMALL`. Poprzednio próg porównywano z aktualnie
widocznym fragmentem: przycisk o wysokości 28 px przy krawędzi przewijanego
menu mógł mieć widoczne 15 px i zostać zgłoszony jako mały. Kolektor zapisuje
teraz `targetSize`: rozmiar ograniczony przez geometrię kontrolki, istniejące
zakresy przewijania oraz obszary przycinania. Pomiar nie przewija dokumentu.
Uwzględnia obie osie, bieżące przesunięcie i poziomy kierunek RTL.

Małe przyciski, trwałe przycięcie `hidden`/`clip`, nieosiągalna ujemna pozycja
oraz zbyt małe okno przewijania nadal dają kandydata. Elementy `fixed`,
`sticky` lub transformowane, także przez przodka, zachowują ostrożny pomiar
widocznego fragmentu. Starsze zrzuty bez `targetSize` również zachowują
dotychczasowe zachowanie. Szczegóły zgłoszenia zawierają `target_size`,
`visible_size` i metodę pomiaru. Test trafienia oraz prostokąty dowodów nadal
dotyczą aktualnie widocznego obszaru; większy wymiar nie unieważnia zasłonięcia.

To oszacowanie geometrii, nie dowód osiągalności każdej pozycji po przewinięciu:
scroll-snap, skrypty przechwytujące gesty i zmiana układu po przewinięciu
wymagają osobnych podróży. Reguła nadal nie ocenia wyjątków odstępu między
celami ani kompletnej zgodności WCAG. Otwarte menu może celowo zakrywać
kontrolki pod nim; sam poprawny rozmiar nie usuwa takich zgłoszeń.

Przypadki renderera obejmują przewijanie pionowe i poziome, dokument,
zagnieżdżone przycinanie, małe okno przewijania, rzeczywiście mały przycisk,
pozycję `fixed`, ujemne przepełnienie, już przewinięte panele i RTL.
Negatywne przypadki sprawdzają również zachowanie wykrywania zasłonięcia.
Aktualny audyt c2004 jest kontynuacją jego napraw PLF-2545/2546;
historyczne 61 naruszeń nie opisuje już aktualnego frontendu.

Weryfikacja 2026-09-24: 281 testów jednostkowych i 33 przeglądarkowe przeszły.
Wśród nich jest 14 przypadków nowej geometrii; cztery scenariusze przewijania
odtworzyły błąd przed poprawką. C2004 obserwowano lokalnie na porcie 8100,
bez własnych zmian kodu aplikacji i bez nowych wykluczeń. Checkout na starcie
miał `38fd71687650f7250c4f59837f14d78ddaf00a6c`, a przy zakończeniu
`606760685aded23858ebd7ec0d3cda47ef1b3f30`: cudze commity zmieniły dokumentację
sprzętu i lock kontraktu, bez zmian frontendu. We wszystkich pięciu usuniętych
zgłoszeniach geometria pozostała taka sama: pełne 370×28 px, widoczne 370×15 px.

| Przebieg C2004 | Kroki zaliczone | Kandydaci | Potwierdzone |
|---|---|---|---|
| Przed: menu myszą/dotykiem | 12/12 | 15, w tym 5 małych celów | 0 |
| Po: menu myszą/dotykiem | 12/12 | 10, wszystkie zasłonięcia | 0 |
| Po: menu klawiaturą | 4/4 | 2 zasłonięcia | 0 |

Identyfikatory raportów: `2026-09-24T072635-051Z-def310d5` (przed),
`2026-09-24T073303-277Z-5992bffe` (po),
`2026-09-24T073527-976Z-3c31d9ff` (klawiatura).
Wszystkie bramki tych przebiegów nadal mają status `incomplete` z powodu
niestabilnych obserwacji. Nie dodano pokrycia wnętrza iframe ani automatycznego
rozstrzygania, czy zakrycie tła przez menu jest zamierzone.

### Stabilność obserwacji i dowodów: wersja 4

PLF-005 rozdziela stabilność geometrii, stanu detektorów i zebranej treści.
Próba na C2004 odtworzyła fałszywe `unstable_layout`: zmienił się wyłącznie
tekst zegara `#bottom-time`, przy identycznych 824 węzłach oraz geometrii
103 zakresów tekstu. Licznik czasu nie oznacza sam w sobie ruchu układu.

Nowy pomiar uwzględnia prostokąty elementów i zakresów tekstu, widoczne
fragmenty, rozmiary celów, maski, przewinięcie oraz viewport. Wcześniejszy
pomiar pomijał ruch tekstu wewnątrz nieruchomego rodzica i zmianę przycięcia.
Porównanie stanu dodatkowo obejmuje wyniki trafień, warstwy zasłaniające,
fokus, disabled/inert, flagi przycięcia i zebrane style. Równe prostokąty
nie wystarczają, gdy nad kontrolką zmieniła się aktywna warstwa.

`snapshot.json`, wpisy `report.json.snapshots` oraz wynik live zawierają
`stability`: `layout`, `state`, `content`, `attempts` i wersjonowaną metodę.
`stable` wymaga zgodności geometrii i stanu. Zmiana zebranej treści przy ich
zgodności jest raportowana osobno, bez luki `unstable_layout`. Raporty HTML,
Markdown i JSON podają liczniki zmian oraz obserwacji bez takiego pomiaru.
To nie jest potwierdzenie prawidłowości komunikatu, jego związku z kliknięciem
ani stabilności wszystkich pikseli. Nadal potrzebne są asercje treści i UX;
maskowana lub ucięta przez limity treść nie jest w pełni porównywana.

Tryb wsadowy zachowuje jedną ponowną próbę. Każdą klatkę otaczają świeże
obserwacje DOM; zapis pochodzi z końcowej próby także wtedy, gdy pozostaje
niestabilna. Maski obejmują obie pozycje prywatnych elementów zaobserwowane
wokół tej klatki. Nie gwarantuje to zamaskowania niezaobserwowanej pozycji
pośredniej ani pełnej anonimizacji. Live stosuje tę samą ocenę w jednej
próbie, z dotychczasowym odstępem pomiarów. Niestabilna geometria lub stan
nadal uniemożliwiają potwierdzenie naruszeń oraz zaliczenie zakresu pomiaru.

Testy Chromium kontrolują zmianę zegara, przesunięcie samego tekstu,
zasłonięcie bez zmiany wymiarów, przemieszczanie prywatnego elementu
w obu próbach i ustabilizowanie drugiej próby. Sprawdzają końcowy DOM,
maski na rzeczywistym obrazie, wynik bramki, manifest oraz zgodność live.
Żaden z tych przypadków nie wymaga wyłączenia reguły ani wykluczenia selektora.

Pozostałe rozszerzenia: jawny kontrakt celowego zasłonięcia tła przez otwarte
menu oraz obserwacja wnętrza ramek. Ta poprawka nie dodaje takiego pokrycia
ani nie uznaje istniejących zasłonięć automatycznie za poprawne.

Weryfikacja 2026-09-24: 296 testów jednostkowych i 40 przeglądarkowych
zaliczonych, bez pominięć w wybranych zestawach. Pięć z sześciu początkowych
regresji geometrii nie przechodziło na bazie. Przypięty checker dokumentacji
również przeszedł.

| C2004: scenariusz | Kroki | Niestabilne zrzuty przed → po | Wynik po |
|---|---|---|---|
| Menu myszą/dotykiem, 3 urządzenia | 12/12 | 27/30 → 1/30 | incomplete; 10 powtarzalnych zasłonięć |
| Menu klawiaturą, desktop | 4/4 | 9/10 → 0/10 | failed; 2 powtarzalne zasłonięcia |

Nowe raporty: `2026-09-24T080625-411Z-2d2513a0` i
`2026-09-24T080809-746Z-56b8f22f`. Porównanie korzysta z poprzednich raportów
wersji 3 wymienionych wyżej; wszystkie cztery manifesty zweryfikowano.
W nowych pomiarach treść zmieniła się odpowiednio w 25/30 i 8/10 klatek.
Jedna końcowa obserwacja po zamknięciu menu nadal zmieniała geometrię i stan;
pozostaje luką. Zasłonięcia nie zniknęły: stabilne dowody pozwalają teraz
potwierdzić ich powtarzalność. Nie rozstrzyga to intencji otwartego menu.
Nie zastosowano wykluczeń i nie ogłoszono zaliczenia całego audytu.

C2004 na końcu pomiaru: `7548feb420fbbde7e3a746fbf69ae1b6b7b9aac3`.
Względem wcześniejszego `6067606` inny wykonawca zmienił testy zdrowia
urządzeń, bez zmian frontendu. Testwins nie modyfikował aplikacji ani jej
wdrożenia. Te podróże obejmują lokalne menu na porcie 8100, nie wnętrze
poradnika iframe ani pozostałe silniki przeglądarek.


## Wersja 5: jawne kontrakty nakładek (PLF-006)

Operator może zadeklarować relację przycisku, nakładki i konkretnych kontrolek tła:

```yaml
overlays:
  - id: language-menu
    trigger: '#language-trigger'
    overlay: '#language-menu'
    background: ['.role-select', 'button[data-key]']
```

Kontrakt obejmuje obserwacje całej konfiguracji. Używaj go w scenach, w których
te elementy istnieją, i ustaw `capture.ready_selector` na stan gotowy do interakcji.
Przycisk i nakładka muszą pasować pojedynczo, a `aria-controls` przycisku wskazywać
unikalne ID nakładki. Stan `aria-expanded` musi odpowiadać widoczności nakładki.
Przycisk pozostaje widoczny, dostępny i trafialny; aktywna nakładka nie może być
`inert` ani `aria-hidden`. Selektory tła wskazują kontrolki, nie kontenery, i nie
mogą obejmować przycisku lub wnętrza nakładki. Limit wynosi 16 kontraktów,
16 selektorów tła i 128 dopasowanych kontrolek na kontrakt.

`TW-CONTROL-OCCLUDED` nie powstaje dla takiej kontrolki tylko wtedy, gdy wszystkie
jej zasłonięte punkty faktycznie trafiają w zadeklarowaną aktywną nakładkę lub jej
potomków. Inny element nad menu, kontrolka spoza listy, wadliwy stan zamknięcia
oraz problemy wewnątrz menu nadal podlegają detekcji. Nieweryfikowalna relacja
produkuje `TW-OVERLAY-CONTRACT` i lukę `overlay_contract`; pojedyncza taka
obserwacja wystarcza, aby bramka nie zaliczyła zakresu. Nie wyłącza zwykłych reguł. Kontrakt nie zmienia
reguł nakładania tekstu, geometrii, masek ani oceny stabilności. Obejmuje dokument
główny; nie rozszerza pokrycia ramek ani zamkniętego Shadow DOM.

JSON zachowuje `overlay_observations` ze stanem, selektorami, trafieniami,
powtórzeniem, stabilnością i ścieżką dowodu. HTML/Markdown pokazują licznik
zamierzonych zasłonięć osobno od naruszeń i wykluczeń. Niestabilne obserwacje nie
wchodzą do licznika stabilnych zasłonięć. Zmiana relacji wokół zrzutu unieważnia
stabilność stanu również w trybie live.

Kontrakt nie dowodzi, że menu daje się zamknąć. Podróż musi otworzyć i zamknąć
menu, sprawdzić `aria-expanded` oraz oczekiwany fokus przez `ux.focus`.
Konfiguracja klawiaturowa C2004 sprawdza Enter, fokus wybranego języka, Escape
i powrót do przycisku. Wymaga wdrożenia poprawionego menu C2004; starsza aplikacja
bez `aria-controls` ma otrzymać błąd, a nie automatyczne wykluczenie zasłonięć.

Walidacja zakresu silnika: 308 testów jednostkowych i 56 przeglądarkowych Chromium.


## Wersja 6: jawne wnętrza iframe (PLF-007)

Konfiguracja wybiera ramkę, scenariusz włącza ją do obserwacji, a krok wskazuje
kontekst swoich selektorów i asercji:

```yaml
frames:
  - id: guide
    selector: iframe.connect-help-frame
journeys:
  - id: guide
    path: /connect-help-oql-poradnik?lang=pl
    frames: [guide]
    steps:
      - id: commands
        frame: guide
        action: click
        selector: '.toc a[href="#commands"]'
        allow_mutation: true
        expect:
          kind: url
          value: '#commands$'
```

Obsługiwany jest jeden poziom iframe tej samej domeny, z jednoznacznym
selektorem, załadowanym dokumentem, bez transformacji i w pełni widoczny
w oknie nadrzędnym. Maksymalnie osiem definicji. Lista `allowed_origins`
zezwala na żądania sieciowe, ale nie rozszerza uprawnień odczytu wnętrza ramek.
Ramki z obcej domeny, nieprzezroczyste sandboxy, ramki prywatne, zasłonięte,
przycięte, przemieszczające się podczas zrzutu i brakujące otrzymują
`frame_unavailable`. Zagnieżdżone iframe wybranego dokumentu pozostają
zamaskowane z luką `frame_nested`. Obie luki blokują zaliczenie wybranego
zakresu. Pozostałe niewybrane iframe nadal mają jawną lukę informacyjną.

Migawka rodzica zawsze maskuje piksele ramek, także po przekroczeniu limitu
obserwowanych elementów. Osobny zrzut wnętrza maskuje jego pola prywatne
według `capture.mask_selectors`. Skrypt nie zapisuje surowego obrazu przed
maskowaniem. Dowody dziecka znajdują się w podkatalogu `frames/<id>` i mają
`scope.kind: frame`, identyfikator, selektor oraz prostokąt w rodzicu.
Prostokąty detektorów i anotacje pozostają w lokalnych współrzędnych iframe.
Geometria osadzenia uczestniczy w ocenie stabilności; identyfikatory etapów
odróżniają identyczne selektory w rodzicu i dziecku.

Kliknięcie, dotyk, klawiatura, wypełnianie i wybór używają wejścia Playwright
w obrębie wybranego Frame. Nie wysyłają lokalnych współrzędnych do sesji CDP
rodzica ani nie wywołują aplikacyjnego `element.click()`. Asercje selektorów
oraz URL dotyczą tego samego dokumentu. `goto`, pobieranie plików i kontrakty
czasowe `ux` wewnątrz ramek pozostają nieobsługiwane i są odrzucane już przy
walidacji konfiguracji. Pomiar CDP wydajności dotyczy rodzica; kontrakty
nakładek i wyrównania z rodzica nie są automatycznie przenoszone do dziecka.
Axe bada każdą wybraną powierzchnię oddzielnie, bez rekurencji do innych ramek.

To ograniczona obserwacja aktualnego viewportu iframe, a nie pełne przejście
całej jego przewijanej treści. Ocena zasłonięcia osadzenia korzysta z pięciu
punktów hit-test; nie jest analizą wszystkich pikseli i efektów kompozytora.
Kompletność skonfigurowanego zakresu nie oznacza poprawności całej aplikacji.

Gotowy scenariusz C2004: `configs/c2004/frames.yaml`. Audyt czterech tras
`configs/c2004/audit.yaml` również wybiera ramkę przewodnika. Dla DisplayNet
należy podać `--url` z aktualnie zweryfikowanym adresem wdrożenia.


Weryfikacja PLF-007: 318 testów jednostkowych bez pominięć; 22 testy wybranego
zakresu ramek, w tym wejście myszy i dotyku, osobne współrzędne, prywatne dane,
obca domena, sandbox, niejednoznaczny selektor, zagnieżdżenia i limit DOM.
Pełny przebieg przeglądarkowy: 67 zaliczonych, jeden błąd istniejącego testu
obserwatora live; jego osobne powtórzenie przeszło. Wynik CI dla publikowanego
commita pozostaje osobnym dowodem.

Pierwsze rzeczywiste przebiegi C2004 (`2026-09-24T113609-698Z-ce1fab12` lokalnie,
`2026-09-24T113815-665Z-199dc45a` na DisplayNet) wykonały po 4/4 kroków desktopu.
Oba potwierdziły `TW-TEXT-OVERLAP` w ramce po przejściu do `#commands`:
przyklejony pasek „Drukuj / zapisz do PDF” zakrywa nagłówek. Przecięcie wynosi
174,72 × 9,30 px; dowody z dwóch powtórzeń są stabilne, a obraz potwierdza
zasłonięcie. Jest to znalezisko aplikacji, nie powód do wyłączenia detektora.

Tablet i telefon otrzymały brak pokrycia z powodu częściowo przyciętego
osadzenia, którego ta wersja nie interpretuje jako pełnej powierzchni iframe.
Raporty pozostają `incomplete`. Także początkowe ładowanie ramki zachowano
w pierwszych dowodach; finalny runner czeka na gotowość rodzica przed próbą
obserwacji dziecka. Nie zmieniono kodu ani wdrożenia C2004 w PLF-007.
