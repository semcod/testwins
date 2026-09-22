# Model bezpieczeństwa

Narzędzie jest przeznaczone do uprawnionego audytowania własnych aplikacji w kontrolowanym środowisku testowym. Nie jest piaskownicą do uruchamiania dowolnego wrogiego kodu z gwarancją bezpieczeństwa hosta.

## Granice

Hostowy launcher ma uprawnienia do Dockera i wykonuje jawne polecenia operatora dotyczące budowania SUT. Samo Docker build może uruchamiać skrypty instalacyjne zależności. Filtr źródeł ogranicza przypadkowe skopiowanie sekretów, lecz nie rozpoznaje każdego możliwego sposobu ich przechowywania. Nie uruchamiaj niezaufanych repozytoriów na ważnym hoście bez dodatkowej VM i kontroli polityk systemowych.

Runtime aplikacji oraz przeglądarki działają jako użytkownik nie-root, z `cap_drop: ALL`, `no-new-privileges`, limitami CPU/pamięci/procesów i odrębnymi katalogami tymczasowymi. Lab ma read-only root filesystem; SUT ma zapisywalną, jednorazową warstwę kontenera, aby działały cache i lokalna baza testowa. Nie ma Docker socketu, hostowego X11, profilu użytkownika, `/home` ani automatycznej synchronizacji cookies.

Sieć `internal` ogranicza egress. Dodatkowa allowlista requestów i WebSocketów w browser context ogranicza originy odwiedzane przez UI. Nie jest to dowód całkowitej izolacji od hosta, wszystkich protokołów, exploitów silnika czy efektów ubocznych HTTP. Nie zastępuje firewalla, VM i polityki wdrożenia.

CDP słucha lokalnie w kontenerze. Host nie dostaje portu 9222. noVNC i raporty są publikowane tylko na 127.0.0.1; bez zmiany tej konfiguracji nie są usługą publiczną. noVNC używa hasła przechowywanego w pliku instancji, nie w URL. Tradycyjne hasło VNC ma ograniczoną długość i nie jest pełną warstwą ochrony transportu. Dla zdalnego dostępu stosuj kontrolowany tunel SSH lub uwierzytelniony reverse proxy z TLS; nie wystawiaj tych portów bezpośrednio do Internetu.

## Sandbox Chromium

Domyślny `sandbox: false` uruchamia Chromium z `--no-sandbox`, ponieważ cel podstawowy to zgodny z Dockerem audyt własnego SUT. Izolacja procesu Chromium jest przez to słabsza. Włączenie `sandbox: true` wymaga poprawnego profilu seccomp/user namespaces i zgodnej konfiguracji kernela/obrazu; brak tych warunków ma dać błąd uruchomienia. Paczka nie dostarcza uniwersalnego, przetestowanego na wszystkich systemach profilu sandboxa. Szczególnie dla nieznanych stron użyj dodatkowej VM i wyraźnie sprawdzonej polityki.

## Dane i LLM

Używaj syntetycznych kont, danych i płatności. Domyślnie maskowane są inputy, textarea, contenteditable i `[data-private]`. Maski nie usuwają automatycznie nazwiska narysowanego w canvas, treści wewnątrz iframe, tekstu w niestandardowym elemencie ani każdej informacji w atrybutach. Zrzuty, HTML i selektory należy przejrzeć przed ich udostępnieniem. Haszowanie pliku nie anonimizuje jego treści.

Wartości kroków `fill` nie są kopiowane do publicznej konfiguracji raportu. Błędy narzędzi zapisywane w raporcie używają typu wyjątku, nie surowego tracebacku aplikacji. Ręczne `make logs` służy operatorowi do diagnostyki kontenerów; takich logów nie należy automatycznie przesyłać do modelu ani publicznego ticketu.

Model dostaje tylko wybrane, ograniczone dowody i nie ma narzędzi wykonawczych. Wynik ma zamknięty format, znane selektory i prostokąty wewnątrz obrazu. Transfer do zdalnego endpointu wymaga `VISION_ALLOW_REMOTE=1`; brak modelu lub odrzucenie odpowiedzi nie daje sfabrykowanych wyników. Prompt injection w treści strony nadal może wpłynąć na opis modelu, dlatego jego wynik pozostaje kandydatem bez uprawnień.

## Operacje zmieniające stan

