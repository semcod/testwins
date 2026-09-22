# TW-CAPTURE-FAILED: Nie udało się zebrać obserwacji UI

## Error DSL

```log-error-dsl
{"category":"RUNTIME","causes":["Nawigacja, gotowość strony lub kolektor nie zakończyły się poprawnie."],"code":"TW-CAPTURE-FAILED","doNot":["Nie zastępuj brakującego testu wynikiem PASS.","Nie wklejaj tokenów, treści formularzy ani surowych logów do zdarzenia."],"meaning":"Wynik tej operacji jest niepełny lub odrzucony; nie dowodzi poprawności badanej aplikacji.","owner":"service:testwins","relatedEventTypes":["validation_failed","error_raised"],"remediation":["Sprawdź URL, port, ready_selector i ograniczenia przeglądarki; odtwórz w noVNC."],"schema":"wellmanifest.logs/error/v1","severity":"ERROR","title":"Nie udało się zebrać obserwacji UI","verification":["Wykonaj ponownie operację i sprawdź raport oraz integralność dowodów."],"version":1}
```

## Situation

Nawigacja, gotowość strony lub kolektor nie zakończyły się poprawnie.

## Meaning

Wynik tej operacji jest niepełny lub odrzucony; nie dowodzi poprawności badanej aplikacji.

## Safe resolution

Sprawdź URL, port, ready_selector i ograniczenia przeglądarki; odtwórz w noVNC.

## Verification

Wykonaj ponownie operację i sprawdź raport oraz integralność dowodów.

## Do not

Nie zastępuj brakującego testu wynikiem PASS. Nie wklejaj tokenów, treści formularzy ani surowych logów do zdarzenia.

## Related events

validation_failed; error_raised. W dzienniku audytu informacje o zakresie są również wskazywane przez testwins.run_completed.

