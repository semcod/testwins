# Katalog klas błędów GUI

92 klas ryzyka i luk obserwacji. **To nie jest 92 zaimplementowanych detektorów.** Nie ma skończonego katalogu wszystkich błędów dla wszystkich stanów aplikacji.

`TW-*` oznacza implementację detektora (część wyników to kandydaci). `contract`: potrzebny jawny scenariusz TestQL/Testwins; `axe`: opcjonalny asset axe-core; `vision`: zadanie CV/LLM lub przegląd człowieka, nie dedykowany klasyfikator; `manual`: test specjalistyczny/ręczny; `gap`: luka pokrycia, nie wada aplikacji.

Kandydat nie staje się potwierdzonym defektem przez samo powtórzenie. Hipoteza przyczyny nie jest przypisaniem winy do pliku/commitu.

## layout

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Nachodzenie tekstu | absolute/fixed poza przepływem; ujemny margines; transformacja; zbyt ciasny line-height | Wyłącz pojedynczo podejrzane transformacje/pozycjonowanie w kopii widoku i zmierz przecięcie ponownie. | `TW-TEXT-OVERLAP` |
| Obcięty tekst | overflow hidden/clip; ograniczenie wysokości; zbyt długi tekst | Sprawdź przycinających przodków i porównaj ich clientHeight z zakresem tekstu. | `TW-TEXT-CLIPPED` |
| Poziomy scroll całego dokumentu | min-content flex/grid; szeroki element; stała szerokość; błąd viewportu | Zidentyfikuj pierwszy element poza viewportem; sprawdź min-width i łamanie tekstu. | `TW-VIEWPORT-OVERFLOW` |
| Nierówne krawędzie | margin/padding/gap; baseline; border-box; różny rozmiar fontu | Porównaj deklarowany kontrakt krawędzi w tych samych współrzędnych. | `TW-ALIGNMENT` |
| Odchylenie wyrównania rodzeństwa | celowy akcent lub odmienne odstępy elementu | Najpierw potwierdź zamiar projektowy; dopiero potem utwórz kontrakt. | `TW-ALIGNMENT-CANDIDATE` |
| Niespójne odstępy | różne tokeny; margin collapsing; gap z paddingiem | Porównaj odstępy między jednorodnymi elementami. | `contract` |
| Błędna liczba kolumn | breakpoint; minmax; intrinsic size | Sprawdź rozmiary w wąskim sąsiedztwie breakpointu. | `contract` |
| Nadmierne ściskanie kontrolek | flex-shrink; min-width auto; długi tekst | Zmierz rozmiary bazowe i minimalne; test min-width:0 w kopii. | `contract` |
| Sticky zachodzi na treść | błędny scroll ancestor; inset; brak miejsca | Przewiń stronę i porównaj położenie kontrolki względem przodka. | `contract` |
| Pusty render | błąd inicjalizacji; opóźnienie; niewłaściwa trasa; celowo pusta strona | Sprawdź jawny ready selector i oczekiwaną zawartość, bez zgadywania błędu API. | `TW-EMPTY-UI` |

## layers

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Zasłonięta kontrolka | overlay; stacking context; fixed header; pointer interception | Porównaj elementFromPoint w kilku punktach i łańcuch przodków warstw. | `TW-CONTROL-OCCLUDED` |
| Interaktywna kontrolka ignoruje wskaźnik | pointer-events none; stan kontrolki; celowa propagacja | Sprawdź kontrakt aktywności i działanie klawiaturą. | `TW-POINTER-DISABLED` |
| Błędny backdrop | warstwa pod dialogiem/nad dialogiem; pointer-events | Kliknij jawnie dozwolone punkty i sprawdź oczekiwany stan. | `contract` |
| Menu/tooltip przycięty | overflow przodka; portal; top-layer | Sprawdź przycinający element przy otwartym menu. | `contract` |
| Tooltip znika lub zasłania treść | obszar hover nie obejmuje tooltipu; warstwy | Przejdź wskaźnikiem i klawiaturą między wyzwalaczem a treścią. | `contract` |
| Dialog poza ekranem | centrowanie; zbyt duża wysokość; brak scrolla | Sprawdź mały viewport, zoom i widoczność przycisku zamknięcia. | `contract` |
| Obszar kliknięcia niezgodny z obrazem | transform; SVG; przezroczysta warstwa | Porównaj hit-test z konturem wizualnym i kontraktem działania. | `contract` |
| Scroll zablokowany po zamknięciu | nieusunięta blokada body; stan modalu | Otwórz/zamknij dialog i porównaj możliwość przewijania. | `contract` |

