from app.models import Word
from app.pipeline import captions


def _words():
    return tuple(
        Word(t, i * 0.5, i * 0.5 + 0.5)
        for i, t in enumerate(["this", "is", "a", "test", "of", "the", "captions"])
    )


def test_strip_emoji_removes_pictographs():
    assert captions.strip_emoji("hello 😀🔥 world 🎬") == "hello  world"
    assert captions.strip_emoji("plain text") == "plain text"


def test_build_ass_has_header_and_events():
    ass = captions.build_ass(_words(), clip_start=0.0, width=1080, height=1920)
    assert "[Script Info]" in ass
    assert "PlayResX: 1080" in ass
    assert "Dialogue:" in ass


def test_captions_are_uppercased_and_grouped():
    ass = captions.build_ass(_words(), clip_start=0.0, width=1080, height=1920)
    dialogues = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")]
    assert dialogues, "expected at least one caption line"
    # 7 words / 3 per line -> 3 lines
    assert len(dialogues) == 3
    assert "THIS IS A" in dialogues[0]


def test_times_are_relative_to_clip_start():
    ass = captions.build_ass(_words(), clip_start=10.0, width=1080, height=1920)
    first = [ln for ln in ass.splitlines() if ln.startswith("Dialogue:")][0]
    # first word started at 0.0 absolute; with clip_start=10 it must clamp to 0:00.00
    assert "0:00:00.00" in first


def test_lines_from_words_returns_structured_lines():
    lines = captions.lines_from_words(_words(), clip_start=0.0)
    assert len(lines) == 3
    assert lines[0].text == "THIS IS A"
    assert lines[0].start >= 0 and lines[0].end > lines[0].start


def test_validate_lines_cleans_and_repairs():
    raw = [
        {"text": "  hello 😀 ", "start": 1.0, "end": 2.0},
        {"text": "🔥", "start": 0.0, "end": 1.0},        # emoji-only -> dropped
        {"text": "bad times", "start": 5.0, "end": 3.0},   # inverted -> repaired
        {"text": "", "start": 0.0, "end": 1.0},            # empty -> dropped
    ]
    lines = captions.validate_lines(raw)
    assert [ln.text for ln in lines] == ["hello", "bad times"]
    repaired = next(ln for ln in lines if ln.text == "bad times")
    assert repaired.end > repaired.start


def test_lines_json_round_trip():
    lines = captions.lines_from_words(_words(), clip_start=0.0)
    restored = captions.lines_from_json(captions.lines_to_json(lines))
    assert [ln.text for ln in restored] == [ln.text for ln in lines]


def test_ass_from_lines_matches_build_ass():
    words = _words()
    direct = captions.build_ass(words, 0.0, 1080, 1920)
    via_lines = captions.ass_from_lines(captions.lines_from_words(words, 0.0), 1080, 1920)
    assert direct == via_lines


def test_preset_resolves_and_falls_back():
    yellow = captions.caption_style_from_preset("bold_yellow")
    assert yellow.primary == "&H0000FFFF" and yellow.font == "Impact"
    fallback = captions.caption_style_from_preset("does-not-exist")
    assert fallback.font == captions.caption_style_from_preset(None).font


def test_position_sets_ass_alignment():
    lines = captions.lines_from_words(_words(), 0.0)
    top = captions.ass_from_lines(lines, 1080, 1920, captions.CaptionStyle(position="top"))
    middle = captions.ass_from_lines(lines, 1080, 1920, captions.CaptionStyle(position="middle"))
    bottom = captions.ass_from_lines(lines, 1080, 1920, captions.CaptionStyle(position="bottom"))
    assert ",-1,8," in top      # numpad 8 = top-center
    assert ",-1,5," in middle   # 5 = middle-center
    assert ",-1,2," in bottom   # 2 = bottom-center


def test_animation_prefix_applied_per_line():
    lines = captions.lines_from_words(_words(), 0.0)
    pop = captions.ass_from_lines(lines, 1080, 1920, captions.CaptionStyle(animation="pop"))
    fade = captions.ass_from_lines(lines, 1080, 1920, captions.CaptionStyle(animation="fade"))
    none = captions.ass_from_lines(lines, 1080, 1920, captions.CaptionStyle(animation="none"))
    assert "\\fscx70" in pop
    assert "\\fad(" in fade
    dialogues = [ln for ln in none.splitlines() if ln.startswith("Dialogue:")]
    assert dialogues and "{\\" not in dialogues[0]
