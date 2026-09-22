# Reguły, dowody i ograniczenia

`confirmed` oznacza odtworzenie konkretnego naruszenia reguły lub jawnego kontraktu UI co najmniej dwukrotnie w stabilnych obserwacjach tej samej komórki. Nie oznacza automatycznie potwierdzenia przyczyny źródłowej lub intencji produktowej. `candidate` wymaga oceny. Wynik brakującej przeglądarki, detektora lub niedokończonego scenariusza nie staje się wynikiem pozytywnym.

| Reguła | Podstawa | Ważny wyjątek / ograniczenie |
|---|---|---|
| `TW-TEXT-OVERLAP` | Przecięcie niezależnych prostokątów zakresów tekstowych: oba wymiary > 2 px, wspólna powierzchnia > 12% mniejszego zakresu | To geometria zakresów linii, nie segmentacja widocznych glifów. Dekoracyjne warstwy i zasłonięty tekst mogą wymagać wykluczenia. Transformacje obniżają wynik do kandydata. |
| `TW-TEXT-CLIPPED` | Tekst wychodzi poza lokalny lub przodkowy `overflow:hidden/clip` | Celowy ellipsis i line-clamp są wyłączone. Samo wyjście poza ekran nie jest clippingiem. Całkowicie niewidoczny tekst nie stanowi pełnej analizy ukrytej treści. |
| `TW-CONTROL-OCCLUDED` | Co najmniej 3 z 5 punktów trafiają w obcy element | Próbki nie obejmują każdego piksela i nie rozstrzygają zamierzonej hierarchii modalnej. Elementy nieaktywne i inert są pomijane. |
| `TW-TARGET-SMALL` | Widoczny obszar kontrolki jest mniejszy niż 24 CSS px w przynajmniej jednym wymiarze, w profilu dotykowym | Zawsze kandydat. Nie rozstrzyga wyjątków WCAG dotyczących odstępów, równoważnych kontrolek i tekstu inline. |
| `TW-VIEWPORT-OVERFLOW` | Dokument przekracza szerokość przechwycenia o więcej niż 2 CSS px | Pozioma mapa, plansza lub świadoma tabela mogą być zamierzone. Wymagają kontraktu lub wykluczenia. |
| `TW-VIEWPORT-META` | Brak meta viewport przy emulowanym mobile | Kandydat, nie uniwersalny dowód błędu responsywności. |
| `TW-IMAGE-BROKEN` | Widoczny img ma `complete=true`, niepusty currentSrc i `naturalWidth=0` | Nie analizuje obrazów tła CSS, canvas ani filmów. Blokada zasobu przez allowlistę także może prowadzić do takiej obserwacji. |
| `TW-ALIGNMENT` | Jawny kontrakt wspólnej krawędzi; rozrzut przekracza tolerancję | Kontrakt musi odzwierciedlać rzeczywisty zamiar projektu. Geometrię można zmierzyć także poza aktualnym kadrem; raport preferuje wystąpienie z widocznym dowodem. |
| `TW-ALIGNMENT-CANDIDATE` | Podobne rodzeństwo DOM, co najmniej dwa zgodne wyrównania i jeden niewielki odstęp | Zawsze kandydat; celowa asymetria jest częsta. |
| `TW-FUNCTION-ASSERTION` | Działanie wykonane; jawne oczekiwanie UI nie spełniło się w czasie | Nie dowodzi błędu zapisu w bazie ani kompletności transakcji. `changed` pozostaje heurystyką. |
| `TW-ACTION-UNVERIFIED` | Nie udało się wykonać działania w stabilnym i dostępnym punkcie wejścia | Kandydat i blokada scenariusza; nie jest równoważny potwierdzonemu błędowi rezultatu funkcji. |
| `TW-AXE-*` | Naruszenie zwrócone przez rzeczywisty axe-core | Zakres automatycznych reguł oraz wyłączenia prywatności; ręczny audyt pozostaje potrzebny. |
| `TW-VISUAL-REGRESSION` | Próg różnicy pikselowej przekroczony względem zaakceptowanego PNG | Domyślnie kandydat; nowe dane lub poprawna zmiana projektu również zmieniają obraz. |

## Mechanizmy ograniczania fałszywych alarmów

Nie porównuje się zwykłych pudełek wszystkich divów. Tekst zbierany jest z bezpośrednich węzłów tekstowych; rodzic i dziecko oraz zakresy tego samego właściciela nie są traktowane jak niezależna kolizja. Pary są indeksowane przestrzennie zamiast pełnego porównania kwadratowego. Istnieje także limit porównań — jego przekroczenie daje lukę pokrycia.

Wyniki geometryczne są powtarzane; snapshot przed i po zrzucie służy wykryciu niestabilności. Czas, locale, kolorystyka, ruch i fonty są jawne. Baseline nie jest automatycznie przyjmowany, a niezgodna wersja przeglądarki unieważnia porównanie. Wykluczenie jest jawne, ma właściciela i wygasa.

Nie wszystkie możliwe fałszywe alarmy zostały wyeliminowane. Przykładowo nakładające się range boxes mogą zawierać wolne przestrzenie między glifami; dolna warstwa tekstu może być zasłonięta nieprzezroczystym overlay. Snapshot DOM zachowuje takie dane geometryczne, a zrzut i przegląd pozwalają rozstrzygnąć intencję. Nie jest to system OCR ani estymator kompletności produktu.

## Interpretacja macierzy

`report.json` zawiera osobne komórki i wystąpienia każdego znaleziska. `reproduced_cells` wymienia komórki spełniające warunek dwóch powtórzeń. Licznik globalny liczy naruszenia w stanach UI, a nie niezależne przyczyny w kodzie. `matrix.csv` zawiera liczby wystąpień; brak obserwacji w niekompletnej komórce to `unknown`, nie zero błędów.

Sprawdzenie jednej trasy nie dowodzi poprawności innych tras, a świeży browser context nie dowodzi świeżości danych serwera. Test koszyka wymaga konkretnego oczekiwania; z samego wyglądu przycisku nie da się stwierdzić, czy ma zwiększać licznik, otwierać modal czy uruchamiać inną funkcję.
