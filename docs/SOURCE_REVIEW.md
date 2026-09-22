# Przegląd źródeł i pochodzenie

Testwins0.2 rozwija dostarczony UXMatrix Lab0.1, bez kopiowania projektu tests-twin-ux.
Pierwsza iteracja wykorzystała doświadczenia z jawnej konfiguracji środowiska, unikania
bezwzględnych ścieżek hosta i rozdzielania braku dowodów od PASS.

Aktualna iteracja używa publicznego API TestQL zamiast jego prywatnego runnera/CLI.
Źródło publicznego kontraktu odczytano2026-09-22. Wersja źródeł i wydanie PyPI różniły
się; obrazy/instalator wymagają jawnego TESTQL_REF. Nie zainstalowano TestQL w lokalnym
środowisku przygotowania i nie deklarujemy jego przejścia end-to-end.

Pełny bieżący przegląd reuse: [OSS_REUSE.md](OSS_REUSE.md).
Rzeczywiste wyniki: [STATUS](../verification/STATUS.md).

Źródła:
- https://github.com/clonerd-com/tests-twin-ux
- https://github.com/autogrammar/testql
- https://github.com/semcod/planfile
- https://github.com/wellmanifest/logs

Dla wellmanifest/docs podany wcześniej publiczny adres nie udostępniał dokumentacji.
Nie deklarowano niezweryfikowanej zgodności. Własne manifesty mają authority:none.
