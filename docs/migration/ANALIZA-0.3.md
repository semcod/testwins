# Analiza przesłanego projektu i plan zastąpienia go przez Testwins

## 1. Rekomendacja

Przenieść projekt do modelu **konfiguracja aplikacji + scenariusze domenowe + Testwins jako silnik audytu**. Zachować repozytorium specyfikacji Clonerd, ale docelowo usunąć z niego własne uruchamianie przeglądarek, detektory GUI, generowanie podstawowego raportu i harmonogram obserwacji.

Nie wykonywać samej podmiany `import twin_ux` na `import testwins`. Publiczny CLI Testwins 0.3.0 nie stanowi zamiennika API tych modułów. Poza GUI obecne persony sprawdzają API, a `cdp.py` zbiera telemetrię, której screenshot/DOM nie zastępuje.

Rekomendowana kolejność: **równoległy pomiar → uściślenie asercji → migracja scenariuszy → sprawdzenie braków → wyłączenie legacy**. Testwins pozostaje zależnością wersjonowaną, nie kopią źródeł rozklejoną w każdym projekcie.

## 2. Co faktycznie otrzymaliśmy

Analiza dotyczy wyłącznie przekazanych archiwów i załączonego Testwins 0.3.0; nie zakłada zgodności z ruchomym upstream `main`.

- Sześć funkcji testowych pytest, każda na desktop/tablet/smartphone: 18 przebiegów person w jednej przeglądarce Chromium.
- Sześć modułów person oraz moduły CDP, obserwacji i raportowania.
- Dziewięć wejściowych nawigacji UI po uwzględnieniu `mode`, `surface`, `view`, `tab`; wersja `layout` zależy od urządzenia.
- Raport: 57 pozytywnych obserwacji, 18 zestawów metryk, 18 screenshotów. Z dziesięciu zadeklarowanych kategorii heurystyk w danych są kategorie 1–8, nie 9 i 10.
- Manifest: 18 `PASS`, `assessment: passed`, 20 wpisów `findings`.
- Hashe wszystkich 18 screenshotów i dokumentu Markdown zgadzają się z manifestem. Nie stwierdzam uszkodzenia tych plików. Zgodność hashy nie dowodzi trafności ocen UX ani zgodności z zewnętrznym schematem.

W archiwach nie ma pełnej aplikacji, sposobu wdrożenia, konfiguracji CI, zależności serwera ani kontraktów testowych danych. Nie można na tej podstawie potwierdzić zachowania działającego portalu ani dobrać jego komendy startowej.

Źródła: `tests/test_digital_twin_personas.py`, `twin_ux/personas/*.py`, `reports/ux-report.json`, `reports/ux-report.report.json`. Wyniki obliczeń: `verification/report-integrity.json`.

## 3. Najważniejsze problemy istniejącego testera

