#!/usr/bin/env python3
"""pdf-translate_win_deeplx.py — Windows PDF translation with DeepLX + Google fallback.

Pipeline: auto-venv (Windows) -> SENSE -> LOGIC (DeepLX -> Google) -> CAUSALITY -> PDF.
Handles: normal text, rotated text, vector drawings (EasyOCR), tables, overflow.
DeepLX auto-detected in PATH or %%USERPROFILE%%\\go\\bin\\DeepLX.exe.

Usage:
  .venv\\Scripts\\python pdf-translate_win_deeplx.py input.pdf output.pdf -f zh -t ru
  .venv\\Scripts\\python pdf-translate_win_deeplx.py input.pdf output.pdf --deeplx-path D:\\tools\\deeplx.exe
"""

import argparse, hashlib, io, json, math, os, subprocess, sys, textwrap, time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

# =============================================================================
# 0. AUTO VENV BOOTSTRAP
# =============================================================================
VENV_DIR = Path(__file__).parent / ".venv_win_deeplx"
REQUIREMENTS = ["pymupdf", "Pillow", "deep-translator", "easyocr"]

def _bootstrap():
    py = VENV_DIR / "Scripts" / "python.exe"
    if py.exists():
        return
    print("[setup] Creating virtual environment...", file=sys.stderr)
    subprocess.check_call([sys.executable, "-m", "venv", str(VENV_DIR)])
    pip = VENV_DIR / "Scripts" / "pip.exe"
    print("[setup] Installing dependencies...", file=sys.stderr)
    subprocess.check_call([str(pip), "install"] + REQUIREMENTS)
    print("[setup] Done.", file=sys.stderr)

def _in_venv():
    return sys.executable.startswith(str(VENV_DIR))

if __name__ == "__main__" and not _in_venv():
    _bootstrap()
    py = VENV_DIR / "Scripts" / "python.exe"
    subprocess.call([str(py)] + sys.argv)
    sys.exit(0)

# =============================================================================
# 1. IMPORTS (inside venv)
# =============================================================================
import fitz
try:
    from PIL import Image
except ImportError:
    Image = None
try:
    from deep_translator import GoogleTranslator
except ImportError:
    GoogleTranslator = None
try:
    import easyocr
except ImportError:
    easyocr = None

# =============================================================================
# 2. CONFIG
# =============================================================================
MIN_FONT_SIZE = 5.0

DEEPLX_URL = "http://127.0.0.1:1188/translate"

# Typical DeepLX binary locations on Windows
DEEPLX_SEARCH_PATHS = [
    "deeplx.exe",
    "DeepLX.exe",
    os.path.join(os.environ.get("USERPROFILE", ""), "go", "bin", "DeepLX.exe"),
    os.path.join(os.environ.get("USERPROFILE", ""), "go", "bin", "deeplx.exe"),
    os.path.join(os.environ.get("LOCALAPPDATA", ""), "go", "bin", "DeepLX.exe"),
    "C:\\tools\\deeplx.exe",
    "C:\\Program Files\\deeplx\\deeplx.exe",
]

FONT_PATHS = {
    "sans": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arial.ttf"),
    "sans-bold": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbd.ttf"),
    "sans-italic": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "ariali.ttf"),
    "sans-bolditalic": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "arialbi.ttf"),
    "serif": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "times.ttf"),
    "serif-bold": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "timesbd.ttf"),
    "serif-italic": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "timesi.ttf"),
    "serif-bolditalic": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "timesbi.ttf"),
    "mono": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "cour.ttf"),
    "mono-bold": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "courbd.ttf"),
    "mono-italic": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "couri.ttf"),
    "mono-bolditalic": os.path.join(os.environ.get("WINDIR", "C:\\Windows"), "Fonts", "courbi.ttf"),
}

