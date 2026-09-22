# Publikacja i dystrybucja Testwins 0.4.0

Dystrybucja Python nazywa się `testwins`, console script również `testwins`. Metadane mają status Alpha.
Wydanie zawiera wheel, sdist i pełny ZIP. **Nie wykonano publikacji, rezerwacji nazwy PyPI, wdrożenia domeny ani push/PR**.
Wybór nazwy w metadanych nie potwierdza prawa do publikowania na danym indeksie ani posiadania domeny.

```bash
make test
make test-browser
make package-final
# Po instalacji narzędzia twine:
python -m twine check dist/*.whl dist/*.tar.gz
```

`make package-final` buduje dystrybucje, synchronizuje profil Clonerd, tworzy ZIP z nimi i sprawdza jego manifest SHA-256.
Nie zawiera credentiali, wag modeli ani zależności przeglądarek. ZIP zawiera źródła/Makefile/landing, wheel również
profile `testwins init`, natomiast sdist zawiera źródła i dokumentację do odtworzenia. Ciężkie screenshoty są osobnym dowodem,
nie warunkiem instalacji. Hash jest kontrolą integralności, nie podpisem wydawcy.

Po weryfikacji konta, praw do nazwy, licencji i docelowego SDK można świadomie wykonać:

```bash
python -m twine upload --repository testpypi dist/*.whl dist/*.tar.gz
# Osobna decyzja o indeksie produkcyjnym:
python -m twine upload dist/*.whl dist/*.tar.gz
```

Powyższych poleceń nie wykonuje żaden instalator/CI. Tokeny przechowuj poza repozytorium; skonfiguruj publikowanie
z ograniczonymi uprawnieniami w wybranym środowisku. Nie kieruj `twine` na cały `dist/*`, bo katalog zawiera też ZIP i checksums.

## Reprodukowalność

Zakresy zależności Python nie są lockfile; `TESTQL_REF=main` i `PLANFILE_REF=main` są ruchome. Przypnij przejrzane
commity SDK, digesty obrazów i zestaw pakietów na docelowej architekturze przed produkcyjnym rolloutem.
Lokalne wersje użyte w tym wydaniu opisuje `verification/environment.json`. Playwright użyty lokalnie i w Dockerfile
mogą się różnić; nie należy ekstrapolować wyników jednego stosu na drugi.

TestQL jest osobnym extra. Polecenia korzystające z jego SDK raportują niekompletność, gdy brakuje publicznego API.
`doctor` tylko pokazuje dostępność; obowiązkowy test backendu to `tools/verify_testql.py`. SDK z PyPI i Git mogą się różnić.
Modele i Ultralytics mają własne licencje; nie zostały skopiowane ani sublicencjonowane jako MIT Testwins.
