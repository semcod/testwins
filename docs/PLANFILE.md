# Integracja Planfile

Przejrzany punkt odniesienia: publiczne `semcod/planfile`, kod `main` z deklaracją wersji **0.1.126**, odczyt 2026-09-22. Numer pochodzi z repozytorium, nie z przeprowadzonego tu testu instalacji PyPI. Ruchomy branch należy zastąpić zweryfikowanym commitem przed stabilnym wdrożeniem.

## Kontrakty

Producent generuje `planfile.ticket-proposal.v1`: `proposal_id`, `dedupe_key`, `name`, `description`, `priority`, `source`, `labels`, `files`, `acceptance_criteria`, `evidence_refs`. W `source` znajdują się narzędzie, jego wersja, identyfikator obserwacji i hash raportu. `files` pozostaje puste: badanie black-box nie daje uprawnienia do wymyślania, w którym pliku kodu znajduje się problem.

Nie ma pól queue, executor, capability, approval, transport ani instrukcji uruchamiania. Lokalny validator odrzuca dodatkowe pola; przed materializacją wybrana partia jest walidowana przez **rzeczywisty** `planfile.contracts.TicketProposalV1`. Cała partia jest sprawdzana przed pierwszym zapisem ticketu.

Następnie adapter używa `to_ticket_kwargs()` oraz `Planfile.create_ticket_deduplicated(dedupe_key=..., ...)`. Nie parsuje tekstowego CLI i nie implementuje własnego zapisu do struktury `.planfile`. Brak tej metody w zainstalowanej wersji kończy publikację błędem; nie ma cichego fallbacku na nieatomowe create.

## Bramka przeglądu

`make publish` bez `APPLY=1` jest podglądem. Nie wymaga SDK Planfile w obrazie przeglądarek i nie zmienia kolejki. Jest to walidacja lokalnego profilu producenta; pełna walidacja SDK następuje dopiero w kroku apply.

Przy apply nowe tickety otrzymują domyślnie `needs-human` i `executor=None`. Obserwacja strony, nawet powtarzalna, nie ma sama nadawać uprawnień automatycznemu wykonawcy. `READY=1` nie dodaje tej bramki do **nowych, potwierdzonych** zadań, ale nie wybiera executora i nie uruchamia pracy. Nie usuwa etykiet z istniejącego ticketu zwróconego przez deduplikację. Zmiana stanu istniejącego zadania wymaga świadomego użycia mechanizmów Planfile.

`INCLUDE_CANDIDATES=1` dopuszcza kandydatów do publikacji z przeglądem. Połączenie tego parametru z `READY=1` jest odrzucane.

## Limit i kolejne partie

Domyślnie wybieranych jest do 25 propozycji. Odpowiedź ma `eligible_total`, `offset` i `next_offset`. Wartość limitu to maksymalnie 500. Aby opublikować kolejną partię tego samego raportu:

```bash
make publish PLANFILE_PROJECT=/projekty/sklep APPLY=1 TICKET_LIMIT=25 TICKET_OFFSET=25 \
  PLANFILE_REF=<rzeczywisty-sprawdzony-SHA>
```

Dla raportu zawierającego 44 propozycje można wybrać np. `TICKET_LIMIT=100`. Nie należy udawać, że ograniczona partia obejmuje cały raport. Zmiana raportu może zmienić kolejność, więc offset odnosi się do konkretnego, niezmiennego pliku propozycji.

Deduplikacja Planfile chroni aktywne zadania przed tworzeniem kolejnego ticketu z tym samym kluczem. Po zamknięciu lub anulowaniu starego zadania ponowne wystąpienie może dać nowy ticket regresji. Ta wersja **nie aktualizuje automatycznie treści istniejącego ticketu, nie zamyka go po zniknięciu obserwacji i nie usuwa starego dowodu**. Brak obserwacji w nowym raporcie może oznaczać pominięty stan, błąd infrastruktury lub zmianę selektora, a nie naprawę.

## Uruchomienie bez wrappera Docker

```bash
python -m testwins publish /raport/proposals.json --project /projekty/sklep
python -m testwins publish /raport/proposals.json --project /projekty/sklep \
  --apply --limit 100 --receipt /raporty-publikacji/receipt.json
```

W tym trybie SDK musi być zainstalowane w używanym środowisku Python. Receipt zapisuj poza zamkniętym katalogiem audytu. Wrapper `make publish` buduje osobny obraz, montuje raport read-only i wyłącznie `.planfile` do zapisu, uruchamia bez sieci i zapisuje stdout publikacji w `.testwins/<instance>/publish-<time>.json`.

Referencje `testwins-artifact:<run>/<path>#sha256:<digest>` są identyfikatorami dowodów, nie publicznymi URL-ami. Zachowaj i udostępnij właściwy pakiet raportu wykonawcy. Ten projekt nie przesyła sam plików do GitHub Issues ani nie konfiguruje zewnętrznego magazynu obiektowego.

## Zakres testów integracji

Testy jednostkowe sprawdzają kontrakt adaptera, gate i deduplikację na jawnych doubles. **Nie są opisane jako wykonany test SDK Planfile.** Obraz publishera zawiera kontrolę obecności publicznych kontraktów przy budowaniu, ale build i prawdziwy zapis do Planfile nie były możliwe w środowisku przygotowania tej paczki. Wynik sprawdź na lokalnym projekcie testowym przed połączeniem z autonomicznym wykonawcą.

Źródła: [publiczne kontrakty](https://github.com/semcod/planfile/blob/main/docs/PUBLIC_CONTRACTS.md), [modele propozycji](https://github.com/semcod/planfile/blob/main/planfile/contracts.py), [API i deduplikacja](https://github.com/semcod/planfile/blob/main/planfile/__init__.py).
