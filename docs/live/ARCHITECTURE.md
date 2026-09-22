# Testwins Live 0.3 — architektura diagnostyki GUI

## Cel i granice

Obserwator działa na wyrenderowanym interfejsie, nie wymaga wiedzy o React, Vue,
Angular, PHP, Django, Rails ani backendzie. „Niezależny od technologii” oznacza wspólny
kontrakt obserwacji; nie oznacza identycznej głębokości dostępu do HTML, canvas,
natywnego okna, zamkniętego Shadow DOM i aplikacji na iOS.

Katalog [92 klas](GUI_TAXONOMY.md) to analiza ryzyka, nie obietnica 92 detektorów lub
wszystkich możliwych defektów. Obejmuje układ, warstwy, responsywność, typografię,
obrazy/media, dostępność, formularze, nawigację, stany dynamiczne, spójność oraz
GUI natywne i luki obserwacji. 18 pozycji katalogu ma przypisane reguły TW-*;
poszczególne wyniki mogą być kandydatami. Pozostałe wymagają kontraktu, axe,
modelu wizyjnego albo testu specjalistycznego. Osobne reguły natywne dotyczą
zmiany pikseli i jawnego dopasowania wzorca.

```
Jawny manifest stron / regionów pulpitu
    → kolejka terminów + zmiany plików + ograniczone gorące strony
    → sterownik zasobów → izolowane konteksty / MSS
    → wyrenderowany DOM, zakresy tekstu, hit-test, screenshot
    → detektory + kontrakty + hipotezy przyczyn
    → trwały cykl życia incydentu w SQLite
    → JSON na stdout + SSE + lokalny panel
    → niezmienny eksport dowodów → propozycje Planfile → świadoma publikacja

Oddzielna, ograniczona kolejka:
    zaobserwowany problem → opcjonalne CV → opcjonalny LiteLLM
                                      → niepotwierdzony kandydat
```

## Trzy niezależne skale

**Wpływ** opisuje konsekwencję, nie pewność: critical → P0, high → P1,
normal → P2, low → P3. P0 należy nadać jawnie krytycznemu kontraktowi, np. brakowi
istotnego elementu; detektor nie zna ekonomicznych skutków transakcji. Zdarzenia
informacyjne i luki pokrycia nie dostają sztucznego P0. `priority: 0..4` celu jest
natomiast priorytetem planowania, nie oceną znalezionego błędu.

**Status dowodu**: `observed` → `confirmed` po wymaganych porównywalnych pomiarach;
`candidate` pozostaje kandydatem nawet po tysiącu powtórzeń. `resolved` oznacza
powtarzalny brak tej reguły w tym samym pokrytym zakresie, nie dowód naprawienia
wszystkich stanów aplikacji. Brak skanu, timeout, pominięty detektor, zmiana zakresu
lub niewystarczający poziom analizy nie są czystym pomiarem. Luka przerywa serię
potwierdzeń i serię czystych pomiarów, ale nie zamyka incydentu.

**Koszt analizy**:

| Warstwa | Rzeczywiste działania | Czego nie dowodzi |
|---|---|---|
| L0 | Uruchomienie/odświeżenie celu, sygnał obecności obserwatora | Brak testów GUI; status `limited` |
| L1 | Stabilność geometrii, DOM/CSS, tekst, hit-test, screenshot, kontrakty tylko do odczytu | Pełna logika biznesowa, wszystkie stany strony |
| L2 | L1 + zmiana pikseli, opcjonalne axe i pochodzenie CSS; osobny worker CV | Że zmiana obrazu jest błędem lub region YOLO jest defektem |
| L3 | L2 + opcjonalna analiza obrazu przez LiteLLM, po lokalnym sygnale i przejściu limitów | Automatyczne potwierdzenie modelu, przyczynowość w kodzie |

L1 także tworzy screenshot: to nie jest bezkosztowy ping. Ustawienie `max_tier`
ostanawia sufit; nie wymusza wykonania wszystkich opcjonalnych bibliotek. axe, CV
i LLM są domyślnie wyłączone w lekkich manifestach. Wariant noVNC wymaga axe.
Poza nową pętlą pozostają dostępne pełne audyty `run` oraz zadania TestQL, shell,
PTY i GUI z wersji 0.2. Live nie wykonuje automatycznie mutujących scenariuszy.

## Diagnoza przyczyn — model dowodów, nie zgadywanie plików

