---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "c2004-displaynet-tests",
  "kind": "analysis",
  "version": 1,
  "title": "Testwins: testy C2004 lokalnie i na DisplayNet",
  "status": "accepted",
  "owner": "semcod/testwins",
  "created": "2026-09-24",
  "updated": "2026-09-24",
  "review_after": "2026-10-24",
  "source_revision": "c6a17bd1f56e6570d6952e5c5330c8a126f11a84",
  "affected_repositories": [
    "semcod/testwins"
  ],
  "evidence": [
    "repo://semcod/testwins/configs/c2004/ux.yaml",
    "repo://semcod/testwins/configs/c2004/keyboard.yaml",
    "repo://semcod/testwins/configs/c2004/audit.yaml",
    "repo://maskservice/c2004/frontend/tests/playwright/responsive-shell.spec.ts",
    "receipt:sha256:2381e04005735414aad003d0fb19e1b45267b58f6cf15d857fa02e1fa222b7a2"
  ]
}
---

# Testwins: C2004 i DisplayNet — PLF-008

<!-- docs:section question -->
## Pytanie i wynik

Czy bieżące interfejsy C2004 na lokalnym hoście i DisplayNet przechodzą
scenariusze obsługi oraz kontrole układu? Na obu panelach przeszło po
**16/16 kroków interakcji** i **9/9 testów responsywności oraz poradnika iframe**.
Pełny audyt Testwins nie jest zaliczony: otwarte menu zasłania kontrolki,
a część obserwacji układu pozostaje niestabilna. Nie wykluczono żadnej reguły.

<!-- docs:section scope -->
## Zakres

Raport dotyczy wykonania Testwins na jednej aplikacji docelowej, w dwóch
wdrożeniach. Właścicielem konfiguracji i tego wyniku jest semcod/testwins;
naprawy kodu aplikacji i diagnostyka sprzętu pozostają w maskservice/c2004.
Nie zmieniano źródeł C2004, nie wdrażano aplikacji i nie wydawano poleceń
sterowania, restartu ani aktualizacji urządzeń. Trwające zadania sprzętowe
PLF-2503/2537 i cudze zmiany zachowały swoich właścicieli.

Obserwator: stacja robocza Testwins. Badane adresy: lokalny
`http://127.0.0.1:8100` oraz DisplayNet `http://192.168.188.116:8100`.
Adres DisplayNet ustalono przez aktualne rozwiązanie `displaynet.local`,
nie przez historyczny adres z raportu. Lokalny rejestr discovery na porcie
8188 nie odpowiadał; nie posłużył do potwierdzania tożsamości sprzętu.
Badania trwały 24 września 2026, około 08:20–08:29 UTC.

<!-- docs:section method -->
## Metoda

Testwins używa rewizji wskazanej w metadanych; checkout C2004 miał
`7548feb420fbbde7e3a746fbf69ae1b6b7b9aac3`. Nie jest to dowód rewizji
uruchomionych kontenerów. Porównano HTTP i hashe faktycznie serwowanych
zasobów: oba panele miały ten sam index, główny pakiet JavaScript
`index-askH_i_G.js` i `startup-guard.js`, lecz różne `config.js`.
Index pozostał identyczny na końcu badania. Nie potwierdzono zgodności
wszystkich modułów dynamicznych, backendów ani firmware.

Przeglądarka działała na stacji roboczej, łącząc się z badanym frontendem.
Użyto Chromium, rozmiarów 1440×900, 820×1180 i 390×844 oraz dwóch
powtórzeń Testwins. Tablet i telefon są emulowane. Dwa środowiska badano
równolegle; scenariusze wewnątrz każdego środowiska wykonywano kolejno.
Pomiar reakcji nie jest benchmarkiem izolowanego urządzenia ani metryką INP.

Scenariusze:

- `ux.yaml`: otwarcie i zamknięcie menu języka myszą/dotykiem, reakcja,
  feedback, zmiana wizualna i budżet animacji; 12 kroków na środowisko.
- `keyboard.yaml`: otwarcie i zamknięcie tego menu klawiszem Enter,
  desktop; 4 kroki na środowisko.
- `audit.yaml`: użytkownicy, urządzenia, raport tygodniowy i poradnik OQL;
  24 obserwacje na środowisko, bez dodatkowych asercji funkcjonalnych.
- Istniejący `responsive-shell.spec.ts`: geometria powłoki i diagnostyki,
  wielkość celów, napis Enter oraz przejście do sekcji Commands wewnątrz
  iframe; po trzy przypadki dla telefonu, tabletu i desktopu.
- 34 lokalne testy jednostkowe: granice naprawy runtime DisplayNet, kontrola
  statusów HTTP scenariusza sprzętowego i audyt adresowania. To testy z
  atrapami/serwerem testowym, nie test ruchu fizycznego sprzętu.

Konfiguracja Playwright odnalazła także dziewięć przypadków z archiwalnej
kopii tego samego pliku w `.subactor/sessions/`. Była bajtowo identyczna;
wszystkie te wykonania również przeszły, ale nie zwiększają liczby dziewięciu
unikalnych przypadków na środowisko. Nie uruchomiono drugiego watchera wup.
`wup health --failed-only` zwrócił pusty stan; nie dowodzi to pełnego
monitorowania ani gotowości sprzętu.

<!-- docs:section evidence -->
## Dowody

Sześć manifestów Testwins zweryfikowano przez `verify_run`. Hashe służą do
wykrywania zmian plików, nie stanowią podpisu autora ani niezależnego pomiaru.
Surowe raporty, DOM, obrazy i logi pozostają lokalnie w
`artifacts/c2004-displaynet-tests/` i `.subactor/recovery/ticket-008/`.
Zbiorczy `summary.json` jest związany hashem w metadanych; zawiera hashe
każdego raportu i manifestu, użyte wersje, kontrole HTTP i wyniki Playwright.