| ID | Ustalenie z kodu | Konsekwencja i zmiana |
|---|---|---|
| L01 | `twin_ux/reporter.py:164–195,234–240`: wszystkie checks mają wpisane `PASS`, coverage liczone z już zebranych metryk, assessment stałe | Reporter nie propaguje błędów UX, nie odróżnia brakujących dowodów ani niewykonanych zaplanowanych komórek. Plan wykonania musi istnieć przed startem. |
| L02 | `tests/test_digital_twin_personas.py:90–177`: końcowe asercje dotyczą DOM/heap/style recalculation; brak asercji nad negatywnymi UXObservation | Negatywna obserwacja może nie zepsuć wyniku pytest. Oddzielić raportowanie od twardej bramki testowej. |
| L03 | `twin_ux/heuristics.py:42–56`: licznik bierze tylko zarejestrowane obserwacje; przy braku danych zwraca 100 | Usunąć interpretację jako pełnej zgodności UX; raportować sprawdzone kontrakty i luki. |
| L04 | `twin_ux/personas/customer.py:18–25`: pozytywna ocena braku blokującego logowania wpisana bez testu blokady | Zamienić narrację na jawny warunek dostępu do treści i brak blokującego dialogu. |
| L05 | `customer.py:54–69`, `developer.py:51–109`, `manager.py:29–39`, `cto.py:83–93`: część brakujących elementów nie ma negatywnej ścieżki raportowania | Brak kontrolki ma być fail/blocked/not applicable z uzasadnieniem, a nie milczącym zniknięciem testu. |
| L06 | `accountant.py:21–29,43–51,71–79`: proste wyszukanie tekstu lub kontrolki prowadzi do szerokich opisów zgodności i działania | Obecność NIP/napisu nie dowodzi weryfikacji procesu, a przycisk PDF nie dowodzi pobrania dokumentu. Zawęzić twierdzenia i dołożyć testy skutku. |
| L07 | `manager.py:19–38`, `ceo.py:19–28`, `cto.py:19–30,83–92`: widoczność/kilka słów/liczba elementów zastępują testy interaktywności, wydajności lub noVNC | Oddzielić obecność widoku od funkcjonalności, aktualności danych i czasu odpowiedzi. |
| L08 | `developer.py:55,88–89`: stałe sleep i warunek całkowitego usunięcia modala z DOM | Używać oczekiwania na stan, nie czasu; prawidłowo ukryty, nadal istniejący modal nie jest błędem zamykania. |
| L09 | `tests/test_digital_twin_personas.py:72–84`: screenshoty dopiero po powrocie całej persony, `full_page=False` | Brak zdjęć otwartej palety, wyników wyszukiwania, macierzy i faktur. Dowód musi powstać w chwili badanego stanu, również po błędzie. |
| L10 | `twin_ux/reporter.py:197–204`: tylko pierwszych 20 obserwacji i puste evidence_ids | Manifest gubi 37 z 57 obserwacji; powiązać każde ustalenie z konkretnym stanem i dowodem. |
| L11 | `tests/conftest.py:15,18–29,48–55`; `tests/test_digital_twin_personas.py:21–22,67` | Lokalna ścieżka użytkownika, mkdir przy imporcie, systemowa przeglądarka, skip przy jej braku, wyłączony sandbox i bypass CSP. Zastąpić kontrolowanym środowiskiem i niekompletnym wynikiem przy braku narzędzi. |
| L12 | `ceo.py:42–81`, `cto.py:44–81`: bezpośrednie HTTP, w tym POST do `/api/auto/cycle` | To nie jest audyt oparty tylko na GUI. Zachować jako testy API; operacje z potencjalnymi skutkami uruchamiać tylko na jawnie autoryzowanych, izolowanych danych. |

Kontrolne wykonanie L01/L03 nie korzystało z portalu: pusty auditor dał 100%; jedna syntetyczna negatywna obserwacja wraz z metryką i bez zdjęcia dała w manifest `PASS`, `assessment: passed`, `coverage: complete`. Wynik: `verification/legacy-probes.json`. To dowód błędu reportera, **nie dowód nieprawidłowego działania aplikacji**.

## 4. Co zachować, co zastąpić

| Obecny element | Docelowa odpowiedzialność |
|---|---|
| `tests/conftest.py` — lifecycle przeglądarki, ścieżki screenshotów | Testwins/Docker i konfiguracja środowiska, bez hostowego profilu użytkownika |
| `twin_ux/heuristics.py` | Reguły Testwins i jawne kontrakty UI; kategoria heurystyki może pozostać etykietą raportu domenowego |
| `twin_ux/reporter.py` | Raport Testwins oraz ewentualny osobny eksporter zgodności; nie przebudowywać całego silnika |
| `twin_ux/cdp.py` | Sterowanie UI w runnerze; pomiary Performance zachować tymczasowo jako osobny probe Chromium |
| `twin_ux/personas/*.py` | Wiedza domenowa, jawne dane, scenariusze TestQL/Playwright/Testwins; usuwać kod dopiero po migracji jego kontraktów |
| `reports/` | Niezmienna historia, nie automatycznie zatwierdzony baseline |
| `tests/test_digital_twin_personas.py` | Czasowo dotychczasowy zestaw z naprawionymi asercjami; docelowo plan scenariuszy i twarda bramka CI |

