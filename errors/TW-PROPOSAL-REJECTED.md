# TW-PROPOSAL-REJECTED: Odrzucona propozycja ticketu

## Error DSL

```log-error-dsl
{"category":"CONTRACT","causes":["Propozycja nie spełnia zamkniętego kontraktu albo próbuje nadać uprawnienia."],"code":"TW-PROPOSAL-REJECTED","doNot":["Nie zastępuj brakującego testu wynikiem PASS.","Nie wklejaj tokenów, treści formularzy ani surowych logów do zdarzenia."],"meaning":"Wynik tej operacji jest niepełny lub odrzucony; nie dowodzi poprawności badanej aplikacji.","owner":"service:testwins","relatedEventTypes":["validation_failed","error_raised"],"remediation":["Sprawdź wersję kontraktu i pola producenta; nie obchodź walidatora."],"schema":"wellmanifest.logs/error/v1","severity":"ERROR","title":"Odrzucona propozycja ticketu","verification":["Wykonaj ponownie operację i sprawdź raport oraz integralność dowodów."],"version":1}
```

## Situation

Propozycja nie spełnia zamkniętego kontraktu albo próbuje nadać uprawnienia.

## Meaning

Wynik tej operacji jest niepełny lub odrzucony; nie dowodzi poprawności badanej aplikacji.

## Safe resolution

Sprawdź wersję kontraktu i pola producenta; nie obchodź walidatora.

## Verification

Wykonaj ponownie operację i sprawdź raport oraz integralność dowodów.

## Do not

Nie zastępuj brakującego testu wynikiem PASS. Nie wklejaj tokenów, treści formularzy ani surowych logów do zdarzenia.

## Related events

validation_failed; error_raised. W dzienniku audytu informacje o zakresie są również wskazywane przez testwins.run_completed.

