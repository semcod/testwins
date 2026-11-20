# Third-party notices and boundaries

Testwins' own source is Apache-2.0 (LICENSE). Optional packages and containers retain their
own licenses. A dependency declaration does not sublicense dependencies or weights.
No external model weights or font files are distributed in this source archive.

Used through dependency/runtime interfaces: TestQL, Playwright, LiteLLM, OpenCV,
Pillow, NumPy, PyYAML, jsonschema, Pexpect, PyAutoGUI, MSS; optional Ultralytics YOLO;
Planfile SDK in publisher; noVNC/websockify/Xvfb/Fluxbox/x11vnc in Docker. Browser brand distribution terms also apply.

Ultralytics has AGPL/enterprise licensing: https://www.ultralytics.com/license
Review your intended use and chosen weights. OmniParser is a researched integration
target via converted generic region JSON, not bundled code or a bundled model.
Its July2026 README distinguishes new MIT-based detector code, earlier AGPL-based
weights, MIT caption models and the repository's CC-BY4.0 notice. Audit exact revisions.

Original input UXMatrix Lab0.1.0 was supplied by the user and developed into Testwins.
No code or checkpoint from tests-twin-ux/OmniParser/Appium/Airtest/Browser-use was copied.
See docs/OSS_REUSE.md for links and the distinction between implemented adapters and
possible future reuse. Repository default branches and package releases are mutable.

## Bundled accessibility engine

Testwins ships the unmodified `axe.min.js` from axe-core 4.10.3 so browser
audits can run offline. Its SHA-256 is
`880970c081707360e64f34cea25ff91892f5bc95675b0776925b9709dd8a68bb`.
The npm release contains the readable `axe.js` alongside the minified build.
[Release archive](https://registry.npmjs.org/axe-core/-/axe-core-4.10.3.tgz) ·
[Upstream source](https://github.com/dequelabs/axe-core/tree/f49c1c49b5eafe1f8065e07c314f75968dd91333)

The engine is licensed under MPL-2.0 and incorporates MIT- and ISC-licensed
components. Both upstream notices are included in the Python distributions.
[MPL-2.0](testwins/resources/axe-core-notices/MPL-2.0.txt) ·
[Component notices](testwins/resources/axe-core-notices/LICENSE-3RD-PARTY.txt)