## responsive

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Brak meta viewport | pominięta deklaracja; szablon bazowy | Porównaj layout viewport, visual viewport i screenshot. | `TW-VIEWPORT-META` |
| Mały cel dotykowy | padding; zagęszczenie; niewłaściwy wariant mobilny | Sprawdź rozmiar i wyjątki dotyczące odstępu oraz alternatywnej kontrolki. | `TW-TARGET-SMALL` |
| Utrata treści przy zoomie | sztywne rozmiary; clipping; fixed element | Sprawdź reflow i zachowanie funkcji przy powiększeniu. | `contract` |
| Błąd po obrocie | nieprzeliczony stan; media query; viewport units | Zmień orientację i ponów kontrakty widoczności. | `contract` |
| Klawiatura ekranowa zasłania pole | visual viewport; scroll restoration; fixed footer | Przetestuj na rzeczywistym urządzeniu z klawiaturą ekranową. | `manual` |
| Element pod wycięciem ekranu | nieuwzględnione safe-area insets | Sprawdź na docelowym urządzeniu i orientacji. | `manual` |
| Artefakty przy innej skali | zaokrąglenia; raster; canvas backing store | Porównaj DPR przy tej samej geometrii CSS. | `vision` |
| Funkcja wymaga hover na dotyku | niewłaściwy warunek pointer/hover | Wykonaj scenariusz dotykiem bez symulowanego hover. | `contract` |

## typography

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Fonty nie zakończyły ładowania | opóźnienie fontu; deklaracje font-face; fallback | Powtórz pomiar po document.fonts.ready i sprawdź zmianę metryk. | `TW-FONT-PENDING` |
| Bardzo mały tekst | token rozmiaru; transform scale; rem bazowy | Porównaj rozmiar i wymagania interfejsu; to heurystyka, nie certyfikat WCAG. | `TW-TEXT-SMALL` |
| Inny font lub brak glifów | fallback; brak unicode range; niedostępny font | Sprawdź dostępność konkretnego fontu i widoczne glify. | `vision` |
| Za ciasna interlinia | line-height; skrypty pisma; diakrytyka | Porównaj granice kolejnych linii i czytelność znaków. | `vision` |
| Błędy pisma od prawej | fizyczne left/right; kierunek; mieszane liczby | Uruchom osobny stan RTL i sprawdź kolejność logiczną. | `contract` |
| Długie tłumaczenie psuje układ | sztywne rozmiary; brak elastycznego zawijania | Użyj pseudo-lokalizacji i najdłuższych zaakceptowanych etykiet. | `contract` |
| Niepoprawne znaki | kodowanie; podwójne dekodowanie; font | Porównaj tekst DOM z oczekiwanym tekstem. | `contract` |
| Ellipsis ukrywa istotną treść | celowe skracanie bez alternatywy | Sprawdź dostęp do pełnej wartości i jej znaczenie dla zadania. | `manual` |

## assets

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Uszkodzony obraz | nieudane ładowanie/dekodowanie; nieobsługiwany zasób | naturalWidth=0 potwierdza brak obrazu, ale nie rozstrzyga HTTP/CSP/dekodowania. | `TW-IMAGE-BROKEN` |
| Zniekształcony obraz | aspect ratio; object-fit; rozmiary CSS | Porównaj docelowy kadr i oczekiwane proporcje. | `vision` |
| Rozmyty obraz/ikona | niewłaściwy raster lub skalowanie | Porównaj piksele źródłowe i docelowy DPR z referencją. | `vision` |
| Błędna ikona | mapowanie symbolu; font ikon; wariant | Porównaj ikonę z opisanym kontraktem produktu. | `vision` |
| Brak odtwarzania lub sterowania | format; autoplay; kontrolki; zgoda | Uruchom jawny scenariusz odtwarzania w docelowej przeglądarce. | `contract` |
| Błędny canvas/WebGL | rozmiar bufora; kontekst GPU; render loop | Porównaj screenshot i jawny stan; DOM nie widzi wnętrza canvasa. | `vision` |
| Błędna ikona SVG | viewBox; clipping; fill/currentColor | Zbadaj granice widoku i render w jasnym/ciemnym motywie. | `vision` |
| Niewczytane treści po scrollu | intersection threshold; root observer; stan listy | Przewiń do jawnego zakresu i sprawdź oczekiwaną treść. | `contract` |