FONT_ALIAS = {
    "helv": "sans", "Helvetica": "sans", "Arial": "sans", "ArialMT": "sans",
    "Arial-BoldMT": "sans-bold", "Arial-ItalicMT": "sans-italic",
    "Arial-BoldItalicMT": "sans-bolditalic",
    "Times": "serif", "Times-Roman": "serif", "TimesNewRoman": "serif",
    "TimesNewRomanPSMT": "serif", "TimesNewRomanPS-BoldMT": "serif-bold",
    "TimesNewRomanPS-ItalicMT": "serif-italic",
    "Courier": "mono", "CourierNew": "mono",
    "CourierNewPSMT": "mono", "CourierNewPS-BoldMT": "mono-bold",
    "CourierNewPS-ItalicMT": "mono-italic",
    "LiberationSans": "sans", "LiberationSerif": "serif", "LiberationMono": "mono",
    "DroidSans": "sans", "DroidSerif": "serif", "DroidSansMono": "mono",
    "Roboto": "sans", "Roboto-Regular": "sans",
    "Roboto-Bold": "sans-bold", "Roboto-Italic": "sans-italic",
    "Noto Sans": "sans", "Noto Serif": "serif",
    "DejaVu Sans": "sans", "DejaVu Serif": "serif", "DejaVu Sans Mono": "mono",
}

# ---------------------------------------------------------------------------
# Azimuth -> angle helpers
# ---------------------------------------------------------------------------
def dir_to_angle(dir_vec: tuple) -> float:
    dx, dy = dir_vec
    if abs(dx) < 0.01 and abs(dy) < 0.01:
        return 0.0
    return math.degrees(math.atan2(-dy, dx))

# =============================================================================
# 3. DATA MODELS
# =============================================================================
@dataclass
class Span:
    text: str
    font: str
    size: float
    color: int
    flags: int
    bbox: tuple[float, float, float, float]
    dir: tuple[float, float]

    @property
    def is_bold(self): return self.flags & 2 != 0
    @property
    def is_italic(self): return self.flags & 1 != 0
    @property
    def angle(self): return dir_to_angle(self.dir)

    def font_category(self) -> str:
        f = self.font.lower()
        if any(x in f for x in ("mono", "courier", "consolas", "liberationmono")):
            base = "mono"
        elif any(x in f for x in ("serif", "times", "roman", "liberationserif")):
            base = "serif"
        else:
            base = "sans"
        if self.is_bold and self.is_italic: return f"{base}-bolditalic"
        if self.is_bold: return f"{base}-bold"
        if self.is_italic: return f"{base}-italic"
        return base

@dataclass
class TextBlock:
    bbox: tuple[float, float, float, float]
    spans: list[Span]
    block_type: int
    number: int
    page_num: int = 0
    block_idx: int = 0
    angle: float = 0.0

    @property
    def text(self): return "".join(s.text for s in self.spans)

    @property
    def is_rotated(self) -> bool:
        return abs(self.angle) > 1.0

    def dominant_font_category(self) -> str:
        if not self.spans:
            return "sans"
        return max((s.font_category() for s in self.spans),
                   key=lambda c: sum(1 for s2 in self.spans if s2.font_category() == c))

    def dominant_font_size(self) -> float:
        if not self.spans:
            return 11.0
        return max(s.size for s in self.spans)

    def dominant_color(self) -> int:
        if not self.spans:
            return 0
        return max((s.color for s in self.spans),
                   key=lambda c: sum(1 for s2 in self.spans if s2.color == c))

@dataclass
class ImageBlock:
    bbox: tuple[float, float, float, float]
    xref: int
    page_num: int
    block_idx: int

@dataclass
class TextLine:
    page_num: int
    block_idx: int
    line_idx: int
    bbox: tuple[float, float, float, float]
    text: str
    font: str
    size: float
    color: int
    flags: int
    dir: tuple[float, float]

    @property
    def is_bold(self): return self.flags & 2 != 0
    @property
    def is_italic(self): return self.flags & 1 != 0
    @property
    def angle(self): return dir_to_angle(self.dir)
    @property
    def is_rotated(self) -> bool:
        return abs(self.angle) > 1.0
    @property
    def key(self): return (self.page_num, self.block_idx, self.line_idx)

    def font_category(self) -> str:
        f = self.font.lower()
        if any(x in f for x in ("mono", "courier", "consolas", "liberationmono")):
            base = "mono"
        elif any(x in f for x in ("serif", "times", "roman", "liberationserif")):
            base = "serif"
        else:
            base = "sans"
        if self.is_bold and self.is_italic: return f"{base}-bolditalic"
        if self.is_bold: return f"{base}-bold"
        if self.is_italic: return f"{base}-italic"
        return base

@dataclass
class PageModel:
    num: int
    width: float
    height: float
    text_blocks: list[TextBlock]
    text_lines: list[TextLine]
    image_blocks: list[ImageBlock]

