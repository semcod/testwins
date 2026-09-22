# Clonerd — profil Testwins 0.4.0 zamiast silnika twin_ux

Profil wygenerowany z dostarczonych testów i planu migracji. Zawiera wykonywalne konfiguracje, nie kod starego
audytora. Do uruchomienia potrzebny jest zainstalowany Testwins 0.4.0 i działająca, autoryzowana aplikacja.
**Selektory i kontrakty nie zostały tu sprawdzone na rzeczywistym Clonerd** — przekazane archiwa nie zawierają serwera.

```bash
testwins init ./clonerd-tests --profile clonerd
cd clonerd-tests
make configure BASE_URL=http://127.0.0.1:8891
make validate
make scan
# Po przeglądzie selektorów i danych:
make personas
make watch
```

## Zakres

| Polecenie | Co wykonuje |
|---|---|
| `make scan` | 9 wejściowych widoków x desktop/tablet/mobile = 27 celów tylko do odczytu w Chromium |
| `make personas` | 6 person x 3 profile, z dwoma powtórzeniami; osobny GET `/v1/menu` raz |
| `make watch` | Te same 27 wejść obserwowanych okresowo; bez niejawnego klikania person |
| `make api` | Jeden read-only kontrakt menu, nie cała macierz urządzeń |
| `make performance` | Oddzielny budżet `JSHeapUsedSize` w desktop Chromium |
| `make download-review` | Jawnie wybierany download PDF; wymaga przeglądu kontrolki i danych |

Customer: plany, wybór Pro i kontrolka CTA (bez płatności). Developer: paleta, wyszukiwanie taskand i zamknięcie.
Manager: macierz i przejście do audytu w tym samym kontekście. Accountant: faktury, kontrolka pobierania i billing.
CEO: KPI i oczekiwane elementy wykresu. CTO: hosty i kontrolka noVNC. **Obecność kontrolki nie dowodzi wykonania operacji**.
`scope.json` jest jawną listą dostarczonych kontraktów i luk, np. RBAC backendu, rzeczywiste płatności,
semantyka faktur/KSeF, aktualność KPI i połączenie noVNC. Nie zastępuj tej listy procentem „100% UX”.

Domyślne `personas.suite.yaml` nie wykonuje płatności, POST `/api/auto/cycle` ani pobierania dokumentów.
Osobny `api/mutations.review.yaml` wymaga dodatkowej zgody:

```bash
python -m testwins api --config api/mutations.review.yaml \
  --output artifacts/api-mutations --approve-mutations
```

Nie uruchamiaj na produkcji lub współdzielonych danych bez świadomej autoryzacji. Nawet nawigacja i kod strony
mogą mieć skutki serwerowe. Testwins nie gwarantuje odwracalności efektów aplikacji.

## Konfiguracja i sesje

`make configure` zapisuje origin do wszystkich właściwych YAML. Nie ma magicznego podstawiania `${BASE_URL}`.
`layout=desktop` dotyczy desktop/tablet; mobile używa `layout=onepage`, jak w legacy.
`make scan MATRIX=engines` zmienia audyt wsadowy. Persony i live pozostają na zadeklarowanej konfiguracji, dopóki
nie edytujesz ich macierzy. W Dockerze podaj nazwę SUT we wspólnej sieci zamiast hostowego localhost.

Każda scena ma nowy kontekst. Przejścia wewnątrz persony zachowują kontekst; dodatkowe przygotowanie sesji można
ustawić przez `setup_path`. Dodaj nazwane `sessions` z prywatnym plikiem `storage_state` i `session` w scenach,
gdy aplikacja wymaga uwierzytelnienia. Żadne hasła ani selektory logowania nie są zgadywane.
Ścieżka sesji jest względem YAML w podkatalogu, np. `../.auth/manager.storage-state.json`; POSIX wymaga 0600.

Originy zewnętrznych zależności dopisz jawnie do `allowed_origins`. Nie wyłączaj CSP ani zarządzanych polityk
przeglądarki, aby ukryć błędy konfiguracji. Sandbox pozostaje włączony w profilach, uruchamiaj jako zwykły użytkownik.

## Bramka 0.4 i CI

Wszystkie wymagane kroki są planowane przed startem. Pojedyncza nieudana asercja blokuje sukces, nawet bez
potwierdzonego naruszenia wizualnego. 0=zaliczony zadeklarowany zakres, 1=niepowodzenie, 2=niekompletność.
Raport jest technicznym wynikiem kontraktów, nie oceną wszystkich niewidzianych stanów i kryteriów dostępności.
Axe/LLM/CV są jawnie wyłączone w tym profilu. Włączaj je z wymaganymi zależnościami i zgodą na transfer dowodów.
Nie importuj starych screenshotów automatycznie jako baseline: stary DPR i końcowe stany person różnią się od
nowych dowodów w skali CSS przed/po krokach.

```bash
make validate
make personas
# W repozytorium źródłowym Testwins: pytest -p testwins.pytest_plugin
```

## Parytet migracji

Zachowaj stare testy do sprawdzenia na działającej aplikacji, że każda potrzebna funkcja ma jawny kontrakt i dowód.
Testy HTTP i wydajności są oddzielnymi zakresami. Nie należy wyłączać testów backendu tylko dlatego, że skan GUI jest zielony.
Weryfikacja dostarczona w wydaniu dotyczy parserów i runnera na kontrolnym UI, nie portalu Clonerd.
Historyczna analiza poprzedniego startera jest w źródłowym wydaniu pod `docs/migration/ANALIZA-0.3.md`.
