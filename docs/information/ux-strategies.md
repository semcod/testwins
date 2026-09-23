---
{
  "schema": "wellmanifest.docs/document/v1",
  "id": "ux-strategies",
  "kind": "information",
  "version": 1,
  "title": "Strategie UX, reakcje interfejsu i naprawy z subllm",
  "status": "implemented",
  "owner": "semcod/testwins",
  "created": "2026-09-23",
  "updated": "2026-09-23",
  "review_after": "2026-12-23",
  "source_revision": "60a99ddc180f19225e951acd158ae7590360267e",
  "affected_repositories": [
    "semcod/testwins"
  ],
  "evidence": [
    "repo://semcod/testwins/tests/test_ux.py",
    "repo://semcod/testwins/tests/test_ux_browser.py",
    "repo://semcod/testwins/testwins/ux.py",
    "repo://semcod/testwins/testwins/ux_probe.js",
    "repo://semcod/testwins/testwins/ux_review.py"
  ]
}
---

# Strategie UX, reakcje interfejsu i naprawy z subllm

<!-- docs:section purpose -->
## Cel

Testwins łączy wybraną strategię aplikacji z jawnym kontraktem przejścia:
**wejście użytkownika → informacja zwrotna → oczekiwany wynik**.
Wykrywa naruszenia zadeklarowanych wymagań i przygotowuje propozycje napraw.
Profile symulują wybrane nawyki; nie wykrywają intencji prawdziwego człowieka.

<!-- docs:section scope -->
## Zakres

`testwins strategies` wyświetla cztery strategie: `dashboard`, `form`,
`commerce`, `content`, wraz z wzorcami do uwzględnienia w scenariuszu.
Operator wybiera strategię i konkretne wymagania produktu. Profile nie
stwierdzają automatycznie, czy proces zakupowy lub model biznesowy jest poprawny.

Nawyki: `standard`, `deliberate` (500 ms namysłu przed działaniem), `keyboard`
(kontrakty używają press/fill/select), `reduced-motion` (preferencja przeglądarki
`reduce`, domyślny budżet ruchu 0 ms). Dotyk nadal wynika z `devices.*.touch`
i istniejącego mechanizmu wejścia CDP. Dla pozostałych profili UX przeglądarka
stosuje `no-preference`; stare konfiguracje zachowują dotychczasowe zachowanie.

<!-- docs:section evidence -->
## Podstawa i dowody

Punktem wyjścia implementacji jest rewizja Testwins wskazana w metadanych.
Publiczne API `subllm.complete` / `configured_routes` sprawdzono w lokalnym
`subactor/subllm` na rewizji `356c91986ba1c815f2447c5e320c97ea0bb6c6fa`
(dystrybucja `subactor-subllm` 1.14.0). Testy adaptera używają jawnych doubles;
nie są dowodem wywołania płatnego providera.