# =============================================================================
# 4. AUDIT TRAIL (hash-chain)
# =============================================================================
class AuditLog:
    def __init__(self):
        self.entries = []
        self.prev_hash = "0" * 64

    def append(self, entry: dict):
        entry["prev_hash"] = self.prev_hash
        entry["ts"] = time.time()
        body = json.dumps(entry, sort_keys=True, ensure_ascii=False).encode()
        entry["hash"] = hashlib.sha256(body).hexdigest()
        self.prev_hash = entry["hash"]
        self.entries.append(entry)

    def dump(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.entries, f, ensure_ascii=False, indent=2)

    @staticmethod
    def verify(entries: list[dict]) -> bool:
        prev = "0" * 64
        for e in entries:
            h = e.pop("hash", "")
            ph = e.get("prev_hash")
            if ph != prev:
                e["hash"] = h
                return False
            body = json.dumps(e, sort_keys=True, ensure_ascii=False).encode()
            if hashlib.sha256(body).hexdigest() != h:
                e["hash"] = h
                return False
            prev = h
            e["hash"] = h
        return True

# =============================================================================
# 5. SENSE - PDF Parser
# =============================================================================
def parse_pdf(path: str) -> tuple:
    doc = fitz.open(path)
    pages = []
    for pnum in range(len(doc)):
        page = doc[pnum]
        rect = page.rect
        raw = page.get_text("dict",
            flags=fitz.TEXT_PRESERVE_LIGATURES | fitz.TEXT_PRESERVE_WHITESPACE)

        text_blocks = []
        text_lines = []
        image_blocks = []

        for b in raw.get("blocks", []):
            btype = b.get("type", -1)
            bbox = tuple(b.get("bbox", (0, 0, 0, 0)))

            if btype == 1:
                image_blocks.append(ImageBlock(
                    bbox=bbox, xref=b.get("number", 0),
                    page_num=pnum, block_idx=b.get("number", 0),
                ))
                continue

            if btype != 0:
                continue

            spans = []
            block_lines = []
            block_angle = 0.0
            first_dir = (1.0, 0.0)
            for line in b.get("lines", []):
                dir_vec = line.get("dir", (1.0, 0.0))
                if first_dir == (1.0, 0.0):
                    first_dir = dir_vec
                line_text = ""
                line_spans = []
                for s in line.get("spans", []):
                    text = s.get("text", "")
                    if not text.strip():
                        continue
                    span = Span(
                        text=text, font=s.get("font", "Helvetica"),
                        size=s.get("size", 11.0), color=s.get("color", 0),
                        flags=s.get("flags", 0),
                        bbox=tuple(s.get("bbox", (0, 0, 0, 0))),
                        dir=dir_vec,
                    )
                    spans.append(span)
                    line_spans.append(span)
                    line_text += text
                    if abs(dir_to_angle(dir_vec)) > abs(block_angle):
                        block_angle = dir_to_angle(dir_vec)

                if line_text.strip() and line_spans:
                    line_bbox = tuple(line.get("bbox", (0, 0, 0, 0)))
                    ref_span = line_spans[0]
                    block_lines.append(TextLine(
                        page_num=pnum, block_idx=len(text_blocks),
                        line_idx=len(block_lines), bbox=line_bbox,
                        text=line_text, font=ref_span.font,
                        size=ref_span.size, color=ref_span.color,
                        flags=ref_span.flags, dir=dir_vec,
                    ))

            if not spans:
                continue

            text_lines.extend(block_lines)

            tb = TextBlock(
                bbox=bbox, spans=spans, block_type=0,
                number=b.get("number", 0), page_num=pnum,
                block_idx=len(text_blocks), angle=block_angle,
            )
            text_blocks.append(tb)

        pages.append(PageModel(
            num=pnum, width=rect.width, height=rect.height,
            text_blocks=text_blocks, text_lines=text_lines,
            image_blocks=image_blocks,
        ))
    return doc, pages

# =============================================================================
# 6. FACT
# =============================================================================
def collect_lines(pages: list[PageModel]) -> list[TextLine]:
    lines = []
    for pg in pages:
        for tl in pg.text_lines:
            lines.append(tl)
    return lines

# =============================================================================
# 7. LOGIC - Translation (DeepLX primary, Google fallback)
# =============================================================================

def _has_cjk(text: str) -> bool:
    for ch in text:
        cp = ord(ch)
        if 0x4E00 <= cp <= 0x9FFF or 0x3400 <= cp <= 0x4DBF:
            return True
    return False