Wariant minimalny: pozostawić pytest, uruchamiać CLI Testwins obok niego. Nie ma w Testwins 0.3 gotowego publicznego pluginu pytest ze zgodnym API `HeuristicsAuditor` czy `CDPSessionWrapper`. Runner jest asynchroniczny, a legacy używa sync Playwright; bezpośrednie mieszanie tych obiektów nie jest bezpiecznym skrótem migracji.

Wariant docelowy: lokalny pakiet domenowy Clonerd ma tylko konfigurację, scenariusze i dane. Testwins obsługuje pomiar, dowody, alerty i integrację Planfile; TestQL może wykonywać scenariusze. Zewnętrzne kontrole pytest można okresowo uruchamiać przez jawne polecenie shell w zadaniu TestQL, ale zielony wrapper nie naprawi źle skonstruowanych asercji w środku.

## 5. Migracja sześciu person bez utraty funkcji

| Persona | Kontrakty UI do przeniesienia | Zakres, którego sam obraz/DOM nie potwierdzi |
|---|---|---|
| Customer | Dostęp do startu, minimum liczby planów, konkretne ceny i limity, wybór planu, widoczność/aktywność CTA, responsywność | Zaksięgowanie płatności, poprawność rozliczeń, dostępność obu providerów; testować w sandboxie |
| Developer | Osobno przycisk i skrót, paleta otwarta, tekst `taskand` w wynikach, brak widocznego modala po Escape/przycisku, powrót fokusu | Skuteczne wykonanie procedury po jej wybraniu; potrzebny świadomy kontrakt |
| Manager | Macierz na odpowiedniej trasie, rzeczywiste przełączenie roli i zmiana widocznych uprawnień, wpisy audytu | Egzekwowanie RBAC przez backend i niezmienność dziennika |
| Accountant | Widok faktur, wymagane pola, komunikat statusu, dostępny przycisk pobrania | Pobranie właściwego pliku, poprawność danych dokumentu i rzeczywisty status integracji; nie deklarować zgodności na podstawie napisu |
| CEO | Osobno kafelki KPI i rzeczywiste wykresy; jawny stan danych/odświeżenia | `/api/auto/cycle`, skutki wykonania oraz pełna walidacja odpowiedzi; uruchamiać raz na zestaw API, nie raz na viewport |
| CTO | Rejestr hostów, konkretne wymagane pola, otwarcie i gotowość noVNC | Kontrakt `/v1/menu`, wykonanie Taskand i stan infrastruktury; testy usług lub sterowanej sesji |

W nowych scenariuszach używać stabilnego `check_id` niezależnego od języka tytułu. Powiązać go z personą, scenariuszem, krokiem, URL-em, przeglądarką, urządzeniem i danymi testowymi. Jest to **proponowany kontrakt migracji**, nie dodatkowe akceptowane pola w obecnym zamkniętym YAML Testwins. Metadane aplikacji można na początek trzymać w osobnym `inventory.json` i kodować personę w ID sceny.

## 6. Pułapki po stronie Testwins 0.3.0