Wzorce bazują na [W3C: komunikaty statusu](https://www.w3.org/WAI/WCAG22/Understanding/status-messages.html),
[W3C: animacja po interakcji](https://www.w3.org/WAI/WCAG22/Understanding/animation-from-interactions.html)
i [NN/g: czas reakcji](https://www.nngroup.com/articles/response-times-3-important-limits/).
Wbudowane budżety są konfigurowalnymi wartościami startowymi Testwins, nie progami
zgodności WCAG ani uniwersalną oceną UX. Sprawdzenie `role`/`aria-live` nie
zastępuje testu czytnika ekranu. Ocena estetyki i przyczyn w kodzie pozostaje hipotezą.

<!-- docs:section content -->
## Użycie

```bash
python -m http.server 8080 --directory examples/ux-lab
# W drugim terminalu, z katalogu projektu:
python -m testwins strategies
python -m testwins validate --config configs/ux.yaml
python -m testwins run --config configs/ux.yaml --output artifacts/ux
```

Przykład działa lokalnie. Aby zobaczyć błędy, skopiuj konfigurację i zmień
`journeys[0].path` na `/?broken=1`: aplikacja nie zaznaczy wyboru, nie przeniesie
fokusu i pozbawi status semantyki. Powrót do `/` przywraca prawidłowe zachowanie.
Sprawdź oba raporty; to odtwarzalny przykład regresji i jej usunięcia.

```yaml
ux:
  strategy: dashboard
  habit: standard
  budgets: {response_ms: 3000, feedback_ms: 700, motion_ms: 500}
# Fragment pojedynczego kroku journeys[].steps[]:
# action: click
# selector: '#choose'
# allow_mutation: true
# expect: {kind: text, selector: '#result', value: Active projects}
# ux:
#   feedback: {kind: text, selector: '#status', value: Filter applied}
#   announce: true
#   focus: '#result'
#   visual_change: '#choose'
#   motion: '#choose'
```

Każdy krok z `ux: {}` sprawdza czas osiągnięcia zwykłej asercji `expect`.
Jeśli wynik pasował już przed wejściem i nie zaobserwowano nowego dopasowania,
kontrakt zgłasza `TW-UX-OUTCOME-UNCHANGED`.
Pozostałe pola rozszerzają zakres. Budżety kroku nadpisują globalne, a globalne
nadpisują strategię. Muszą mieścić się w `capture.timeout_ms`.
Wybór strategii wymaga przynajmniej jednego kroku UX. Profil klawiaturowy wymaga
odpowiednich działań, np. `press` z `key: Enter`, zamiast kliknięć.

| Warstwa | Kontrakt / obserwacja | Przykładowy błąd |
|---|---|---|
| Funkcjonalność | istniejący `expect`, `response_ms` | brak wyniku lub za późny wynik |
| Grafika | `visual_change`, istniejące detektory geometrii | brak widocznej zmiany wyboru, overlap, clipping |
| Informacja | `focus`, `announce` | niewłaściwy fokus, status bez semantyki |
| Przekaz informacji | `feedback`, `feedback_ms` | brak nowego komunikatu, zbyt późny komunikat |
| Animacja | `motion`, `motion_ms` | długa lub nieskończona animacja CSS/Web Animation |

`feedback` obsługuje `visible`, `text`, `contains_text`, `attribute`; element
musi być widoczny. Stan pasujący już przed wejściem nie jest nowym potwierdzeniem.
`visual_change` porównuje tekst, geometrię i wybrane style, więc sama klasa CSS
bez efektu nie wystarczy. `motion` wymaga `capture.freeze_animations: false`.
Brak elementu do pomiaru lub utrata dokumentu daje `incomplete`, nie sukces.

W `report.json` i osobnym `ux.json` są pomiary, budżety, naruszenia i nieobserwowane
warstwy. HTML i Markdown pokazują wyniki oraz odnośniki do dowodów. Bramka
wymaga kontraktów UX także przy jednym powtórzeniu; status LLM nie wpływa na nią.
Brak pomiaru wymaganego przez plan blokuje zaliczenie. Zmiana dokumentu podczas
kroku (pełna nawigacja) nie jest obsługiwana przez ten próbnik.

### Propozycje poprawek przez subactor/subllm

```bash
python -m pip install '.[subllm]'
# Ustaw w prywatnym .env lub środowisku; klucze przechowuje konfiguracja subllm:
# SUBLLM_PROVIDER_ORDER=zai,openrouter
# SUBLLM_APPLICATION=repair-agent
# SUBLLM_FUNCTION=repair-plan
# LLM_ALLOW_REMOTE=1
# LLM_TIMEOUT=60
python -m testwins ux-review artifacts/ux/KONKRETNY-RUN \
  --output artifacts/ux-review --env .env --limit 10
python -m testwins publish artifacts/ux-review/proposals.json \
  --project /repo/aplikacji --include-candidates
```

Przykład korzysta z istniejącej publicznej trasy `repair-agent/repair-plan`.
Inną parę application/function musi znać polityka subllm. Nie dodajemy potajemnie
trasy `testwins` w drugim repozytorium. Modele, kolejność i failover pochodzą
z subllm; raport zapisuje rzeczywiście zwrócony model i providera. Jeżeli
korzystasz z `SUBLLM_POLICY_FILE`, eksportuj go do środowiska procesu zgodnie
z API subllm 1.14.0; samo `--env` Testwins nie zastępuje konfiguracji SDK.

Klient wykonuje jedno logiczne wywołanie z ograniczonym czasem. Liczbę prób
providerów i budżety modelu kontroluje polityka subllm. Wymagana jest jawna
kolejność providerów oraz zgoda na transfer zdalny. Trasy uruchamiające lokalnych
agentów CLI/Cursor są odrzucane; ten konsument tworzy wyłącznie dane o naprawie.
Przekazuje ograniczony pakiet naruszeń i liczników, bez screenshotów, pełnego DOM
lub kodu źródłowego. Selektory i komunikaty też mogą zawierać dane aplikacji.

Wynik: `ux-review.json` i `proposals.json`. Każda propozycja ma znany identyfikator
dowodu, hipotezę przyczyny, zmianę UI, sposób regresji i wymóg przeglądu. Nieznane
pola, pominięte dowody i wymyślone identyfikatory są odrzucane. Raport wejściowy
jest sprawdzany pod kątem integralności i pozostaje niezmieniony. Wybór ograniczony
przez `--limit` jest jawny w `scope`. Brak naruszeń nie uruchamia modelu i nie
zmienia wyniku niekompletnego audytu na pozytywny.

Przekaż zaakceptowaną propozycję wykonawcy posiadającemu kod aplikacji, po czym
uruchom ten sam scenariusz ponownie. Black-box nie zna ścieżek plików, więc
`files` pozostaje puste. Polecenie `publish` powyżej jest podglądem istniejącego
adaptera Planfile; rzeczywisty zapis wymaga jego jawnego `--apply`.

<!-- docs:section limitations -->
## Ograniczenia

Pomiary biegną od zaobserwowanego zdarzenia wejścia; obejmują próbkowanie i narzut
automatyzacji. Nie są metryką INP. Powiązanie czasowe nie dowodzi przyczynowości:
niezależny timer strony może spełnić ten sam selektor. Używaj izolowanych danych
oraz jednoznacznych stanów. Krótsze niż próbkowanie zmiany mogą zostać pominięte.
Próbnik nie mierzy klatek canvas/video ani percepcji człowieka. Animacje są
sprawdzane w ograniczonym oknie, nie przez cały czas życia aplikacji.

To nie jest automatyczna ocena całej architektury informacji, rozumienia tekstu,
przyzwyczajeń wszystkich odbiorców ani kompletności wzorca biznesowego. Raport
pozostawia niebadane warstwy jawne; LLM nie może ich dopisać jako zaliczonych.
Nie wykonuje patchy źródłowych. Istniejąca ścieżka `vision` nadal używa LiteLLM;
nowa ścieżka `ux-review` korzysta z subllm.

<!-- docs:section next_actions -->
## Weryfikacja i dalsze użycie

```bash
python -m pytest -q
CHROMIUM_EXECUTABLE=/sciezka/do/playwright/chrome python -m pytest -q -m browser
```

Testy obejmują negatywne kontrakty konfiguracji, pominięte pomiary, rzeczywiste
zdarzenia Chromium, status, fokus, ruch, raporty HTTP oraz eksport propozycji.
Dobierz własne selektory, budżety i scenariusze person przed użyciem na aplikacji.
Rozszerzenie zakresu o kolejne ekrany wymaga zadeklarowania ich w podróżach;
jeden udany scenariusz nie świadczy o reszcie produktu.

Weryfikacja tej zmiany (2026-09-23): 277 testów jednostkowych zaliczonych,
3 pominięte z powodu opcjonalnych integracji; 18 testów przeglądarkowych
zaliczonych, 1 timeout pobrania pliku. Ten sam timeout odtworzono na niezmienionej
rewizji bazowej `60a99ddc180f19225e951acd158ae7590360267e`; kontynuacja: PLF-002.
Wszystkie 37 nowych testów UX zaliczono (26 jednostkowych i 11 przeglądarkowych).
Przykład `examples/ux-lab` przez HTTP wykazał 3 naruszenia dla `?broken=1`
i 0 dla poprawnego wariantu; manifesty obu przebiegów zweryfikowano.
Zbudowano wheel/sdist i sprawdzono ich metadane przez Twine. Kontrola dokumentu
przypiętym checkerem wellmanifest/docs 0.1.0 przeszła lokalnie.

Pełny zestaw nie jest zielony z powodu wskazanego timeoutu. Lokalna konfiguracja
chronionego Validatora nie zawiera `semcod/testwins`, a repozytorium nie deklaruje
OneDev. Przypięcie dokumentacji i lokalne testy nie oznaczają wdrożonej bramy
CI ani zgody na samodzielne scalenie.