_LANG_DEEPLX = {
    "bg": "BG", "cs": "CS", "da": "DA", "de": "DE", "el": "EL",
    "en": "EN", "es": "ES", "et": "ET", "fi": "FI", "fr": "FR",
    "hu": "HU", "id": "ID", "it": "IT", "ja": "JA", "ko": "KO",
    "lt": "LT", "lv": "LV", "nb": "NB", "nl": "NL", "pl": "PL",
    "pt": "PT", "ro": "RO", "ru": "RU", "sk": "SK", "sl": "SL",
    "sv": "SV", "tr": "TR", "uk": "UK", "zh": "ZH",
}

_LANG_GOOGLE = {
    "bg": "bg", "cs": "cs", "da": "da", "de": "de", "el": "el",
    "en": "en", "es": "es", "et": "et", "fi": "fi", "fr": "fr",
    "hu": "hu", "id": "id", "it": "it", "ja": "ja", "ko": "ko",
    "lt": "lt", "lv": "lv", "nb": "nb", "nl": "nl", "pl": "pl",
    "pt": "pt", "ro": "ro", "ru": "ru", "sk": "sk", "sl": "sl",
    "sv": "sv", "tr": "tr", "uk": "uk", "zh": "zh-CN",
}

# ---- DeepLX server management ----
_deeplx_proc: Optional[subprocess.Popen] = None
_deeplx_available = False

def _find_deeplx_bin(custom_path: str = "") -> Optional[str]:
    if custom_path:
        if os.path.exists(custom_path):
            return custom_path
        print(f"  [warn] DeepLX path not found: {custom_path}", file=sys.stderr)
        return None
    for candidate in DEEPLX_SEARCH_PATHS:
        if os.path.exists(candidate):
            return candidate
    # Also check PATH
    for p in os.environ.get("PATH", "").split(os.pathsep):
        for exe in ("deeplx.exe", "DeepLX.exe", "deeplx", "DeepLX"):
            full = os.path.join(p.strip(), exe)
            if os.path.exists(full):
                return full
    return None