1. **Nie ma pełnej zgodności funkcjonalnej z legacy.** Konfiguracja obsługuje widoczność, ukrycie, tekst, count, URL i changed. Asercje atrybutów, nazw dostępności, złożonych zależności danych i download wymagają dodatkowego runnera lub rozszerzenia.
2. **PDF:** `testwins/browser.py:context_options` ustawia `accept_downloads=False`; nie obiecywać pobierania faktur istniejącym runnerem bez świadomej zmiany lub osobnego scenariusza Playwright.
3. **Sesje:** nowy kontekst na scenę; brak `storage_state` w zamkniętym schemacie konfiguracji. Nie dopisywać nieobsługiwanego `auth:`. Stan uwierzytelnienia i powiązania kolejnych ekranów trzeba zaprojektować.
4. **Różne URL-e dla urządzeń:** stary kod przełącza `layout=onepage` wyłącznie dla smartphone. Sam viewport nie wystarczy. Starter ma dwa rzeczywiste pliki audytu oraz dwa sites live. Nazwa `mobile` mapuje wcześniejsze `smartphone`.
5. **Live to aktualny viewport i kontrakty do odczytu**, nie wykonanie pełnych person, scrollowania wszystkich ekranów ani API POST. Gorąca strona nie jest automatycznie otwartą paletą. Stany modali sprawdza oddzielny scenariusz.
6. **Brak automatycznej wspólnej analityki każdego rodzaju wyniku.** `suite` scala wyniki kroków web/task, ale nie jest gotowym importerem wszystkich obserwacji starego `ux-report.json` do live SQLite.
7. **Twarde asercje a powtarzalność:** `reporting.py:24–38` wymaga dwóch stabilnych powtórzeń do `confirmed`; `cli.py:101–103` opiera kod zakończenia na completeness/confirmed. Sporadyczny błąd końcowej asercji może pozostać kandydatem, więc bramka zastępująca pytest powinna dodatkowo odczytywać wszystkie `checks` i blokować niespełnione obowiązkowe kroki.
8. **Inna skala screenshotów:** Testwins robi `scale='css'` (`runner.py:185`). Legacy mobile ma 1170×2532, nowy profil CSS 390×844. Przeskalowanie nie odtworzy DOM, maskowania, wersji fontów i punktu scenariusza. Zebrać świeże, zatwierdzone baseline'y.
9. **CSP, SW i allowlist:** nie przejmować `bypass_csp=True`. Domyślne blokowanie service workers i zasobów z innych originów może zmienić zachowanie aplikacji; jawnie uzgodnić środowisko, nie zgłaszać każdej różnicy jako defektu produktu.
10. **Schemat raportu:** Testwins używa własnego `testwins.report-manifest/v1`, nie identycznego sidecar starego projektu. Jeżeli odbiorcy wymagają wellmanifest, zbudować cienki eksporter, zachować hash oryginału i walidować rzeczywistym dostępnym schematem. Nie deklarować zgodności przez zmianę pola `schema`.

To są ustalenia z dołączonych źródeł, nie twierdzenie o wszystkich przyszłych wersjach bibliotek.

## 7. Etapy wdrożenia i kryteria odbioru

### Etap A — wiarygodny punkt wyjścia

Zamrozić zipy i aktualny raport jako historię, wskazać dane demo i stałą wersję aplikacji. Naprawić powiązanie niepowodzeń z pytest, brak danych zamiast 100%, planowane 18 komórek i brak screenshotu. Każdemu kontraktowi przypisać własne ID. Nie uznawać poprzedniego `100%` za wymaganie zgodności nowych pomiarów.

### Etap B — audyt Testwins obok legacy

Uruchomić starter na tym samym izolowanym środowisku. Na początek Chromium i trzy profile. Zgromadzić pomiary błędów geometrii i luki, bez automatycznych napraw, publikacji ticketów ani wywołań LLM. Wyjaśnić różnice wynikające z fontów, CSP, danych i stanu kontekstu. Baseline przyjmować dopiero po przeglądzie.

### Etap C — migracja zachowania

Przenieść najpierw paletę, później customer, manager, accountant, CEO/CTO. Każda obserwacja, która dotychczas była tylko narracją, dostaje jawne warunki albo status wymagający manualnego przeglądu. Zachować metryki Performance oddzielnie; nie przemianowywać czasu skanu na czas renderowania aplikacji.

Testy API przenieść do osobnego zakresu; kontrakt read-only `/v1/menu` nie musi być powtarzany dla urządzeń. POST `/api/auto/cycle` pozostaje domyślnie poza monitorowaniem GUI i wymaga izolacji oraz zgody operatora.

### Etap D — bramka i kontrolowane defekty

