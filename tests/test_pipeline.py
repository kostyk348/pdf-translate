"""Tests for pdf-translate pipeline (pure functions, no DeepLX)."""

import importlib.util, json, math, os, sys, tempfile, hashlib, time

_home = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_spec = importlib.util.spec_from_file_location("pdf_translate",
    os.path.join(_home, "pdf-translate.py"))
pt = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(pt)


class TestAngle:
    def test_horizontal(self):
        assert pt.dir_to_angle((1.0, 0.0)) == 0.0

    def test_vertical_up(self):
        a = pt.dir_to_angle((0.0, -1.0))
        assert abs(a - 90.0) < 1e-9

    def test_vertical_down(self):
        a = pt.dir_to_angle((0.0, 1.0))
        assert abs(a - (-90.0)) < 1e-9

    def test_diagonal(self):
        a = pt.dir_to_angle((1.0, -1.0))
        assert abs(a - 45.0) < 1e-9

    def test_zero_vector(self):
        assert pt.dir_to_angle((0, 0)) == 0.0


class TestSpan:
    def test_span_properties(self):
        s = pt.Span("Hello", "Arial", 12, 0, 3, (0, 0, 10, 10), (1.0, 0.0))
        assert s.text == "Hello"
        assert s.is_bold
        assert s.is_italic
        assert s.angle == 0.0

    def test_font_category_sans(self):
        s = pt.Span("a", "Arial", 12, 0, 0, (0, 0, 1, 1), (1, 0))
        assert s.font_category() == "sans"

    def test_font_category_mono(self):
        s = pt.Span("a", "CourierNew", 12, 0, 0, (0, 0, 1, 1), (1, 0))
        assert s.font_category() == "mono"

    def test_font_category_serif(self):
        s = pt.Span("a", "TimesNewRoman", 12, 0, 0, (0, 0, 1, 1), (1, 0))
        assert s.font_category() == "serif"

    def test_font_category_bold(self):
        s = pt.Span("a", "Arial", 12, 0, 2, (0, 0, 1, 1), (1, 0))
        assert s.font_category() == "sans-bold"

    def test_font_category_bolditalic(self):
        s = pt.Span("a", "Arial", 12, 0, 3, (0, 0, 1, 1), (1, 0))
        assert s.font_category() == "sans-bolditalic"

    def test_font_category_italic(self):
        s = pt.Span("a", "Arial", 12, 0, 1, (0, 0, 1, 1), (1, 0))
        assert s.font_category() == "sans-italic"

    def test_angle_90(self):
        s = pt.Span("a", "Arial", 12, 0, 0, (0, 0, 1, 1), (0.0, -1.0))
        assert abs(s.angle - 90.0) < 1e-9


class TestTextBlock:
    def test_text_concatenation(self):
        s1 = pt.Span("Hello", "Arial", 12, 0, 0, (0, 0, 5, 10), (1, 0))
        s2 = pt.Span(" World", "Arial", 12, 0, 0, (5, 0, 15, 10), (1, 0))
        tb = pt.TextBlock((0, 0, 15, 10), [s1, s2], 0, 0)
        assert tb.text == "Hello World"

    def test_dominant_font_category(self):
        s1 = pt.Span("a", "Arial", 12, 0, 2, (0, 0, 1, 1), (1, 0))
        s2 = pt.Span("b", "Arial", 12, 0, 2, (1, 0, 2, 1), (1, 0))
        s3 = pt.Span("c", "Times", 12, 0, 0, (2, 0, 3, 1), (1, 0))
        tb = pt.TextBlock((0, 0, 3, 1), [s1, s2, s3], 0, 0)
        assert tb.dominant_font_category() == "sans-bold"

    def test_dominant_font_size(self):
        s1 = pt.Span("a", "Arial", 10, 0, 0, (0, 0, 1, 1), (1, 0))
        s2 = pt.Span("b", "Arial", 14, 0, 0, (1, 0, 2, 1), (1, 0))
        tb = pt.TextBlock((0, 0, 2, 1), [s1, s2], 0, 0)
        assert tb.dominant_font_size() == 14.0

    def test_dominant_color(self):
        s1 = pt.Span("a", "Arial", 12, 0xFF0000, 0, (0, 0, 1, 1), (1, 0))
        s2 = pt.Span("b", "Arial", 12, 0xFF0000, 0, (1, 0, 2, 1), (1, 0))
        s3 = pt.Span("c", "Arial", 12, 0x000000, 0, (2, 0, 3, 1), (1, 0))
        tb = pt.TextBlock((0, 0, 3, 1), [s1, s2, s3], 0, 0)
        assert tb.dominant_color() == 0xFF0000

    def test_rotated(self):
        tb = pt.TextBlock((0, 0, 10, 10), [], 0, 0, angle=90.0)
        assert tb.is_rotated

    def test_not_rotated(self):
        tb = pt.TextBlock((0, 0, 10, 10), [], 0, 0, angle=0.0)
        assert not tb.is_rotated


