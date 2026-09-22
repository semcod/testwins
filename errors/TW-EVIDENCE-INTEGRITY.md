# TW-EVIDENCE-INTEGRITY: Naruszona integralność dowodów

## Error DSL

```log-error-dsl
{"category":"CHAIN","causes":["Hash pliku lub ciąg zdarzeń różni się od zapisanego manifestu."],"code":"TW-EVIDENCE-INTEGRITY","doNot":["Nie zastępuj brakującego testu wynikiem PASS.","Nie wklejaj tokenów, treści formularzy ani surowych logów do zdarzenia."],"meaning":"Wynik tej operacji jest niepełny lub odrzucony; nie dowodzi poprawności badanej aplikacji.","owner":"service:testwins","relatedEventTypes":["validation_failed","error_raised"],"remediation":["Odtwórz artefakty z zaufanej kopii lub wykonaj nowy audyt; zachowaj wadliwy pakiet do analizy."],"schema":"wellmanifest.logs/error/v1","severity":"ERROR","title":"Naruszona integralność dowodów","verification":["Wykonaj ponownie operację i sprawdź raport oraz integralność dowodów."],"version":1}
```

## Situation

Hash pliku lub ciąg zdarzeń różni się od zapisanego manifestu.

## Meaning

Wynik tej operacji jest niepełny lub odrzucony; nie dowodzi poprawności badanej aplikacji.

## Safe resolution

Odtwórz artefakty z zaufanej kopii lub wykonaj nowy audyt; zachowaj wadliwy pakiet do analizy.

## Verification

Wykonaj ponownie operację i sprawdź raport oraz integralność dowodów.

## Do not

Nie zastępuj brakującego testu wynikiem PASS. Nie wklejaj tokenów, treści formularzy ani surowych logów do zdarzenia.

## Related events

validation_failed; error_raised. W dzienniku audytu informacje o zakresie są również wskazywane przez testwins.run_completed.