## accessibility

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Niski kontrast tekstu | kolor; przezroczystość; tło; gradient | Uruchom axe i ręcznie oceń obrazy/gradienty oraz stany. | `axe` |
| Brak nazwy kontrolki | brak label/aria; usunięte powiązanie | Sprawdź nazwę dostępną i zrozumiałość kontekstu. | `axe` |
| Fokus na zasłoniętym elemencie | overlay; brak scrollIntoView; sticky | Zbadaj rzeczywisty fokus i hit-test; dodaj scenariusz klawiaturowy. | `TW-FOCUS-OBSCURED` |
| Fokus wewnątrz aria-hidden | niezsynchronizowany stan dialogu; błędne ukrywanie | Sprawdź aktywny element i aria-hidden w jego przodkach. | `TW-ARIA-HIDDEN-FOCUS` |
| Pułapka klawiaturowa | obsługa Tab/Escape; stan modalu | Wykonaj pełną sekwencję wejścia i wyjścia klawiaturą. | `contract` |
| Nielogiczna kolejność fokusu | tabindex; kolejność DOM vs CSS | Porównaj sekwencję Tab z zadaniem użytkownika. | `contract` |
| Brak wskaźnika fokusu | outline none; niewidoczne style | Sprawdź każdy stan klawiaturowy na screenshotach. | `vision` |
| Niepoprawna semantyka struktur | role; nagłówki; landmarki | Uruchom automatyczne reguły i ocenę semantyki. | `axe` |
| Zmiana nieogłaszana czytnikowi | brak live region; timing; aria-busy | Sprawdź z czytnikiem ekranu w realnym przebiegu. | `manual` |
| Znaczenie tylko przez kolor | brak tekstu/ikony/wzoru | Sprawdź rozróżnialność bez percepcji koloru. | `manual` |

## forms

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Niespełnione oczekiwanie UI | stan aplikacji; błędne powiązanie; asynchroniczność | Odtwórz jawny kontrakt i odróżnij błąd od nieukończonego testu. | `TW-EXPECTATION` |
| Błędna walidacja pola | reguła; format; moment walidacji | Sprawdź zaakceptowane i odrzucone klasy danych. | `contract` |
| Komunikat błędu w złym miejscu | layout; brak powiązania; scroll | Sprawdź położenie i identyfikację konkretnego pola. | `contract` |
| Podwójne wysłanie | brak blokady; retry; obsługa wielu zdarzeń | Sprawdź oczekiwany stan UI; bez API nie potwierdzaj podwójnego zapisu w bazie. | `contract` |
| Utrata wpisanych danych | remount; navigation; reset form | Wprowadź dane testowe, zmień stan i porównaj pola. | `contract` |
| Autofill zmienia czytelność | styl user-agent; typ pola; kontrast | Sprawdź rzeczywisty autofill docelowej przeglądarki. | `manual` |
| Uszkodzone wprowadzanie złożone | composition events; filtrowanie input | Przetestuj rzeczywiste IME i sekwencje composition. | `manual` |
| Błędna aktywność kontrolki | stan formularza; race; disabled/inert | Użyj jawnego kontraktu aktywności dla zestawu danych. | `contract` |

## navigation

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Link prowadzi w złe miejsce | routing; base path; błędny href | Sprawdź docelowy URL/stan po dozwolonym kliknięciu. | `contract` |
| Back/forward psuje stan | history; router; cache | Wykonaj nawigację w obie strony i porównaj stan. | `contract` |
| Nie działa wejście bezpośrednie | fallback serwera; router; auth redirect | Załaduj trasę w nowym kontekście. | `contract` |
| Pętla przekierowań | sesja; warunki routera; konfiguracja | Test kończy się jako niekompletny; nie zgaduj stanu auth bez dowodów. | `contract` |
| Błędne przywrócenie scrolla | history restoration; lazy list | Porównaj pozycję po powrocie do listy. | `contract` |
| Błąd paginacji | indeksy; filtry; stan routera | Zweryfikuj jawne oczekiwania treści między stronami. | `contract` |
| Wyniki niezgodne z filtrem | stan; debounce; nieaktualna odpowiedź | Sprawdź kontrakt wyniku dla kontrolnych danych. | `contract` |
| Znikające/duplikowane wiersze | klucze; recycling; szacowana wysokość | Przewijaj w obie strony i sprawdzaj kontrolne rekordy. | `contract` |

