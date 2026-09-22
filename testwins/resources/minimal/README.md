# Testwins — minimal profile

Edit `audit.yaml`: use your running application's origin and real expected selector/text.
The default expects a visible `h1`; replace that contract rather than deleting it merely to obtain green.
Install Chromium with `python -m playwright install chromium`, then:

```bash
testwins run --config audit.yaml --output artifacts
```

Chromium, three viewport profiles, isolated contexts. External origins are denied unless explicitly allowed.
Axe/CV/LLM are disabled: a passed report means only the declared scope was completed.
`shell.oql` is an independent TestQL example; it requires the optional TestQL backend.
