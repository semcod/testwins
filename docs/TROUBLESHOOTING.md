# Rozwiązywanie problemów

## Docker / platforma

`make doctor` sprawdza obecność klienta, Compose v2 i dostępność demona. Brak Dockera nie uruchamia fikcyjnej macierzy. Potrzebny jest działający Docker Engine/Desktop. Macierz CDP wymaga obrazu amd64. Na ARM sprawdź działanie emulacji lub zacznij od `MATRIX=engines`; nie traktuj braku binarnego pliku jako PASS.

Obraz Playwright i pakiet Python muszą mieć tę samą wersję. W paczce przypięto 1.61.0 dla obrazu i zależności. Zmieniając wersję, zmień obie referencje oraz ponów cały test macierzy. Chrome/Edge/Brave są instalowane z kanałów dystrybucyjnych podczas budowania; ich numery wersji są zapisywane w raporcie. To nie jest bitowo odtwarzalny lock całego systemu operacyjnego.

## SUT nie startuje

Najpierw `make logs`. Usługa musi słuchać na 0.0.0.0 i zadeklarowanym APP_PORT. Nie ma automatycznego zgadywania frameworka ani poprawiania komendy uruchomienia. `APP_INSTALL` wykonuje się podczas builda. `npm ci` wymaga lockfile; Python/Node/PHP musi być dostępny w APP_IMAGE. Dla natywnych rozszerzeń przygotuj odpowiedni obraz bazowy.

Kopia projektu pomija `.env*`, symlinki i katalogi zależności. Przekaż testowe zmienne przez osobny `SUT_ENV_FILE`, a nie przez wyłączenie wszystkich filtrów sekretów. Pip instalowany przez użytkownika korzysta z trwałego HOME w obrazie; `/tmp` jest osobnym runtime tmpfs. Aplikacja wymagająca bazy może użyć kontrolowanego COMPOSE_OVERRIDE.

## Puste okno noVNC

`make up` uruchamia pulpit i SUT. Przeglądarki otwierają się podczas `make audit`; po audycie są zamykane wraz z tymczasowymi profilami. `headless: true` celowo nie pokazuje okien w noVNC. Hasło odczytuje `make vnc-password`. Nie klikaj w sesję w trakcie pomiarów — ręczna ingerencja zmienia stan i może powodować niestabilność.

Przy konflikcie portów wybierz inne VNC_PORT/REPORT_PORT. Zdalny dostęp powinien używać tunelu, nie otwierania CDP na 0.0.0.0.

## Błędy i niekompletność

Kod audytu 1 to znalezione powtarzalne naruszenia, nie awaria samego programu. Kod 2 oznacza niekompletność. `report.json` zawiera błędy per komórka i `scope_gaps`; JUnit odróżnia failure od error.

Gdy wymagany axe-core nie jest dostępny, raport jest niekompletny. Do świadomego pominięcia tej warstwy służy `axe.enabled: false` albo lokalne `--no-axe`. Nie nazywaj takiego uruchomienia pełnym audytem dostępności. Zewnętrzny font lub obraz może nie załadować się z powodu prywatnej sieci albo allowlisty; najpierw ustal, czy to konfiguracja środowiska.

`ready_selector` powinien wskazywać stabilnie wyrenderowany stan aplikacji. Dla wolnych SPA dostosuj timeout do wymagań produktu. Limit czasu nie powinien być zwiększany tylko po to, aby ukryć regresję wydajności. Zamrażanie animacji nie testuje ich jakości.

## Mobilne współrzędne

Nie zastępuj korekty `visualViewport` prostym `innerWidth` ani `force=True`. Test kontrolny tej paczki wykrył rzeczywistą rozbieżność przy poziomym overflow: źle przeliczone maski trafiały w inny obszar obrazu, a standardowe kliknięcie wskazywało nakładkę zamiast kontrolki. Implementacja rozdziela hit-test DOM i współrzędne wejścia CDP. Przy dodawaniu innych transportów należy testować ten przypadek regresyjny.

## Polityka blokująca HTTP

W środowisku przygotowania paczki zainstalowany Chromium odrzucał nawigację HTTP przez politykę administratora. Nie zmieniono tej polityki. `make smoke-offline` umieszcza znany, syntetyczny HTML w nowej pustej stronie i testuje rzeczywisty renderer/CDP bez nawigacji. Jest to test kolektora, geometrii, wejścia i raportowania — **nie zamiennik testu serwera HTTP, noVNC ani Docker**. Standardowy `make smoke` nie ukrywa takiej blokady fallbackiem.

## Planfile / baseline

Publisher wymaga istniejącego `.planfile` i wersji z TicketProposalV1 oraz atomową deduplikacją. Niepełna lub zmieniona instalacja ma zakończyć się błędem. `main` jest ruchomy; wybierz i zanotuj własny sprawdzony SHA. Paginację wyjścia sprawdzaj przez `next_offset`.

Nowa przeglądarka, fonty lub obraz bazowy mogą unieważnić baseline. Nie nadpisuj wzorca automatycznie. Najpierw przejrzyj zmianę i wykonaj świadome `--approve` na kompletnym raporcie.

## Vite: host `sut` niedozwolony

Vite ma osobną allowlistę hostów; samo `--host 0.0.0.0` nie dopuszcza dowolnej nazwy DNS. Przykład Node w README ustawia `__VITE_ADDITIONAL_SERVER_ALLOWED_HOSTS=sut` wyłącznie dla procesu aplikacji. Nie ustawiaj `allowedHosts: true`. Dla innych frameworków skonfiguruj analogicznie dokładny host sieci testowej. Źródło: [Vite server.allowedHosts](https://vite.dev/config/server-options.html#server-allowedhosts).
