# pdf-translate

**Layout‑preserving PDF translation** — translates technical PDFs (Chinese→Russian, English→Russian, etc.) while keeping every line at its exact position, including rotated text, tables, and dimensions.

## Features

- **Line‑level translation** — each line keeps its original position, rotation, font, and size.
- **Rotated text support** — handles any rotation angle (90°, 180°, 270°, -90°).
- **DeepLX backend** — free, high‑quality translation via reverse‑engineered DeepL API (no API key needed).
- **Auto‑language detection** — automatically detects CJK characters and switches source language.
- **No white rectangles** — redacts original text without covering underlying drawings.
- **Overflow handling** — text that would overflow the page is repositioned to stay visible.
- **Hash‑chain audit trail** — every translation step is cryptographically chained for verifiability.
- **Image OCR** — optional OCR for text embedded in images (`--ocr`).
- **Self‑contained** — auto‑creates its own Python virtual environment on first run.

## Requirements

- Linux (tested on Debian/Ubuntu)
- Python 3.10+
- Liberation fonts (`fonts-liberation` package)

## Install

```bash
# Clone
git clone https://github.com/kostyk348/pdf-translate.git
cd pdf-translate

# Ensure Liberation fonts (for Cyrillic rendering)
sudo apt install fonts-liberation

# Run — virtual environment and dependencies auto‑install on first launch
./pdf-translate.py input.pdf output.pdf -f zh -t ru
```

## Usage

```bash
# Chinese → Russian (auto‑detects CJK)
./pdf-translate.py drawing.pdf drawing-ru.pdf -f zh -t ru

# English → Russian
./pdf-translate.py doc.pdf doc-ru.pdf -f en -t ru

# With verification
./pdf-translate.py doc.pdf doc-de.pdf -f en -t de --verify

# With image OCR
./pdf-translate.py doc.pdf doc-ru.pdf --ocr

# Specific page range
./pdf-translate.py doc.pdf doc-ru.pdf -f zh -t ru --page 1-5

# Disable auto‑language detection
./pdf-translate.py doc.pdf doc-ru.pdf -f zh -t ru --no-auto-lang
```

The **DeepLX** server starts automatically on first translation.

## Output

- **Translated PDF** — preserves original layout, all text replaced in‑place.
- **Audit log** — `<input>.audit.json` with hash‑chain of every translation step.

## How it works

```
input.pdf → SENSE (parse, extract lines) → LOGIC (DeepLX translate) → CAUSALITY (redact + insert) → output.pdf
                                                                                                      ↘
                                                                                            audit.json (hash‑chain)
```

## Supported language pairs

Any pair supported by DeepL:
- Chinese → Russian, English, German, French, Japanese, etc.
- English → Russian, German, French, Spanish, etc.
- 30+ languages total.

See [DeepL language support](https://www.deepl.com/docs-api/translate-text) for the full list.

## Architecture

- `pdf-translate.py` — single‑file pipeline (SENSE → FACT → LOGIC → CAUSALITY → VERIFIER)
- `.venv/bin/deeplx` — DeepLX reverse‑engineered DeepL API server
- Python libraries: PyMuPDF (PDF processing), Pillow (image OCR), DeepLX (translation via HTTP)

## License

MIT