## dynamics

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Układ porusza się podczas pomiaru | animacje; fonty; późna treść; zmiana wymiarów | Porównaj geometrię wokół screenshotu; niestabilny wynik pozostaje kandydatem. | `TW-LAYOUT-UNSTABLE` |
| Zmiana obrazu względem poprzedniego skanu | zawartość dynamiczna; motyw; regresja; zegar | Potwierdź intencję zmiany; poprzedni skan nie jest zatwierdzonym baseline. | `TW-PIXEL-DRIFT` |
| Drżenie elementu | pętla resize/layout; animacje; zaokrąglenia | Porównaj wiele kolejnych klatek; wyklucz oczekiwaną animację. | `vision` |
| Nieskończony stan ładowania | niezamknięty stan; timeout; oczekiwanie na dane | Dodaj czasowy kontrakt zniknięcia loadera. | `contract` |
| Migotanie/FOUT/FOUC | fonty; CSS loading; hydration | Analizuj sekwencję klatek; pojedynczy screenshot nie wystarcza. | `vision` |
| Wyświetlenie nieaktualnego stanu | kolejność zdarzeń; anulowanie; render state | Wykonaj sekwencję szybko zmieniających się dozwolonych działań. | `contract` |
| Ignorowanie ograniczenia ruchu | brak media query; animacja JS | Sprawdź oddzielny profil reduced motion bez sztucznego zamrażania animacji. | `contract` |
| Ryzykowne błyski | częstotliwość; kontrast; animacja | Wymaga analizy sekwencji i specjalistycznej oceny; nie orzeka z pojedynczej klatki. | `manual` |

## consistency

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Błędy jasnego/ciemnego motywu | tokeny; hardcoded color; obrazy bez wariantu | Porównaj te same stany w obu motywach. | `contract` |
| Rozjazd wspólnego komponentu | duplikacja stylów; wersje; tokeny | Porównaj homologiczne komponenty z jawnym kontraktem. | `vision` |
| Różnice między silnikami | CSS support; user-agent styles; rendering | Powtórz tę samą wersję aplikacji i stan w całej macierzy. | `contract` |
| Ucięty wydruk | print CSS; pagination; hidden content | Sprawdź osobny profil mediów print. | `contract` |
| Nieaktualny interfejs | service worker; cache; wersje zasobów | Porównaj czysty i jawnie utrwalony kontekst; live skaner blokuje SW. | `manual` |
| Widoczny stan innego użytkownika | cache; storage; sesja; izolacja | Testuj wyłącznie kontrolne konta; screenshot nie potwierdza pełnego modelu uprawnień. | `contract` |
| Błędna prezentacja wykresu | skala; jednostki; etykiety; dane | Porównaj jawny zestaw referencyjny i kontrakt znaczenia. | `manual` |
| Niezrozumiała/nieprawdziwa etykieta | treść; tłumaczenie; brak kontekstu | Potrzebna ocena względem celu produktu, nie sama geometria. | `manual` |

## native-and-coverage

| Klasa | Możliwe przyczyny | Próba rozstrzygająca | Pokrycie |
|---|---|---|---|
| Natywne okno poza pulpitem | zapisana geometria; zmiana monitora; DPI | Sprawdź na docelowym OS przez adapter desktop/Appium. | `contract` |
| Błędy skali natywnego GUI | DPI awareness; skalowanie aplikacji | Porównaj profile monitora na rzeczywistym systemie. | `vision` |
| Błędy zawijania terminala | wcwidth; Unicode; szerokość PTY | Uruchom scenariusz Pexpect w kilku rozmiarach PTY. | `contract` |
| Nieczytelne kolory TUI | paleta; ANSI; motyw terminala | Porównaj render TUI w kontrolowanych paletach. | `vision` |
| Wnętrze iframe nie zostało zbadane | granica kolektora lub originu | Dodaj osobny autoryzowany target albo analizę obrazu; to luka pokrycia. | `gap` |
| Zamknięty Shadow DOM | brak dostępu przez DOM | Analizuj screenshot i kontrakty wejścia; nie ogłaszaj pełnego pokrycia. | `gap` |
| Nieosiągnięty stan po zalogowaniu | brak sesji testowej; przekierowanie | Dodaj jawny, bezpieczny fixture/session setup; brak danych to nie PASS. | `gap` |
| Analiza ograniczona zasobami | CPU/RAM/dysk/budżet LLM | Pokaż zaległość, pominiętą warstwę i ostatni rzeczywisty pomiar. | `gap` |

## Źródła i interpretacja

Kategorie opracowano dla tego projektu. Odniesienia do dostępności nie są deklaracją zgodności ani poradą prawną.
- W3C WCAG 2.2: https://www.w3.org/TR/WCAG22/
- CDP CSS: https://chromedevtools.github.io/devtools-protocol/tot/CSS/
- Playwright: https://playwright.dev/python/docs/intro
- WUP (odczyt 2026-09-22): https://github.com/semcod/wup