Przed wyłączeniem legacy porównać zaplanowane ID, wykonane asercje, naruszenia, luki i dowody. Minimalne próby: usunięta paleta; celowo błędne filtrowanie; modal ukryty, lecz nadal obecny w DOM; zasłonięty CTA; przepełniona karta mobile; brak faktury; uszkodzone pobieranie; brak przeglądarki; przerwany pomiar; brak wymaganego screenshotu. Każdy przypadek musi mieć oczekiwany status.

Wymagane 18 kombinacji persony i urządzenia mają być jawnie rozliczone w planie biznesowym, a zakresy API osobno. `not_run`, `blocked`, `validated` lub brak danych nie mogą być traktowane jako zdany obowiązkowy test. Podczas przejścia pytest pozostaje bramką dla zakresów jeszcze nieprzeniesionych.

### Etap E — wyłączenie własnego silnika

Gdy wszystkie wymagane kontrakty mają nowego wykonawcę, przenieść legacy do archiwum i usunąć produkcyjne importy. Zachować prosty punkt wejścia `make ux-test`/`make ux-watch`, ale kierować go do Testwins. WUP używa tej samej konfiguracji live; nie potrzebuje drugiego zestawu detektorów.

## 8. Proponowany backlog, nie opublikowane tickety

| ID | Zadanie | Kryterium ukończenia |
|---|---|---|
| MIG-01 | Naprawić stare wyniki i ustalić inventory | Negatywna obserwacja nie może dać PASS; brak zaplanowanego przebiegu to luka |
| MIG-02 | Dodać Testwins jako przypiętą zależność i job obok legacy | Zbierane są kompletne artefakty, statusy i środowisko |
| MIG-03 | Ustalić stan sesji i wejścia per urządzenie | Wszystkie trasy otwierają właściwy stan na zimnym kontekście albo mają jawny setup |
| MIG-04 | Migrować paletę i stany pośrednie | Otwarcie, trafność wyników, zamknięcie oraz odpowiednie dowody |
| MIG-05 | Migrować customer/manager/accountant | Kontrakty widoczności nie udają płatności, RBAC lub weryfikacji dokumentów |
| MIG-06 | Wydzielić API i CDP Performance | Zachowane zakresy, bez mutującego API w pętli GUI |
| MIG-07 | Rozszerzyć download/auth/obsługę trudniejszych asercji | Rzeczywiste testy integracyjne, nie tylko obecność pól w konfiguracji |
| MIG-08 | Dodać bramkę funkcjonalną i porównanie pokrycia | Pojedynczy obowiązkowy niespełniony krok nie przechodzi mimo braku confirmed |
| MIG-09 | Dodać exporter/zgodność historycznych raportów | Każde ustalenie ma dowód; jawne luki; walidacja wymaganym schematem |
| MIG-10 | Włączyć live, Planfile i opcjonalny LLM | Kontrolowane koszty, deduplikacja i review; brak automatycznych skutków z tekstu strony |

## 9. Weryfikacja i źródła

W tej iteracji wykonano: analizę źródeł; odczyt raportów i screenshotów; weryfikację 19 hashy; dwie kontrolne próby starego reportera; walidację 3 plików Testwins i 27 celów live; 10 testów startera. **Nie wykonano testów działającego Clonerd, Dockera, live watch, płatności, API, TestQL SDK ani LLM.**

Uzupełniające źródła pierwotne do projektu migracji:

- Playwright Python, BrowserType: CDP tylko dla Chromium i ograniczenia zgodności połączenia — https://playwright.dev/python/docs/api/class-browsertype
- Playwright Python, Assertions: asercje widoczności, ukrycia, atrybutów, wartości, URL i timeout — https://playwright.dev/python/docs/test-assertions
- Playwright Python, Other locators: `:visible`, `:has-text`, `:nth-match` użyte w częściowym przykładzie palety — https://playwright.dev/python/docs/other-locators
- Playwright Python, Downloads: odbieranie zdarzenia download zamiast testu samego istnienia przycisku — https://playwright.dev/python/docs/downloads

Pierwszeństwo dla opisu aktualnego projektu mają przesłane pliki. Nie zmieniono oryginalnych archiwów ani repozytoriów.
