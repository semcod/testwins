# LiteLLM i lokalna analiza obrazu

## Konfiguracja

`pip install '.[llm,cv]'`. Profile wybiera `LLM_PROVIDER`: openrouter, zai, zai-coding,
deepseek, ollama, custom. Główne `.env` jest czytane bez eval/shell/ekspansji zmiennych;
zmienne procesu mają pierwszeństwo. Wybierany jest tylko klucz aktywnego providera.
`LLM_VISION_MODEL` nadpisuje `<PROVIDER>_VISION_MODEL`. Pole `LLM_MODEL` jest przygotowane
dla zastosowań tekstowych; polecenia vision i draft w tej wersji używają **modelu wizyjnego**.

LiteLLM `completion` dostaje base64 PNG jako `image_url`, limit tokenów, timeout,
JSON response format, bez tools i bez retry. Obsługę obrazów sprawdza `supports_vision`.
`LLM_VISION_CAPABLE=1` to tylko świadome oświadczenie dla własnego, zweryfikowanego modelu;
nie dodaje modelowi zdolności wizyjnych. Nie każdy provider/model obsługuje JSON mode.
Nieobsługiwane parametry dają błąd, nie pozornie poprawny wynik.

W przypadku Ollama domyślnie `http://127.0.0.1:11434`, prefiks `ollama_chat`.
Model trzeba wcześniej samodzielnie pobrać; Testwins nie pobiera wag. Remote HTTPS
wymaga `LLM_ALLOW_REMOTE=1` i klucza. Limity: 1..20 calls, 100..8000 output tokens,
5..180 sekund/wywołanie. Trzy domyślne calls to nie pełne pokrycie raportu.
W `scope` są liczniki wybranych i dostępnych obrazów, a użycie tokenów jest zachowane,
gdy provider je zwróci. Nie ma obietnicy dokładnego budżetu USD.

## Analiza i zakres

`testwins vision RUN --output analysis/run-001` najpierw sprawdza hash-chain i pliki
raportu, wybiera stabilne snapshoty, najpierw po jednym na komórkę macierzy, potem
pozostałe do limitu. Obrazy z pojedynczej ścieżki można uzupełnić `--before` i `--goal`.
Kolejność: before, after; ramki odnoszą się do ostatniego obrazu w pikselach, nie CSS.
Wynik zawiera `model_verdict`, `authority:none`, `human_review_required:true`.
Nawet werdykt modelu `pass` nie zmienia statusu deterministycznego audytu.
Kod wyjścia 0 polecenia `vision` oznacza ukończenie analizy, a nie poprawność aplikacji.

CV: `testwins cv image.png --backend opencv --output regions.json` lub lokalne YOLO
z `--weights`, opcjonalnym `--weights-sha256` i obowiązkowym `--trust-model`.
YOLO używa kafelków1280px z zakładką160px, limitu40 kafelków, max300 detections/kafelek,
max1000 finalnych regionów i NMS per klasa. Nie stawia diagnozy błędu.
OpenCV kontury mają stałe score1 — to nie prawdopodobieństwo defektu ani elementu UI.
Własne detektory mogą zwracać `testwins.regions/v1`, po przeliczeniu do pikseli screenshotu.

YOLO .pt może wykonać kod podczas ładowania. Sama suma SHA potwierdza tylko tożsamość,
nie bezpieczeństwo ani jakość. Wag nie dostarczamy. Sprawdź licencję wybranego kodu
**i modelu**, zwłaszcza Ultralytics oraz różne generacje OmniParser.

## Draft, nie autopilot

`testwins draft` wymaga jawnego celu, obrazu i inwentarza DOM. Kompilator pozwala tylko
click/input/assert_visible/assert_text, dokładne selektory z inwentarza, co najmniej
jedną asercję. Zakazuje znaków kontroli i `$`; nigdy nie kompiluje SHELL, INCLUDE,
sekretów ani narzędzi z odpowiedzi modelu. Wyniki to draft.json + draft.oql, do przeglądu.
Scenariusz trzeba przenieść do własnego projektu i uruchomić osobnym poleceniem.

## Prywatność i błędy

Raport DOM maskuje wybrane inputy/data-private, ale maskowanie jest best-effort.
Canvas, obrazy, treści zwykłych akapitów i desktop mogą zawierać dane osobowe.
Desktop nie ma maskowania DOM. Zewnętrzny LLM otrzymuje obraz i wybrany inwentarz —
operator musi mieć zgodę/podstawę do ich transferu i sam sprawdzić materiał.
Treść aplikacji jest niezaufana; prompt injection może wpłynąć na opis, dlatego opis
ma zerowy autorytet wykonawczy. Odpowiedzi mają zamknięty schemat, ograniczenie liczby
wyników i weryfikację ramek/selektorów. Błędy LiteLLM zapisywane są jako typ, nie raw
nagłówki/prompty. Callbacks logujące LiteLLM są wyłączane w tym kliencie.
Nie jest to gwarancja zachowania samego operatora LLM ani jego retencji danych.

Źródła (2026-09-22):
- https://docs.litellm.ai/docs/completion/vision
- https://docs.litellm.ai/docs/providers/openrouter
- https://docs.litellm.ai/docs/providers/zai
- https://docs.litellm.ai/docs/providers/ollama
- https://docs.ultralytics.com/modes/predict
- https://github.com/microsoft/OmniParser
