# TW-BROWSER-UNAVAILABLE: Przeglądarka niedostępna

## Error DSL

```log-error-dsl
{"category":"DEPENDENCY","causes":["Brakuje binarnego pliku przeglądarki, sterownika lub działającego środowiska graficznego."],"code":"TW-BROWSER-UNAVAILABLE","doNot":["Nie zastępuj brakującego testu wynikiem PASS.","Nie wklejaj tokenów, treści formularzy ani surowych logów do zdarzenia."],"meaning":"Wynik tej operacji jest niepełny lub odrzucony; nie dowodzi poprawności badanej aplikacji.","owner":"service:testwins","relatedEventTypes":["validation_failed","error_raised"],"remediation":["Zbuduj właściwy target obrazu, sprawdź architekturę CPU i uruchom ponownie tę komórkę."],"schema":"wellmanifest.logs/error/v1","severity":"ERROR","title":"Przeglądarka niedostępna","verification":["Wykonaj ponownie operację i sprawdź raport oraz integralność dowodów."],"version":1}
```

## Situation

Brakuje binarnego pliku przeglądarki, sterownika lub działającego środowiska graficznego.

## Meaning

Wynik tej operacji jest niepełny lub odrzucony; nie dowodzi poprawności badanej aplikacji.

## Safe resolution

Zbuduj właściwy target obrazu, sprawdź architekturę CPU i uruchom ponownie tę komórkę.

## Verification

Wykonaj ponownie operację i sprawdź raport oraz integralność dowodów.

## Do not

Nie zastępuj brakującego testu wynikiem PASS. Nie wklejaj tokenów, treści formularzy ani surowych logów do zdarzenia.

## Related events

validation_failed; error_raised. W dzienniku audytu informacje o zakresie są również wskazywane przez testwins.run_completed.

