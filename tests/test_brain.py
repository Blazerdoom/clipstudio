from app.models import Segment, Word
from app.pipeline import brain


def _seg(text, start, end):
    # one evenly-spaced Word per token so windows have words to score.
    tokens = text.split()
    step = (end - start) / max(1, len(tokens))
    words = tuple(
        Word(tok, round(start + i * step, 3), round(start + (i + 1) * step, 3))
        for i, tok in enumerate(tokens)
    )
    return Segment(text=text, start=start, end=end, words=words)


def _transcript():
    return (
        _seg("Why nobody talks about this incredible secret.", 0, 6),
        _seg("Here is the number one mistake people make every single day.", 6, 14),
        _seg("And that is honestly the reason it matters so much to you.", 14, 22),
        _seg("Some filler talking that is fairly plain and ordinary here.", 22, 30),
        _seg("This is the amazing final payoff you have been waiting for.", 30, 38),
    )


def test_scores_are_bounded():
    score, reason = brain.score_window("Why is this so amazing? Because numbers 5.", 30.0)
    assert 0.0 <= score <= 100.0
    assert isinstance(reason, str) and reason


def test_hook_opener_beats_plain_text():
    strong, _ = brain.score_window("Why nobody tells you this incredible secret.", 30.0)
    plain, _ = brain.score_window("the the the and and of to it was on a", 30.0)
    assert strong > plain


def test_select_clips_returns_non_overlapping_ranked():
    clips = brain.select_clips(_transcript(), max_clips=3)
    assert 1 <= len(clips) <= 3
    for c in clips:
        assert c.title and c.score >= 0 and c.duration >= 0
    # non-overlapping
    ordered = sorted(clips, key=lambda c: c.start)
    for a, b in zip(ordered, ordered[1:]):
        assert a.end <= b.start


def test_titles_and_tags_are_clean():
    clips = brain.select_clips(_transcript(), max_clips=2)
    c = clips[0]
    assert not c.title.startswith(" ")
    assert all(isinstance(t, str) for t in c.tags)


def test_make_hook_is_short():
    hook = brain.make_hook("Here is the number one mistake people make every single day and more.")
    assert 0 < len(hook.split()) <= 9
