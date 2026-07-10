<div align="center">

# 📄 pdf-translate

**Translate technical PDFs. Keep every line exactly where it belongs.**

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![DeepLX](https://img.shields.io/badge/translation-DeepLX-0a66c2)](https://github.com/OwO-Network/DeepLX)
[![PyMuPDF](https://img.shields.io/badge/PDF-PyMuPDF-orange)](https://github.com/pymupdf/PyMuPDF)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg)](http://makeapullrequest.com)
[![CI](https://github.com/kostyk348/pdf-translate/actions/workflows/ci.yml/badge.svg)](https://github.com/kostyk348/pdf-translate/actions/workflows/ci.yml)

<p align="center">
  <i>Chinese → Russian · English → Russian · 30+ language pairs · No API key · No broken layout</i>
</p>

```
                  ╔══════════════════════════╗
                  ║      pdf-translate       ║
                  ║  Layout-Preserving PDF   ║
                  ║      Translation         ║
                  ╚══════════════════════════╝
                          │
     ┌────────────────────┼────────────────────┐
     │                    │                    │
  ┌──▼──┐           ┌────▼────┐          ┌────▼───┐
  │SENSE│ ────────> │  LOGIC  │ ───────> │CAUSALI-│
  │parse│  extract  │ DeepLX  │  redact+ │  TY    │
  │ PDF │   lines   │translate│  insert  │output  │
  └─────┘           └─────────┘          └────────┘
                          │                    │
                          │                    ▼
                          │            ┌────────────┐
                          └────────────│audit.json  │
                                       │hash‑chain  │
                                       └────────────┘
```

</div>

---

## ✨ Features

| Capability | Description |
|---|---|
| **Layout‑perfect** | Every line keeps its original position, rotation, font and size. No wrapping, no clipping. |
| **Rotated text** | Handles 0°, 90°, 180°, 270°, -90° — even mixed on the same page. |
| **No API key** | Uses [DeepLX](https://github.com/OwO-Network/DeepLX) — a free, reverse‑engineered DeepL endpoint. |
| **Auto CJK** | Detects Chinese/Japanese/Korean characters and switches source language automatically. |
| **No white rectangles** | Redacts original text with `fill=None` — underlying drawings stay visible. |
| **Overflow guard** | Long translations are repositioned to stay within page boundaries. |
| **Audit trail** | Every step is cryptographically chained in a hash‑based audit log. |
| **Image OCR** | Optional OCR for text inside embedded images (`--ocr`). |
| **Self‑booting** | Creates its own venv on first run — zero manual setup. |

---

## 🎬 Demo

Translating MSP430-UIF JTAG emulator documentation (Chinese → Russian):

<p align="center">
  <img src="demo-files/msp430uif-demo.gif" alt="pdf-translate demo — MSP430-UIF manual zh→ru" width="600">
</p>

---

## 🚀 Quick start

```bash
# Requirements
sudo apt install fonts-liberation python3 python3-venv

# Grab it
git clone https://github.com/kostyk348/pdf-translate.git
cd pdf-translate

# Translate a Chinese technical drawing to Russian
./pdf-translate.py input.pdf output-ru.pdf -f zh -t ru
```

On first run it automatically:
1. Creates a Python virtual environment
2. Installs PyMuPDF + Pillow
3. Downloads the DeepLX binary
4. Starts the DeepLX translation server

**No `pip install`, no `npm install`, no Docker, no API signup.**

---

## 📖 Usage

```bash
# Chinese → Russian (auto-detects CJK, `-f` optional)
./pdf-translate.py drawing.pdf ru.pdf -f zh -t ru

# English → Russian
./pdf-translate.py manual.pdf manual-ru.pdf -f en -t ru

# Verify integrity with hash‑chain audit
./pdf-translate.py doc.pdf doc-de.pdf -f en -t de --verify

# Specific page range
./pdf-translate.py doc.pdf out.pdf -f zh -t ru --page 3-7

# With image OCR
./pdf-translate.py scan.pdf scan-ru.pdf --ocr

# Disable auto‑language detection
./pdf-translate.py doc.pdf out.pdf -f zh -t ru --no-auto-lang
```

### Arguments

| Arg | Default | Description |
|---|---|---|
| `-f, --from` | `en` | Source language (ZH, EN, RU, DE, FR, etc.) |
| `-t, --to` | `ru` | Target language |
| `--page` | all | Page range, e.g. `1-5` or `1,3,5` |
| `--ocr` | off | OCR text in embedded images |
| `--verify` | off | Verify hash‑chain audit log after translation |
| `--no-auto-lang` | off | Skip automatic CJK detection |

---

```
[pipeline] en → ru  |  FR0108-1 电热管.pdf
[sense] Parsing PDF...  1 pages, 46 lines, 39 rotated
[logic] Translating 46 lines (zh→ru)...
[causality] Rebuilding PDF layout...
[output] FR0108-1 电热管 (ru).pdf  (320 KB)
[pipeline] Done.
```

> **Result**: a drop‑in replacement — open it in any PDF viewer and every label, dimension, and note is in Russian at the exact same position as the original.

---

## 🔧 How it works

```
 ┌─────────┐   ┌──────────────┐   ┌──────────────────┐   ┌──────────┐
 │  SENSE  │──>│     FACT     │──>│      LOGIC       │──>│CAUSALITY │
 │ parse   │   │ extract      │   │ DeepLX translate │   │ redact   │
 │ structure│   │ lines+spans  │   │ per-line, retry  │   │ +insert  │
 └─────────┘   └──────────────┘   └──────────────────┘   └─────┬────┘
                                                                │
                                                           ┌────▼────┐
                                                           │VERIFIER │
                                                           │ audit   │
                                                           │ chain   │
                                                           └─────────┘
```

**SENSE** — Reads the PDF with PyMuPDF, extracts text blocks, lines, and spans with full positioning metadata (bbox, rotation, font, size).  
**FACT** — Filters, deduplicates, and sorts lines into a canonical ordered list.  
**LOGIC** — Sends each line to the DeepLX server for translation. Retries on failure.  
**CAUSALITY** — Redacts original Chinese text (no white rectangles), inserts translated text at the exact same baseline position with matching rotation.  
**VERIFIER** — Computes a hash chain over the entire translation log and verifies integrity.

---

## 🌐 Supported languages

Any combination supported by DeepL. Common pairs:

| Source | Target |
|---|---|
| Chinese (ZH) | Russian, English, German, French, Japanese, Korean |
| English (EN) | Russian, German, French, Spanish, Italian, Portuguese |
| Japanese (JA) | English, Chinese, Korean |
| Russian (RU) | English, German, French |

Full list: [DeepL docs](https://www.deepl.com/docs-api/translate-text)

---

## 📦 Project structure

```
pdf-translate/
├── pdf-translate.py   # single‑file pipeline (SENSE → ... → VERIFIER)
├── .venv/
│   └── bin/
│       └── deeplx     # DeepLX translation server (auto‑downloaded)
├── demo-files/
│   ├── pdf-translate-demo.gif
│   └── msp430uif-demo.gif
├── README.md
├── LICENSE
└── requirements.txt
```

---

## 💬 Why pdf-translate?

Existing tools either:
- Use paid APIs (Google Cloud, AWS Translate)
- Ruin the layout (wrapping, missing rotated text, white rectangles over drawings)
- Require complex Docker setup
- Have no audit trail

**pdf-translate** solves all of these in a single self‑contained Python script.

---

## 🤝 Contributing

PRs are very welcome! Ideas:

- Multiprocessing for large documents
- GUI / web frontend
- More translation backends (LibreTranslate, local LLM)
- Windows / macOS support for auto‑bootstrap

Check [open issues](https://github.com/kostyk348/pdf-translate/issues) for planned work.

---

## ⭐ Support

If this saved you time, **star the repo**! It helps others find it.

[![GitHub stars](https://img.shields.io/github/stars/kostyk348/pdf-translate?style=social)](https://github.com/kostyk348/pdf-translate)

---

## 📄 License

MIT — do whatever you want, just don't blame us.