def _start_deeplx(custom_path: str = ""):
    global _deeplx_proc, _deeplx_available
    import socket
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.settimeout(1)
        s.connect(("127.0.0.1", 1188))
        s.close()
        _deeplx_available = True
        return
    except Exception:
        pass

    deeplx_bin = _find_deeplx_bin(custom_path)
    if deeplx_bin:
        print(f"[logic] Starting DeepLX server ({deeplx_bin})...", file=sys.stderr)
        try:
            _deeplx_proc = subprocess.Popen(
                [deeplx_bin], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            time.sleep(2)
            _deeplx_available = True
        except Exception as e:
            print(f"  [warn] Failed to start DeepLX: {e}", file=sys.stderr)
            _deeplx_available = False
    else:
        print("  [warn] DeepLX binary not found. Will use Google Translate.",
              file=sys.stderr)
        _deeplx_available = False

# ---- Translation functions ----

def deeplx_translate(text: str, from_code: str, to_code: str) -> Optional[str]:
    if not _deeplx_available:
        return None
    src = _LANG_DEEPLX.get(from_code.lower())
    dst = _LANG_DEEPLX.get(to_code.lower())
    if not src or not dst or src == dst:
        return text
    body = json.dumps({"text": text, "source_lang": src, "target_lang": dst})
    try:
        import urllib.request
        req = urllib.request.Request(
            DEEPLX_URL, data=body.encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(req, timeout=30) as resp:
            result = json.loads(resp.read())
        if result.get("code") == 200:
            return result["data"]
        else:
            print(f"  [warn] DeepLX error: code {result.get('code')}",
                  file=sys.stderr)
    except Exception as e:
        print(f"  [warn] DeepLX request failed: {e}", file=sys.stderr)
    return None

def google_translate(text: str, from_code: str, to_code: str) -> str:
    src = _LANG_GOOGLE.get(from_code.lower())
    dst = _LANG_GOOGLE.get(to_code.lower())
    if not src or not dst or src == dst:
        return text
    if GoogleTranslator is None:
        return text
    try:
        result = GoogleTranslator(source=src, target=dst).translate(text)
        if result:
            return result
    except Exception as e:
        print(f"  [warn] Google Translate error: {e}", file=sys.stderr)
    return text

def translate_text(text: str, from_code: str, to_code: str) -> str:
    """Primary: DeepLX. Fallback: Google Translate. Final fallback: original."""
    if _deeplx_available:
        result = deeplx_translate(text, from_code, to_code)
        if result is not None:
            return result
    result = google_translate(text, from_code, to_code)
    return result

# =============================================================================
# 8a. CAUSALITY - Font resolver
# =============================================================================
def _resolve_font(page: fitz.Page, cat: str) -> str:
    for c in (cat, "sans", "sans-bold", "sans-italic"):
        fpath = FONT_PATHS.get(c)
        if fpath and os.path.exists(fpath):
            fname = f"F{abs(hash(fpath)) % 10**8:08x}"
            try:
                page.insert_font(fontname=fname, fontfile=fpath)
                return fname
            except Exception:
                continue
    return "helv"

# =============================================================================
# 8b. CAUSALITY - Text placement
# =============================================================================
_page_grid_cache = {}

def _detect_page_grid(page: fitz.Page) -> tuple:
    pno = id(page)
    if pno in _page_grid_cache:
        return _page_grid_cache[pno]
    drawings = page.get_drawings()
    h_lines = []
    v_lines = []
    for d in drawings:
        for item in d.get('items', []):
            if item[0] != 'l':
                continue
            x1, y1 = item[1]
            x2, y2 = item[2]
            dx, dy = abs(x2 - x1), abs(y2 - y1)
            if dy < 2 and dx > 30:
                h_lines.append((min(x1, x2), max(x1, x2), (y1 + y2) / 2))
            elif dx < 2 and dy > 30:
                v_lines.append((min(y1, y2), max(y1, y2), (x1 + x2) / 2))
    h_lines.sort(key=lambda x: x[2])
    v_lines.sort(key=lambda x: x[2])
    _page_grid_cache[pno] = (h_lines, v_lines)
    return h_lines, v_lines

def _find_cell_extent(bbox: tuple, rotate: int,
                      h_lines: list, v_lines: list) -> float | None:
    cx = (bbox[0] + bbox[2]) / 2
    cy = (bbox[1] + bbox[3]) / 2
    top = bottom = left = right = None
    for x1, x2, y in h_lines:
        if x1 <= cx <= x2:
            if y < cy and (top is None or y > top):
                top = y
            if y > cy and (bottom is None or y < bottom):
                bottom = y
    for y1, y2, x in v_lines:
        if y1 <= cy <= y2:
            if x < cx and (left is None or x > left):
                left = x
            if x > cx and (right is None or x < right):
                right = x
    if all(v is not None for v in (top, bottom, left, right)):
        return (right - left) if rotate in (0, 180) else (bottom - top)
    return None

def _text_extent(text: str, fontsize: float) -> float:
    return len(text) * fontsize * 0.55

def _scale_to_fit(text: str, fontsize: float, max_extent: float) -> float:
    if max_extent <= 0 or not text:
        return fontsize
    text_len = _text_extent(text, fontsize)
    if text_len <= max_extent:
        return max(fontsize, MIN_FONT_SIZE)
    ratio = max_extent / text_len
    scaled = fontsize * ratio
    return max(scaled, MIN_FONT_SIZE)

def _place_text(page: fitz.Page, bbox: tuple, text: str,
                fontname: str, fontsize: float, color: int,
                meas_cat: str = "sans", rotate: int = 0) -> tuple:
    box_w = bbox[2] - bbox[0]
    box_h = bbox[3] - bbox[1]
    if box_w <= 0 or box_h <= 0:
        return bbox, False, True

    h_lines, v_lines = _detect_page_grid(page)
    cell_extent = _find_cell_extent(bbox, rotate, h_lines, v_lines)

    if rotate in (0, 180):
        max_extent = cell_extent if cell_extent is not None else box_w
    else:
        max_extent = cell_extent if cell_extent is not None else box_h

    actual_size = _scale_to_fit(text, fontsize, max_extent)
    scaled = actual_size < fontsize * 0.95

    page_h = page.mediabox.height
    page_w = page.mediabox.width
    text_len = _text_extent(text, actual_size)

    if rotate == 0:
        pt = fitz.Point(bbox[0], bbox[3] - actual_size * 0.15)
        if pt.x + text_len > page_w:
            pt = fitz.Point(max(0, page_w - text_len - 5), pt.y)
    elif rotate == 90:
        pt = fitz.Point(bbox[0], bbox[3])
        if pt.y - text_len < 0:
            pt = fitz.Point(pt.x, min(page_h, text_len + 5))
    elif rotate == 180:
        pt = fitz.Point(bbox[2], bbox[3])
        if pt.x - text_len < 0:
            pt = fitz.Point(min(page_w, text_len + 5), pt.y)
    elif rotate == 270:
        pt = fitz.Point(bbox[0], bbox[1])
        if pt.y + text_len > page_h:
            pt = fitz.Point(pt.x, max(0, page_h - text_len - 5))
    else:
        pt = fitz.Point(bbox[0], bbox[3])

    page.insert_text(pt, text, fontname=fontname, fontsize=actual_size,
                     color=color, rotate=rotate)
    return bbox, scaled, False

# =============================================================================
# 8e. Full-page OCR for vector drawings (EasyOCR)
# =============================================================================
_ocr_reader_cache = {}

def _get_ocr_reader(langs: list) -> "easyocr.Reader":
    key = tuple(langs)
    if key not in _ocr_reader_cache:
        if easyocr is None:
            return None
        _ocr_reader_cache[key] = easyocr.Reader(langs, gpu=False)
    return _ocr_reader_cache[key]

def _ocr_full_page(page: fitz.Page, dpi: int = 300) -> list:
    if easyocr is None:
        return []
    rect = page.rect
    pix = page.get_pixmap(dpi=dpi)
    img_data = pix.tobytes("png")
    pil_img = Image.open(io.BytesIO(img_data))

    reader = _get_ocr_reader(["ch_sim", "en"])
    if reader is None:
        return []
    import numpy as np
    raw = reader.readtext(np.array(pil_img), detail=1)

    scale_x = rect.width / pix.width
    scale_y = rect.height / pix.height

    results = []
    for bbox, text, conf in raw:
        text = text.strip()
        if not text or conf < 0.1:
            continue
        x0 = min(p[0] for p in bbox) * scale_x
        y0 = min(p[1] for p in bbox) * scale_y
        x1 = max(p[0] for p in bbox) * scale_x
        y1 = max(p[1] for p in bbox) * scale_y
        results.append({
            "bbox": (x0, y0, x1, y1),
            "text": text,
            "conf": conf,
        })
    return results

def _overlay_ocr_regions(page: fitz.Page, ocr_results: list,
                          translations: dict, audit: AuditLog,
                          from_code: str, to_code: str) -> None:
    redact_rects = []
    overlay_data = []
    for idx, reg in enumerate(ocr_results):
        txt = reg["text"]
        bbox = reg["bbox"]
        if not _has_cjk(txt):
            continue

        translated = translations.get(("ocr", page.number, idx))
        if translated is None:
            continue
        if not translated.strip():
            continue

        box_w = bbox[2] - bbox[0]
        box_h = bbox[3] - bbox[1]
        if box_w <= 2 or box_h <= 2:
            continue

        fsize = max(5.0, min(box_h * 0.8, box_w / max(len(translated), 1) * 1.8))

        redact_rects.append(fitz.Rect(bbox))
        overlay_data.append((bbox, translated, fsize, txt, idx))

    for r in redact_rects:
        page.add_redact_annot(r, fill=(1, 1, 1))
    if redact_rects:
        page.apply_redactions()

    fname = _resolve_font(page, "sans")
    for bbox, translated, fsize, txt, idx in overlay_data:
        pt = fitz.Point(bbox[0], bbox[3] - fsize * 0.15)
        page.insert_text(pt, translated, fontname=fname, fontsize=fsize, color=0)

        audit.append({
            "stage": "fullpage_ocr",
            "page": page.number,
            "ocr_idx": idx,
            "bbox": list(bbox),
            "original": txt[:100],
            "translated": translated[:100],
            "font_size": fsize,
        })

# =============================================================================
# 9. CAUSALITY - Main rebuild
# =============================================================================
def rebuild_pdf(doc: fitz.Document, pages: list[PageModel],
                translations: dict, audit: AuditLog,
                ocr: bool = False, from_code: str = "en", to_code: str = "ru") -> fitz.Document:
    for pg in pages:
        page = doc[pg.num]
        page_lines = [tl for tl in pg.text_lines if tl.page_num == pg.num]

        for tl in page_lines:
            page.add_redact_annot(tl.bbox, fill=None)

        if page_lines:
            page.apply_redactions()

        cat_cache = {}
        for tl in page_lines:
            key = tl.key
            ttext = (translations.get(key) or "").strip()
            if not ttext:
                ttext = tl.text.strip()
            if not ttext:
                continue

            cat = tl.font_category()
            fsize = tl.size
            color = tl.color
            base_cat = FONT_ALIAS.get(cat, cat)

            if base_cat not in cat_cache:
                cat_cache[base_cat] = _resolve_font(page, base_cat)
            fname = cat_cache[base_cat]

            rotate_val = int(round(tl.angle / 90.0)) * 90 % 360 if tl.is_rotated else 0
            actual_bbox, scaled, overflow = _place_text(
                page, tl.bbox, ttext, fname, fsize, color,
                meas_cat=base_cat, rotate=rotate_val)

            audit.append({
                "stage": "causality",
                "page": pg.num,
                "block": tl.block_idx,
                "line": tl.line_idx,
                "angle": tl.angle,
                "original_snippet": tl.text[:100],
                "translated_snippet": ttext[:100],
                "original_bbox": list(tl.bbox),
                "actual_bbox": list(actual_bbox),
                "font_category": cat,
                "font_resolved": fname,
                "font_size_requested": fsize,
                "font_size_actual": fsize,
                "scaled": scaled,
                "overflow": overflow,
            })
    return doc

# =============================================================================
# 10. VERIFIER
# =============================================================================
def verify(doc_in: fitz.Document, doc_out: fitz.Document,
           translations: dict, pages: list[PageModel], audit: AuditLog) -> dict:
    total_lines = sum(len(p.text_lines) for p in pages)
    report = {
        "pages_in": len(doc_in),
        "pages_out": len(doc_out),
        "total_lines": total_lines,
        "translated_lines": len(translations),
        "empty_translations": 0,
        "warnings": [],
        "audit_valid": AuditLog.verify(audit.entries),
    }
    if report["pages_in"] != report["pages_out"]:
        report["warnings"].append("Page count mismatch")
    for k, t in translations.items():
        if not t.strip():
            report["empty_translations"] += 1
    return report

# =============================================================================
# 11. CLI
# =============================================================================
def main():
    ap = argparse.ArgumentParser(
        description="Windows PDF translation with DeepLX + Google Translate fallback",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=textwrap.dedent("""\
            Examples:
              .venv\\Scripts\\python pdf-translate_win_deeplx.py doc.pdf doc-ru.pdf -f zh -t ru
              .venv\\Scripts\\python pdf-translate_win_deeplx.py doc.pdf doc-ru.pdf --deeplx-path D:\\\\tools\\\\deeplx.exe
        """),
    )
    ap.add_argument("input", help="Input PDF")
    ap.add_argument("output", help="Output PDF")
    ap.add_argument("-f", "--from", dest="from_code", default="en", help="Source language (default: en)")
    ap.add_argument("-t", "--to", dest="to_code", default="ru", help="Target language (default: ru)")
    ap.add_argument("--page", help="Page range, e.g. 1-5,3,7-9")
    ap.add_argument("--audit", help="Audit log path (default: input.audit.json)")
    ap.add_argument("--verify", action="store_true", help="Run post-translation verification")
    ap.add_argument("--no-auto-lang", action="store_true",
                    help="Disable auto-detection of Chinese in text")
    ap.add_argument("--deeplx-path", default="",
                    help="Path to DeepLX executable (auto-detected if not set)")
    ap.add_argument("--deeplx-only", action="store_true",
                    help="Fail if DeepLX unavailable (no Google fallback)")

    args = ap.parse_args()

    if not os.path.exists(args.input):
        print(f"Error: input not found: {args.input}", file=sys.stderr)
        sys.exit(1)

    audit_path = args.audit or (Path(args.input).stem + ".audit.json")
    audit = AuditLog()

    print(f"[pipeline] {args.from_code} -> {args.to_code}  |  {args.input}", file=sys.stderr)

    # ---- SENSE ----
    print("[sense] Parsing PDF...", file=sys.stderr)
    doc, pages = parse_pdf(args.input)
    n_tblocks = sum(len(p.text_blocks) for p in pages)
    n_tlines = sum(len(p.text_lines) for p in pages)
    n_iblocks = sum(len(p.image_blocks) for p in pages)
    print(f"[sense] {len(pages)} pages, {n_tblocks} text blocks ({n_tlines} lines), {n_iblocks} images", file=sys.stderr)

    lines = collect_lines(pages)
    if args.page:
        sel = set()
        for part in args.page.split(","):
            if "-" in part:
                a, b = map(int, part.split("-"))
                sel.update(range(a - 1, b))
            else:
                sel.add(int(part) - 1)
        lines = [l for l in lines if l.page_num in sel]
        print(f"[sense] Filtered to {len(lines)} lines on pages {args.page}", file=sys.stderr)

    rotated = [l for l in lines if l.is_rotated]
    if rotated:
        print(f"[sense] {len(rotated)} rotated line(s) detected", file=sys.stderr)

    from_code = args.from_code
    if not args.no_auto_lang:
        has_cjk = any(_has_cjk(l.text) for l in lines)
        if has_cjk and from_code != "zh":
            print(f"[sense] CJK detected, auto-switching source to zh", file=sys.stderr)
            from_code = "zh"

    # ---- DeepLX startup ----
    _start_deeplx(args.deeplx_path)
    if args.deeplx_only and not _deeplx_available:
        print("[error] --deeplx-only set but DeepLX is unavailable", file=sys.stderr)
        sys.exit(1)

    # ---- LOGIC ----
    translations = {}
    print(f"[logic] Translating {len(lines)} lines ({from_code}->{args.to_code})...", file=sys.stderr)
    for idx, tl in enumerate(lines):
        txt = tl.text.strip()
        if not txt:
            translations[tl.key] = txt
            continue

        audit.append({
            "stage": "logic_input",
            "page": tl.page_num, "block": tl.block_idx,
            "line": tl.line_idx, "angle": tl.angle,
            "text": txt[:200],
        })

        try:
            translated = translate_text(txt, from_code, args.to_code)
        except Exception as e:
            print(f"  [warn] page {tl.page_num} block {tl.block_idx} line {tl.line_idx}: {e}",
                  file=sys.stderr)
            translated = txt

        translations[tl.key] = translated
        if (idx + 1) % 20 == 0:
            print(f"  {idx+1}/{len(lines)}", file=sys.stderr)

    # ---- FULL-PAGE OCR for vector drawings ----
    vector_pages = []
    for pg in pages:
        page = doc[pg.num]
        drawings = page.get_drawings()
        if len(drawings) > 50 and len(pg.text_lines) < 10:
            vector_pages.append(pg.num)
    if vector_pages:
        print(f"[sense] {len(vector_pages)} vector-drawing page(s), running full-page OCR...",
              file=sys.stderr)
    for pnum in vector_pages:
        print(f"  OCR page {pnum+1}...", file=sys.stderr)
        page = doc[pnum]
        ocr_results = _ocr_full_page(page)
        print(f"    {len(ocr_results)} text regions found", file=sys.stderr)
        cjk_regions = [r for r in ocr_results if _has_cjk(r["text"])]
        print(f"    {len(cjk_regions)} with CJK text", file=sys.stderr)

        ocr_translations = {}
        for idx, reg in enumerate(cjk_regions):
            key = ("ocr", pnum, idx)
            txt = reg["text"]
            audit.append({
                "stage": "fullpage_ocr_input",
                "page": pnum, "ocr_idx": idx,
                "bbox": list(reg["bbox"]), "text": txt[:200],
            })
            try:
                translated = translate_text(txt, from_code, args.to_code)
            except Exception as e:
                print(f"    [warn] OCR region {idx}: {e}", file=sys.stderr)
                translated = txt
            ocr_translations[key] = translated

        _overlay_ocr_regions(page, cjk_regions, ocr_translations, audit,
                            from_code, args.to_code)

    # ---- CAUSALITY ----
    print("[causality] Rebuilding PDF layout...", file=sys.stderr)
    rebuild_pdf(doc, pages, translations, audit,
                ocr=False, from_code=from_code, to_code=args.to_code)

    doc.save(args.output, garbage=4, deflate=True, clean=True)
    print(f"[output] {args.output}  ({os.path.getsize(args.output)/1024:.0f} KB)", file=sys.stderr)

    audit.dump(audit_path)
    print(f"[audit] {audit_path}", file=sys.stderr)

    if args.verify:
        dc = fitz.open(args.output)
        rep = verify(doc, dc, translations, pages, audit)
        dc.close()
        if rep["warnings"]:
            print(f"[verify] Warnings: {rep['warnings']}", file=sys.stderr)
        if rep["empty_translations"]:
            print(f"[verify] Empty translations: {rep['empty_translations']}", file=sys.stderr)
        print(f"[verify] Audit chain valid: {rep['audit_valid']}", file=sys.stderr)

    doc.close()
    print("[pipeline] Done.", file=sys.stderr)

if __name__ == "__main__":
    main()
