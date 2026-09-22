# TW-CELL-FAILED: Niekompletna komórka macierzy

## Error DSL

```log-error-dsl
{"category":"RESOURCE","causes":["Limit czasu albo awaria zatrzymały urządzenie lub scenariusz."],"code":"TW-CELL-FAILED","doNot":["Nie zastępuj brakującego testu wynikiem PASS.","Nie wklejaj tokenów, treści formularzy ani surowych logów do zdarzenia."],"meaning":"Wynik tej operacji jest niepełny lub odrzucony; nie dowodzi poprawności badanej aplikacji.","owner":"service:testwins","relatedEventTypes":["validation_failed","error_raised"],"remediation":["Zmniejsz zakres lub zwiększ uzasadniony limit; sprawdź zasoby i powtórz test."],"schema":"wellmanifest.logs/error/v1","severity":"ERROR","title":"Niekompletna komórka macierzy","verification":["Wykonaj ponownie operację i sprawdź raport oraz integralność dowodów."],"version":1}
```

## Situation

Limit czasu albo awaria zatrzymały urządzenie lub scenariusz.

## Meaning

Wynik tej operacji jest niepełny lub odrzucony; nie dowodzi poprawności badanej aplikacji.

## Safe resolution

Zmniejsz zakres lub zwiększ uzasadniony limit; sprawdź zasoby i powtórz test.

## Verification

Wykonaj ponownie operację i sprawdź raport oraz integralność dowodów.

## Do not

Nie zastępuj brakującego testu wynikiem PASS. Nie wklejaj tokenów, treści formularzy ani surowych logów do zdarzenia.

## Related events

validation_failed; error_raised. W dzienniku audytu informacje o zakresie są również wskazywane przez testwins.run_completed.