Nawet wejście na URL może wywołać skutki uboczne. Crawler ma allowlistę, ale nie potrafi dowieść nieszkodliwości wszystkich GET-ów. Click/fill/press/check/select wymagają opt-in w scenariuszu. Nie używaj produkcyjnych kont z możliwością zamówień, wypłat, publikacji lub usuwania danych.

Publisher Planfile jest osobnym kontenerem bez dostępu sieciowego w runtime i bez źródeł SUT. Uprawnieniem operatora jest sam wybór `.planfile` oraz apply/ready. Nie zakładaj, że etykieta `needs-human` ochroni system, którego zewnętrzny executor świadomie ignoruje reguły Planfile.

## Retencja i porządkowanie

`make down` zatrzymuje kontenery, ale nie usuwa raportów, baseline ani kontekstu builda. `.testwins/<instance>/target-build` zawiera odfiltrowaną kopię aplikacji; obrazy Docker również zachowują tę kopię. Usuwaj je zgodnie z polityką projektu. Nie commituj `.env`, `.testwins`, `artifacts`, danych użytkowników i przypadkowo zebranych dowodów do publicznego repozytorium.


## Testwins 0.2: nowe granice

Scenariusze TestQL/shell/GUI są wykonywalnym kodem operatora. Nigdy nie traktuj
otrzymanego od osoby trzeciej repo/.oql jako bezpiecznych danych. Docker worker nie
jest gwarantowaną piaskownicą dla celowo wrogiego kodu: współdzieli kernel i zależy od
bezpieczeństwa runtime. Nie uruchamiaj na sekretach/produkcji. Build ma osobną sieć.
`--trusted-local` jawnie rezygnuje z izolacji Docker i używa uprawnień hosta.

Worker nie dziedziczy tokenów LLM/cloud ani PYTHONPATH. Lokalny tryb nadal ma HOME,
DISPLAY i uprawnienia użytkownika, a więc może odczytać hostowe pliki. Dlatego wyłącznie
przejrzane scenariusze. Desktop screenshoty nie są DOM-maskowane. Jednorazowy Xvfb
z syntetycznymi danymi jest domyślnym przeznaczeniem backendu desktop.

Checkpoint .pt może wykonywać kod, nawet przy znanej sumie SHA. CV wymaga przejrzanych
wag i --trust-model. Nie pobieramy modeli automatycznie. Zewnętrzny LLM wymaga zgody
LLM_ALLOW_REMOTE, lecz operator musi sam sprawdzić obrazy i politykę providera.
LLM nie ma narzędzi wykonawczych; drafty wymagają przeglądu i osobnego uruchomienia.

Wyniki TestQL zachowują oryginalny JSON wraz z opisami failures/errors. Mogą zawierać
wrażliwy tekst pochodzący ze scenariusza/aplikacji; sanitizacja wyjątku workera nie
redaguje zawartości oryginalnego kontraktu. Raporty trzymaj prywatnie.


## Live 0.3: dodatkowe granice

Używaj wyłącznie kontrolowanych aplikacji i autoryzowanych URL. Nawigacja GET
również może mieć skutki uboczne w źle zaprojektowanej aplikacji. Monitor nie
uzyskuje Twojego profilu przeglądarki, haseł systemowych ani socketu Docker.
Pulpit wymaga jawnej zgody na region; maski muszą zostać dobrane przez operatora.
Semantyczny HTML i CSS mogą zawierać dane aplikacji; nie publikuj automatycznie
artefaktów. Maski/OCR/redakcja URL nie są formalną gwarancją anonimizacji.

SSE/HTTP to tylko lokalny panel odczytu, bez auth i TLS. Porty Compose są wiązane
z loopback. Nie wystawiaj `--allow-expose` bez własnej warstwy uwierzytelniania,
TLS i firewall. Kontenery dev używają uproszczonego sandboxingu przeglądarki;
nie są bezpieczną piaskownicą dla wrogiego Internetu. Allowlista origin nie jest
sieciowym firewallem ani ochroną przed każdym DNS rebinding.

Żadne instrukcje odczytane ze strony/modelu nie są wykonywane jako shell.
Hipotezy nie powodują automatycznej modyfikacji CSS ani wysłania ticketu do executora.
Wywołania modeli są opt-in, a przekazanie obrazów operatorowi wymaga osobnej zgody.
Używaj wirtualnych kont testowych i tajemnic ograniczonych do tego środowiska.
Wagi `.pt` są kodem/artefaktem wysokiego zaufania; wymagane jest `trust_model`.