| Środowisko | Scenariusz | Identyfikator przebiegu |
|---|---|---|
| local | ux | `2026-09-24T082152-740Z-cb5aac88` |
| local | keyboard | `2026-09-24T082412-336Z-66620095` |
| local | audit | `2026-09-24T082509-838Z-19f3b08c` |
| displaynet | ux | `2026-09-24T082154-131Z-9ff2ccfe` |
| displaynet | keyboard | `2026-09-24T082340-533Z-b6eca7cf` |
| displaynet | audit | `2026-09-24T082419-170Z-f56d18ae` |

<!-- docs:section facts -->
## Wyniki

| Środowisko | Scenariusz | Kroki zaliczone | Powtarzalne zgłoszenia | Niestabilne zrzuty | Bramka |
|---|---|---|---:|---:|---|
| local | ux | 12/12 | 10 | 1/30 | incomplete |
| local | keyboard | 4/4 | 2 | 1/10 | incomplete |
| local | audit | brak kroków | 0 | 4/24 | incomplete |
| displaynet | ux | 12/12 | 10 | 0/30 | failed |
| displaynet | keyboard | 4/4 | 2 | 0/10 | failed |
| displaynet | audit | brak kroków | 0 | 5/24 | incomplete |

Wszystkie zgłoszenia dotyczą `TW-CONTROL-OCCLUDED` przy otwartym menu
języka — po otwarciu oraz przed jego zamknięciem. To powtórzenia stanów,
nie dwanaście odrębnych przyczyn na środowisko. Zrzut desktopu DisplayNet
potwierdza nałożenie listy języków na klawisz ekranowej klawiatury.
Sama powtarzalność nie rozstrzyga, czy zasłonięcie tła jest błędem produktu.
Nie znaleziono naruszeń w statycznych audytach czterech widoków, lecz ich
niestabilne próbki nadal blokują zaliczenie. Każdy audyt zapisuje także
sześć luk dotyczących wnętrza iframe. Osobne testy poradnika pokrywają
konkretną nawigację i przepełnienie, nie całe wnętrze dowolnej ramki.

| Środowisko | Wejście | Reakcja: min / mediana / max [ms] | Maks. feedback [ms] |
|---|---|---|---:|
| local | ux | 12.2 / 30.8 / 127.1 | 37.4 |
| local | keyboard | 19.6 / 24.4 / 174.4 | 6.7 |
| displaynet | ux | 9.6 / 27.5 / 126.2 | 42.4 |
| displaynet | keyboard | 12.4 / 41.0 / 52 | 12.9 |

Jedna seria odczytów HTTP około 08:21:49 UTC uzyskała 8/8 odpowiedzi 200:
po `/health` oraz trzy odczyty sprzętu na środowisko. Dla health sprzętu
oba panele zwróciły `runtime=stacknet`, `mode=real`,
`transport_reachable=true`, `overall_ok=true`; status Tica i pakiet czujników
zwróciły `ok=true`. Odczyty miały jawny wybór StackNet. Wynik opisuje te
konkretne próbki, nie długotrwałą stabilność komunikacji ani test peryferiów
pod obciążeniem. Nie zmieniano receiptu aktywnego urządzenia.

<!-- docs:section hypotheses -->
## Interpretacja

Zasłonięcie klawiatury przez otwarte menu może być zamierzonym zachowaniem
warstwy. Do automatycznego rozstrzygnięcia potrzebny jest jawny kontrakt
aktywnego menu, obszaru tła oraz powrotu do działania po zamknięciu.
Niestabilność pozostałych zrzutów wymaga porównania kolejnych stanów;
nie uznano jej automatycznie za kolejną zmianę samych sekund zegara.

<!-- docs:section limitations -->
## Ograniczenia

Zakres nie obejmuje logowania, CRUD, wszystkich ról/języków, rzeczywistego
kiosku i dotyku DisplayNet, innych silników przeglądarki ani uruchamiania
sprzętu. Axe było wyłączone w zastanych konfiguracjach; nie deklarujemy
pełnego audytu dostępności. Testwins nie analizuje wnętrza iframe w tym
trybie, canvas ani zamkniętego shadow DOM. Pomiary pochodzą ze współdzielonego,
czynnego środowiska. Nie zastosowano suppressions, masek zegara, nowych
baseline ani zmian reguł w celu uzyskania pozytywnego wyniku.

<!-- docs:section recommendations -->
## Odtworzenie i dalsze działania

Wersjonowane konfiguracje odpowiadają faktycznie wykonanym scenariuszom;
znormalizowano tylko nazwę projektu i domyślny adres lokalny. Adres zdalny
należy potwierdzić przy kolejnym uruchomieniu i przekazać przez `--url`:

```bash
C2004_TEST_URL=http://displaynet.local:8100
python -m testwins run --config configs/c2004/ux.yaml --url "$C2004_TEST_URL" --output artifacts/c2004/ux
python -m testwins run --config configs/c2004/keyboard.yaml --url "$C2004_TEST_URL" --output artifacts/c2004/keyboard
python -m testwins run --config configs/c2004/audit.yaml --url "$C2004_TEST_URL" --output artifacts/c2004/audit
```

PLF-006 przechowuje kontrakty celowego zasłonięcia przez menu i weryfikację
odzyskania stanu po zamknięciu; PLF-007 przechowuje rozszerzenie obserwacji
ramek. Ten przebieg dostarcza nowe dowody, bez konkurencyjnej implementacji
tych funkcji. Wyniki sprzętowe pozostają osobno w aktywnym zadaniu C2004.
