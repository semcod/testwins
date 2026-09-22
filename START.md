# Testwins 0.4.0 — start

Pełny ZIP rozpakowuje się do katalogu `testwins/`. Zawiera gotowe `dist/*.whl` i `dist/*.tar.gz`.
Nie zastępuje instalacji zależności ani obrazów przeglądarek. Wymagane Python 3.11–3.13, a do Makefile GNU Make.

## 1. Własny landing w Docker/noVNC

```bash
cd testwins
cp .env.example .env
make landing-check MATRIX=chromium
make report INSTANCE=landing
make vnc-password INSTANCE=landing
# Zatrzymanie:
make landing-down
```

Wymaga Docker Compose v2 i sieci do budowania. Landing: `http://127.0.0.1:8090/`, raporty: `http://127.0.0.1:8088/`,
noVNC: `http://127.0.0.1:6080/vnc.html`. Pełny lab sprawdza obecność publicznego SDK TestQL przy budowaniu.
`MATRIX=engines` dodaje Firefox/WebKit, `MATRIX=cdp` wybiera Chrome/Edge/Brave (amd64).

## 2. Lokalny tester własnej aplikacji

```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install './dist/testwins-0.4.0-py3-none-any.whl[live,terminal]'
python -m playwright install chromium
testwins init ./my-tests
# Ustaw adres i kontrakty w my-tests/audit.yaml, uruchom własną aplikację.
testwins run --config my-tests/audit.yaml --output my-tests/artifacts
```

## 3. Migracja Clonerd

```bash
testwins init ./clonerd-tests --profile clonerd
cd clonerd-tests
make configure BASE_URL=http://127.0.0.1:8891
make validate
make scan
# Po przejrzeniu kontraktów i selektorów:
make personas
```

`make scan` nie klika. `make personas` wykonuje sześć person dla trzech profili i jeden osobny kontrakt GET.
Mutujący POST i pobranie faktury są osobnymi, jawnie wybieranymi scenariuszami.

Wyniki `run`/`gate`: **0** — przejście zadeklarowanego zakresu, **1** — nieudany obowiązkowy kontrakt/naruszenie,
**2** — niekompletność. Żaden kod nie oznacza automatycznej poprawności wszystkich stanów całej aplikacji.

Przeczytaj [README](README.md), [nowe kontrakty](docs/RELEASE-0.4.md) i
[rzeczywistą weryfikację tego wydania](verification/STATUS.md). Publikacja PyPI/domeny i push/PR nie były wykonywane.
