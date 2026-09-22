# Landing page testwins.com

Samodzielny, statyczny HTML/CSS/JS; bez zewnętrznych fontów, trackerów i formularzy
udających działający backend. Grafika raportu jest jawnie podpisaną ilustracją DEMO.
Motyw jasny/ciemny, menu mobilne, wybór shell/web/GUI, kopiowanie komendy z uczciwym
fallbackiem, FAQ, dokumentacja i strona prywatności.

## Osobny Docker

Z katalogu głównego paczki:

```bash
docker compose -f landing/compose.yaml up --build -d
# http://127.0.0.1:8090/
docker compose -f landing/compose.yaml down
```

Dla osobnego archiwum `testwins-landing.zip`, po wejściu do katalogu
`testwins-landing/`, użyj `docker compose up --build -d` oraz `docker compose down`.
Testy `make landing-check` wymagają pełnej paczki źródłowej Testwins.

nginx-unprivileged, port8080, UID101, read-only FS, własna polityka CSP, bez dostępu
do plików aplikacji Testwins. Nie dołączono pobranych fontów/modeli ani śledzenia.

## Testowanie własną paczką

```bash
make landing-check
make report INSTANCE=landing
make landing-down
```

Buduje TEN Dockerfile i uruchamia audyt Python Testwins oraz scenariusz TestQL
`tests/landing.oql`. `tests/audit.yaml` zawiera trzy trasy i kontrakty zmiany motywu,
trybów oraz FAQ. TestQL jest osobnym przebiegiem, nie twierdzeniem, że jego scenariusz
wykonano w każdej z dziewięciu komórek macierzy. Macierz realizuje audytor DOM/CDP.
Testy nie pomijają bibliotek wymaganych w obrazie Docker.

Lokalny `python tools/verify_landing.py` jest innym, jawnym testem renderera: ładuje
nasz statyczny HTML/CSS/JS bez nawigacji HTTP; służy środowiskom z blokadą administracyjną.
Nie jest dowodem poprawnego działania kontenera, nginx, CSP, DNS ani TLS.

## Domena

Pliki są przygotowane dla testwins.com, ale **nie wykonano wdrożenia** i nie sprawdzono
uprawnień do domeny. Wskaż własny serwer w DNS i skonfiguruj reverse proxy HTTPS/TLS.
Przykładowy blok Caddy, jeśli proxy działa na tym samym hoście:

```caddyfile
testwins.com {
    reverse_proxy 127.0.0.1:8090
}
```

To przykład konfiguracyjny, nie zweryfikowany deployment. Kontenerowy reverse proxy
potrzebuje wspólnej sieci/nazwy usługi zamiast własnego loopbacku. Nie publikuj portów
raportów/noVNC/CDP w Internecie. Przed uruchomieniem publicznym uzupełnij rzeczywisty
adres repozytorium, dane operatora i sposób dystrybucji pakietu po publikacji.
