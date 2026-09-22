# Standardy dowodów i logów

## Rzeczywisty punkt odniesienia

Sprawdzono kod i kontrakt `wellmanifest/logs`, a nie tylko opis README. W odczytanym repozytorium checker odwołuje się do `contracts/logs.contract.v0.5.json` z wersją **0.5.0**. Zdarzenie ma identyfikator schematu `wellmanifest.logs/event/v1`; wersja bundle i wersja nazwy eventu nie są tym samym.

Własny emitter stosuje ograniczony profil tego eventu: stały zestaw pól, sekwencję, UTC, causation/correlation, osobne producer/source, identyfikatory podmiotu, wynik, stan, odwołania do dowodów, hash wejścia i łańcuch SHA-256. Pierwszy `previousHash` jest zerowym początkiem łańcucha, **nie fałszywym hashem Git**. `receiptRef` jest null, gdy nie ma rzeczywistego receipt.

Geometria i wyniki modeli zawierające liczby zmiennoprzecinkowe nie są osadzane w eventach. Event wskazuje pliki przez ścieżkę i hash. JSON jest kanoniczny: posortowane klucze, bez zbędnych spacji, UTF-8. `eventHash` oblicza się po usunięciu samego pola `eventHash`.

`rawOutputIncluded=false` i `secretMaterialIncluded=false` opisują ograniczony event, nie stanowią gwarancji anonimizacji wszystkich zrzutów. Prywatność dowodów wymaga odrębnych masek i przeglądu.

## Dwa poziomy walidacji

```bash
python -m testwins verify /raport/run
make conformance RUN=/raport/run LOGS_ROOT=/zaufany/checkout/wellmanifest-logs
```

Pierwsza komenda sprawdza lokalny profil, łańcuch, lifecycle, manifest, ścieżki i hashe plików. Nie twierdzi, że zastępuje pełną walidację upstream.

Druga importuje **kod** `standard/logs_check.py` ze wskazanego, zaufanego checkoutu operatora. Wczytuje jego kontrakt, weryfikuje dokumenty błędów, JSON Schema zdarzeń i wywołuje `validate_event()` dla każdego wpisu. Wynik wskazuje hashe checkera i kontraktu oraz zostaje zapisany w `analysis/<run-id>/logs-conformance.json`, bez zmiany oryginalnego runu. Nie używaj checkoutu dostarczonego przez badaną stronę — import to wykonanie kodu.

Ta integracja nie implementuje usług RPC, protokołu append/check-and-swap całego upstream ani podpisów autentyczności. Nie nadaje uprawnień pracy wykonawcy. Weryfikacja upstream nie została wykonana podczas tworzenia paczki, ponieważ dostępny terminal nie mógł pobrać checkoutu, a nie było jego lokalnej kopii. Tool nie wypisuje sukcesu, gdy checkoutu brakuje.

## Dokumenty błędów

`errors/*.md` zawierają zamknięte definicje `wellmanifest.logs/error/v1` w kanonicznym jednoliniowym bloku `log-error-dsl`, tytuł zgodny z kodem oraz sekcje Error DSL, Situation, Meaning, Safe resolution, Verification, Do not, Related events. Opisują błędy infrastruktury i kontraktu adaptera. Reguły UX są osobnym katalogiem w RULES.md; dynamiczne reguły axe-core nie są udawane jako komplet własnego katalogu błędów protokołu.

## Dlaczego manifest raportu ma własny schemat

Podany adres `https://github.com/wellmanifest/docs` zwrócił publicznie 404. Nie dało się ustalić, czy repozytorium jest prywatne, usunięte, przeniesione, czy adres jest nieaktualny. Nie przypisano mu zmyślonych zasad i nie oznaczono raportu jako certyfikowanego przez ten standard.

Manifest `testwins.report-manifest/v1` ma `authority: none`, rozróżnienie incomplete/findings/no_confirmed_findings, licznik rzeczywiście obserwowanych komórek, listę dowodów z rozmiarem i SHA-256, jawne statusy obu integracji oraz ograniczenie redakcji. Gdy dostępny będzie autorytatywny kontrakt docs, należy dodać osobny adapter i test zgodności, a nie zmienić tylko nazwę schematu.

## Integralność nie jest autentycznością

Hash wykrywa niezgodność treści z zapisanym manifestem, lecz osoba mogąca przepisać cały raport i cały łańcuch może obliczyć nowe hashe. Zaufane archiwum, podpis lub zakotwiczenie głowy łańcucha w zewnętrznym rejestrze to osobna warstwa. Ta wersja nie twierdzi, że ją zapewnia.

Źródła: [logs](https://github.com/wellmanifest/logs), [kontrakt](https://github.com/wellmanifest/logs/blob/main/contracts/logs.contract.v0.5.json), [checker](https://github.com/wellmanifest/logs/blob/main/standard/logs_check.py), [adres docs wymagający wyjaśnienia](https://github.com/wellmanifest/docs).
