# Ponowne wykorzystanie OSS — rozszerzenie live

Sprawdzono publiczne kontrakty 22 września 2026 r. To nie jest test całych
repozytoriów ani gwarancja zgodności dowolnej przyszłej wersji `main`.

| Element | Użycie w 0.3 | Istotna granica |
|---|---|---|
| WUP | Addytywne polecenia `wup gui`, installer i patch do istniejącego Typer CLI | Nie zmienia automatycznie `wup watch`; pełny checkout/CI upstream nie był uruchomiony |
| Playwright/CDP | Procesy przeglądarek, izolowane konteksty, DOM/CSS/hit-test/screenshot | Firefox i WebKit nie są CDP; emulacja nie jest urządzeniem fizycznym |
| axe-core | Opcjonalne sprawdzanie dostępności w L2 | Wyniki incomplete są luką; automat nie certyfikuje WCAG |
| psutil + cgroup v2 | Kontrola przyjmowania nowych zadań | Nie jest sprzętowym real-time schedulerem ani twardym limitem RSS |
| SQLite WAL i SSE | Trwałe incydenty, ledger modeli i lokalne zdarzenia live | Jeden writer/agent, lokalny dysk; brak klastra i uwierzytelnionego publicznego panelu |
| MSS | Adapter regionu pulpitu | Testowano kontrakt na obrazach; rzeczywiste uprawnienia/OS wymagają sprawdzenia |
| LiteLLM | Kontrolowana multimodalna analiza obrazów po wykryciu lokalnej obserwacji | Brak live call w weryfikacji; wynik tylko candidate |
| OpenCV / Ultralytics | Regiony, template matching, opcjonalny model lokalny | Brak automatycznej trafnej klasyfikacji wszystkich wad GUI; YOLO CPU, bez dostarczonych wag |
| TestQL / Planfile | Istniejące wykonanie zadań i publikacja reviewable proposals | Live sam nie uruchamia kodu wygenerowanego przez model |

Źródła pierwotne:
- https://github.com/semcod/wup
- https://raw.githubusercontent.com/semcod/wup/main/wup/cli.py
- https://raw.githubusercontent.com/semcod/wup/main/wup/config.py
- https://playwright.dev/python/docs/docker
- https://chromedevtools.github.io/devtools-protocol/tot/CSS/
- https://github.com/dequelabs/axe-core
- https://www.w3.org/TR/WCAG22/
- https://github.com/giampaolo/psutil
- https://www.sqlite.org/wal.html
- https://html.spec.whatwg.org/multipage/server-sent-events.html
- https://github.com/BoboTiG/python-mss
- https://docs.litellm.ai/docs/completion/vision
- https://docs.litellm.ai/docs/proxy/users
- https://github.com/autogrammar/testql
- https://github.com/semcod/planfile

Dokumentacja Playwright wskazywała parę 1.61.0/image v1.61.0-noble.
Zastąpiono odziedziczony niezweryfikowany pin 1.63.0. Lokalny Playwright użyty
w testach renderera to osobna wersja zapisana w STATUS; obrazu Docker nie zbudowano.
Sprawdzono również aktualne przykłady actions/checkout, setup-python oraz
upload-artifact; zachowano istniejące @v7. Przed produkcją warto przypiąć
reviewowane pełne SHA akcji, TestQL i Planfile zamiast ruchomych majorów/main.
