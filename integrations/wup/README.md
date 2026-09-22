# WUP + Testwins 0.4 — implementacja addytywna

Zachowano adapter z Testwins 0.3, bez ingerencji w prywatne mechanizmy WUP.
Odczytana przy przygotowaniu wcześniejszego wydania 2026-09-22 gałąź `main` WUP zawiera `app = typer.Typer(...)` i `console = Console()` w `wup/cli.py`. Dodajemy **realny moduł komend** `wup/gui_testwins.py` oraz rejestrację `wup gui`. Nie zmieniamy działania istniejącego `wup watch`, jego API probes, TestQL, pfix ani rozpoznawania usług. Ten wariant unika kruchego wpinania w prywatne wątki WUP. Nie twierdzimy, że GUI automatycznie uruchamia się po dotychczasowym `wup watch`.

```bash
# Z katalogu Testwins, w środowisku Python używanym przez WUP:
python -m pip install -e '.[live]'
python integrations/wup/install.py /sciezka/do/wup
python integrations/wup/install.py /sciezka/do/wup --apply
python -m pip install -e /sciezka/do/wup

# Konfiguracja jest osobnym plikiem; nie jest gubiona przez save_config starszego WUP.
wup gui watch /sciezka/do/badanego-projektu --config testwins.watch.yaml
wup gui status /sciezka/do/badanego-projektu --config testwins.watch.yaml
wup gui capacity /sciezka/do/badanego-projektu --config testwins.watch.yaml --seconds-per-cell 2
wup gui export /sciezka/do/badanego-projektu --config testwins.watch.yaml --output /tmp/gui-evidence-001
```

Można równolegle uruchomić zwykłe `wup watch /sciezka/do/projektu` do istniejących testów HTTP/shell/TestQL; `wup gui watch` dostarcza graficzny strumień diagnostyczny. Nie uruchamiamy istniejącej konfiguracji testów/napraw WUP niejawnie.

Instalator ma dry-run, pełny preflight, kopię zapasową i sprawdzanie konfliktów. Jest idempotentny dla identycznej wersji dodatku. Alternatywa: `git -C /sciezka/do/wup apply --check /sciezka/do/testwins/integrations/wup/wup-testwins.patch`, a następnie to samo bez `--check`. Wygenerowany patch nie zawiera całego upstream repozytorium.

**Stan weryfikacji:** przetestowano moduł komend i instalator na kontrolowanym szkielecie z odczytanym punktem rejestracji. Nie udało się pobrać pełnego checkoutu (brak rozwiązywania DNS w środowisku wykonawczym), dlatego nie uruchomiono całego zestawu testów WUP. Nie wykonano push ani PR. Przed scaleniem sprawdź patch i testy WUP na wybranym commicie; `main` nie jest przypięciem wersji.

Źródła: https://github.com/semcod/wup oraz https://raw.githubusercontent.com/semcod/wup/main/wup/cli.py
