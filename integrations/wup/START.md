# WUP — start z pełnej paczki Testwins 0.4.0

To dodatek, nie pełny checkout WUP. Z katalogu rozpakowanego ZIP:

```bash
cd testwins
# Użyj środowiska Python, w którym jest też WUP:
python -m pip install './dist/testwins-0.4.0-py3-none-any.whl[live]'
python integrations/wup/install.py /repo/wup
python integrations/wup/install.py /repo/wup --apply
python -m pip install -e /repo/wup
python -m playwright install chromium
wup gui watch /repo/app --config testwins.watch.yaml
```

Manifest własnej aplikacji utwórz na podstawie `configs/live/` lub profilu Clonerd.
Nie stosuj jednocześnie patcha i instalatora. Zdalne repozytorium nie jest modyfikowane.
Testy lokalne objęły kontrolowany punkt rejestracji i instalator, nie cały upstream WUP.
