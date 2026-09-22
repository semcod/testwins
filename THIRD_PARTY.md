# Third-party notices and boundaries

Testwins' own source is Apache-2.0 (LICENSE). Optional packages and containers retain their
own licenses. A dependency declaration does not sublicense dependencies or weights.
No external model weights or font files are distributed in this source archive.

Used through dependency/runtime interfaces: TestQL, Playwright, LiteLLM, OpenCV,
Pillow, NumPy, PyYAML, jsonschema, Pexpect, PyAutoGUI, MSS; optional Ultralytics YOLO;
Planfile SDK in publisher; noVNC/websockify/Xvfb/Fluxbox/x11vnc in Docker; axe-core
installed by npm during image build. Browser brand distribution terms also apply.

Ultralytics has AGPL/enterprise licensing: https://www.ultralytics.com/license
Review your intended use and chosen weights. OmniParser is a researched integration
target via converted generic region JSON, not bundled code or a bundled model.
Its July2026 README distinguishes new MIT-based detector code, earlier AGPL-based
weights, MIT caption models and the repository's CC-BY4.0 notice. Audit exact revisions.

Original input UXMatrix Lab0.1.0 was supplied by the user and developed into Testwins.
No code or checkpoint from tests-twin-ux/OmniParser/Appium/Airtest/Browser-use was copied.
See docs/OSS_REUSE.md for links and the distinction between implemented adapters and
possible future reuse. Repository default branches and package releases are mutable.
