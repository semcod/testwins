# Przegląd OSS — stan odczytany 2026-09-22

To przegląd dokumentacji/źródeł pierwotnych, nie benchmark skuteczności.
"Adapter" oznacza kod w tej paczce, nie automatyczne potwierdzenie testu end-to-end.
Rzeczywistą weryfikację wskazuje osobny STATUS.

| Projekt | Przydatność | Stan w Testwins |
|---|---|---|
| TestQL | DSL shell/WWW/API, publiczne wyniki batch verification | **Adapter SDK**, bootstrap i scenariusze |
| Playwright | renderowanie i interakcje browser; CDP tylko Chromium | **Rdzeń** macierzy i DOM |
| noVNC + Xvfb + Fluxbox | obserwacja izolowanego pulpitu przez przeglądarkę | **Docker** laboratoryjny |
| axe-core | deterministyczne reguły dostępności WWW | **Integracja** odziedziczona w obrazie |
| LiteLLM | wspólny klient różnych providerów, image_url, supports_vision | **Adapter**, przed/po, limity, kandydaci |
| OpenCV | kontury, template matching | **Wykonane lokalnie** i adapter desktop |
| Ultralytics YOLO | detekcja obiektów/regionów obrazu | **Adapter**, lokalne zaufane wagi, kafle/NMS |
| Pexpect | proces interaktywny / terminal POSIX | **Adapter i rzeczywiste testy PTY** |
| PyAutoGUI + MSS | screenshot i jawne wejście pulpitu | **Adapter**, dedykowany worker X11 |
| Microsoft OmniParser | regiony interaktywne i opis ikon na screenshotach | **Punkt importu generic regions** po konwersji; bez pełnego silnika |
| Appium | testy przez drivery urządzeń/platform | **Kierunek/oddzielny worker**, nie backend tej wersji |
| Airtest | visual automation aplikacji/gier i urządzeń | **Alternatywa**, bez wbudowanego adaptera |
| Browser-use | agent do eksploracyjnych działań w przeglądarce | **Alternatywa**, nie automatyczny oracle poprawności |
| Robot Framework | orkiestracja acceptance/RPA i ekosystem bibliotek | **Alternatywa** dla organizacji posiadających już Robot |
| BackstopJS | porównanie screenshotów do referencji | **Alternatywa**; nie dublowano własnych baseline |
| Schemathesis | generowanie testów z kontraktu OpenAPI/GraphQL | **Opcjonalny proces shell**, odrębny zakres API |
| PaddleOCR | OCR i parsery dokumentów/obrazów | **Kierunek**, brak OCR w tej paczce |

## Co reużyć dalej

Dla portalów zacznij od jawnych scenariuszy TestQL i macierzy Playwright, a agentowi
Browser-use powierz generowanie propozycji eksploracji, nie zatwierdzanie wyników.
Dla natywnego desktopu bez DOM użyj obrazu/wzorca i asercji zmiany stanu; dla telefonów
potrzebny jest rzeczywisty driver/device lub emulator Appium/Airtest.
Dla całej platformy/API dołącz testy kontraktowe jako osobny zakres — nie przedstawiaj
ich jako obserwacji uzyskanej wyłącznie ze screenshotu.
Te sugestie architektoniczne są oceną zastosowania, nie zmierzoną przewagą narzędzi.

## OmniParser i licencje modeli

Nie należy powtarzać starego twierdzenia, że wszystkie modele OmniParser mają tę samą
licencję. Aktualny README podaje dodanie w lipcu2026 YOLOv9-E `icon_detect_v3` opartego
na implementacji MIT; wcześniejsze detektory Ultralytics zachowują AGPL, modele caption
są oznaczone MIT. Repozytorium pokazuje CC-BY4.0. README w momencie odczytu wskazuje
wagi nowego detektora w HF PR37 — to ruchomy stan, nie zamrożone wydanie.
Sprawdź konkretny komponent/checkpoint/revision przed pobraniem i dystrybucją.
Nie kopiowano kodu OmniParser ani wag do projektu. Ultralytics oferuje AGPL/warunki
komercyjne; MIT własnego kodu Testwins nie zastępuje tych warunków.

## Źródła pierwotne

- TestQL: https://github.com/autogrammar/testql ; https://pypi.org/project/testql/
- Publiczny kontrakt: https://github.com/autogrammar/testql/blob/main/testql/verification.py
- Playwright: https://playwright.dev/python/docs/api/class-browsertype
- LiteLLM: https://docs.litellm.ai/docs/completion/vision
- YOLO: https://docs.ultralytics.com/modes/predict ; https://www.ultralytics.com/license
- OmniParser: https://github.com/microsoft/OmniParser
- PyAutoGUI: https://pyautogui.readthedocs.io/en/latest/
- MSS: https://python-mss.readthedocs.io/
- Pexpect: https://pexpect.readthedocs.io/en/stable/
- OpenCV: https://docs.opencv.org/4.x/d4/dc6/tutorial_py_template_matching.html
- Appium: https://appium.io/docs/en/latest/intro/
- Airtest: https://github.com/AirtestProject/Airtest
- Browser-use: https://github.com/browser-use/browser-use
- Robot: https://github.com/robotframework/robotframework
- Backstop: https://github.com/garris/BackstopJS
- Schemathesis: https://github.com/schemathesis/schemathesis
- PaddleOCR: https://github.com/PaddlePaddle/PaddleOCR
- noVNC: https://github.com/novnc/noVNC
- axe-core: https://github.com/dequelabs/axe-core