Dla objawu są zbierane: selektor, prostokąt, zakres tekstu, pozycja przodka,
whitelistowane computed styles, scroll size oraz warstwa zasłaniająca kontrolkę.
Z tego powstają uszeregowane **hipotezy**, z przesłankami, próbą rozstrzygającą
i kierunkiem naprawy. `support_score` jest niekalibrowanym wsparciem heurystyki,
a nie prawdopodobieństwem. Osobny `confidence` detekcji również nie jest
obietnicą statystycznie skalibrowanej dokładności.

Przykład: tekst poza viewportem + rodzic flex/grid + `min-width:auto` + `nowrap`
→ hipoteza ograniczenia min-content. Proponowana próba: w kopii kontrolowanego
stanu zmienić pojedyncze ograniczenie szerokości i powtórzyć pomiar. Silnik NIE
wykonuje automatycznie tych zmian CSS i NIE przypisuje błędu do backendu.

`diagnostics.css_provenance: true` włącza dodatkowy odczyt przez CDP CSS.
`getMatchedStylesForNode` daje dopasowane deklaracje, selektor, URL serwowanego
arkusza i dostępną linię. To nie jest pełny algorytm zwycięskiej kaskady,
mapowanie do SCSS/TSX przez source map ani dowód, że wskazany plik jest przyczyną.
Firefox/WebKit i nieobsługiwane selektory pokazują ograniczenie, nie wymyślone dane.

Obserwacja plików służy tylko do uruchamiania skanów: metadane mtime/size,
nie zawartość źródeł. Bliskość czasowa zapisu i defektu nie jest przypisaniem winy
commitowi. `source_globs` jest jawną mapą operatora, nie wyuczoną zależnością.

## Incydenty, zakres i dowody

Klucz komórki: witryna + trasa + przeglądarka + profil. Odcisk zakresu obejmuje
adres, kontrakty, parametry audytu i region/maski pulpitu. Zmiana konfiguracji
nie zamyka automatycznie wcześniejszych wyników. Incydenty deduplikują regułę,
selektory i rozróżnienie kontraktu w obrębie komórki. Eksport grupuje porównywalne
komórki tej samej trasy; nie próbuje odgadywać jednej wspólnej przyczyny dla
całego portalu.

Każdy pomiar ma osobny katalog `evidence/scan-*` ze screenshotem, adnotacjami,
snapshotem, lokalnym semantycznym HTML, rezultatem i SHA-256. CV/LLM zapisują
osobne `augmentations/review-*`, nie zmieniają manifestu oryginału. Łańcuch SSE
jest trwałą sekwencją SQLite, NIE podpisanym lub odpornym na operatora audytem.
Eksport sprawdza hashe oryginału i kopii. Nie publikuj przypadkowo raportów z
danymi klientów; maskowanie nie gwarantuje usunięcia każdego sekretu.

## Ograniczenia szczegółowe

Nowy monitor sprawdza widoczny viewport i zadeklarowane kontrakty. Nie przewija
automatycznie każdej strony, nie enumeruje wszystkich stanów, nie klika wszystkich
przycisków i nie zarządza logowaniem do każdego portalu. Używa nowych kontekstów,
nie Twojego codziennego profilu. Konta testowe, procedura logowania i rozszerzenia
sterownika muszą być jawnie przygotowane; wykrycie formularza logowania nie
potwierdza przetestowania wnętrza aplikacji.

Zamknięty Shadow DOM, zawartość iframe, canvas, WebGL, wirtualizowane listy,
zmiany poza widocznym obszarem i efekty wyłączonych animacji ograniczają obserwację.
MSS daje piksele, nie semantykę aplikacji natywnej. Pełny Windows/macOS/iOS
potrzebuje odpowiedniego hosta/urządzenia i uprawnień. Nie używaj tego agenta jako
jedynej bramki dostępności lub testu bezpieczeństwa aplikacji.

Źródła kontraktów zewnętrznych (sprawdzone 2026-09-22):
- WUP: https://github.com/semcod/wup
- CDP CSS: https://chromedevtools.github.io/devtools-protocol/tot/CSS/
- WCAG 2.2: https://www.w3.org/TR/WCAG22/
- LiteLLM vision: https://docs.litellm.ai/docs/completion/vision
- Playwright Docker: https://playwright.dev/python/docs/docker
- MSS: https://github.com/BoboTiG/python-mss
