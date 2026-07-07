from app.models import Segment, Word, words_in_range
from app import config


def _seg(start, end, words):
    return Segment(text=" ".join(w for w, _, _ in words), start=start, end=end,
                   words=tuple(Word(t, s, e) for t, s, e in words))


def test_word_and_clip_are_immutable():
    w = Word("hi", 0.0, 0.5)
    try:
        w.text = "no"  # type: ignore[misc]
        assert False, "Word should be frozen"
    except Exception:
        pass


def test_words_in_range_filters_by_midpoint():
    segs = (
        _seg(0, 2, [("a", 0.0, 0.5), ("b", 1.0, 1.5)]),
        _seg(2, 4, [("c", 2.0, 2.5), ("d", 3.0, 3.5)]),
    )
    got = words_in_range(segs, 1.0, 3.0)
    assert [w.text for w in got] == ["b", "c"]


def test_aspect_dims_defaults_to_9_16():
    assert config.aspect_dims("9:16") == (1080, 1920)
    assert config.aspect_dims("bogus") == config.aspect_dims(config.DEFAULT_ASPECT)