class TestTextLine:
    def test_properties(self):
        tl = pt.TextLine(0, 0, 0, (0, 0, 10, 10), "Hello", "Arial", 12, 0, 2, (1.0, 0.0))
        assert tl.is_bold
        assert not tl.is_italic
        assert tl.font_category() == "sans-bold"
        assert tl.key == (0, 0, 0)
        assert not tl.is_rotated

    def test_rotated_line(self):
        tl = pt.TextLine(0, 0, 0, (0, 0, 10, 10), "Hi", "Arial", 12, 0, 0, (0.0, -1.0))
        assert tl.is_rotated


class TestCJK:
    def test_cjk_chinese(self):
        assert pt._has_cjk("这是一个测试")

    def test_cjk_mixed(self):
        assert pt._has_cjk("Hello 世界")

    def test_no_cjk_latin(self):
        assert not pt._has_cjk("Hello world")

    def test_no_cjk_cyrillic(self):
        assert not pt._has_cjk("Привет мир")

    def test_no_cjk_empty(self):
        assert not pt._has_cjk("")

    def test_cjk_single_char(self):
        assert pt._has_cjk("中")


class TestTextExtent:
    def test_empty(self):
        assert pt._text_extent("", 12.0) == 0.0

    def test_simple(self):
        r = pt._text_extent("Hello", 12.0)
        assert abs(r - 5 * 12 * 0.55) < 1e-9

    def test_cyrillic(self):
        r = pt._text_extent("Привет", 10.0)
        assert abs(r - 6 * 10 * 0.55) < 1e-9


class TestScaleToFit:
    def test_fits_already(self):
        r = pt._scale_to_fit("Hi", 12.0, 100.0)
        assert r >= 12.0

    def test_needs_scaling(self):
        r = pt._scale_to_fit("Hello World! This is a long text", 12.0, 50.0)
        assert r < 12.0
        assert r >= pt.MIN_FONT_SIZE

    def test_no_overflow_empty_text(self):
        r = pt._scale_to_fit("", 12.0, 50.0)
        assert r >= 12.0

    def test_no_overflow_zero_extent(self):
        r = pt._scale_to_fit("Hello", 12.0, 0)
        assert r >= 12.0

    def test_min_font_size_respected(self):
        r = pt._scale_to_fit("Very long text that needs extreme shrinking", 12.0, 5.0)
        assert r >= pt.MIN_FONT_SIZE


class TestAuditLog:
    def test_append_and_verify(self):
        log = pt.AuditLog()
        log.append({"stage": "test", "msg": "hello"})
        log.append({"stage": "test", "msg": "world"})
        assert len(log.entries) == 2
        assert pt.AuditLog.verify(log.entries)

    def test_verify_fails_on_tamper(self):
        log = pt.AuditLog()
        log.append({"stage": "test", "msg": "hello"})
        log.append({"stage": "test", "msg": "world"})
        entries = log.entries
        tampered = list(entries)
        tampered[0]["msg"] = "tampered"
        assert not pt.AuditLog.verify(tampered)
        assert "hash" in tampered[0]

    def test_verify_fails_on_bad_prev_hash(self):
        log = pt.AuditLog()
        log.append({"stage": "test", "msg": "a"})
        log.append({"stage": "test", "msg": "b"})
        entries = log.entries
        bad = list(entries)
        bad[1]["prev_hash"] = "x" * 64
        assert not pt.AuditLog.verify(bad)

    def test_empty_log(self):
        assert pt.AuditLog.verify([])

    def test_single_entry(self):
        log = pt.AuditLog()
        log.append({"stage": "test", "msg": "only"})
        assert pt.AuditLog.verify(log.entries)

    def test_dump_and_load(self):
        log = pt.AuditLog()
        log.append({"stage": "t1", "x": 1})
        log.append({"stage": "t2", "x": 2})
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            path = f.name
            log.dump(path)
        with open(path, encoding="utf-8") as f:
            loaded = json.load(f)
        assert pt.AuditLog.verify(loaded)
        os.unlink(path)


class TestFontAlias:
    def test_helv(self):
        assert pt.FONT_ALIAS["helv"] == "sans"

    def test_times_new_roman(self):
        assert pt.FONT_ALIAS["TimesNewRoman"] == "serif"

    def test_courier_new(self):
        assert pt.FONT_ALIAS["CourierNew"] == "mono"

    def test_noto_sans(self):
        assert pt.FONT_ALIAS["Noto Sans"] == "sans"

    def test_liberation_serif(self):
        assert pt.FONT_ALIAS["LiberationSerif"] == "serif"


class TestFindCellExtent:
    def test_no_cell(self):
        r = pt._find_cell_extent((0, 0, 10, 10), 0, [], [])
        assert r is None


class TestLangMapping:
    def test_russian(self):
        assert pt._LANG_DEEPLX.get("ru") == "RU"

    def test_chinese(self):
        assert pt._LANG_DEEPLX.get("zh") == "ZH"

    def test_english(self):
        assert pt._LANG_DEEPLX.get("en") == "EN"

    def test_unknown_fallback(self):
        assert pt._LANG_DEEPLX.get("unknown") is None
