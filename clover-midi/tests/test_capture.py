import gzip
from defusedxml.ElementTree import fromstring
from clover_midi.capture import ChordCapturer, progression_to_score
from clover2xml.clover_writer import write_clover


def _play(cap, notes):
    """Press all notes then release them all → one captured chord."""
    for n in notes:
        cap.note_on(n)
    last = None
    for n in notes:
        last = cap.note_off(n)
    return last


def test_capture_sequence():
    cap = ChordCapturer()
    _play(cap, [60, 64, 67, 71])   # Cmaj7
    _play(cap, [62, 65, 69, 72])   # Dm7
    _play(cap, [55, 59, 62, 65])   # G7
    assert cap.chords == [
        ("C", "maj7", "none", "none"),
        ("D", "m7", "none", "none"),
        ("G", "7", "none", "none"),
    ]


def test_single_notes_ignored():
    cap = ChordCapturer(min_notes=3)
    _play(cap, [60])        # single note, ignored
    _play(cap, [60, 64])    # 2 notes, ignored (< min 3)
    assert cap.chords == []


def test_progression_to_clvz(tmp_path):
    cap = ChordCapturer()
    _play(cap, [60, 64, 67, 71])   # Cmaj7
    _play(cap, [55, 59, 62, 65])   # G7
    score = progression_to_score(cap.chords, title="Test")
    out = tmp_path / "p.clvz"
    write_clover(score, out)
    r = fromstring(gzip.open(out, "rb").read())
    cvs = r.findall(".//chord-value")
    assert cvs[0].get("step1") == "C" and cvs[0].get("step2") == "maj7"
    assert cvs[1].get("step1") == "G" and cvs[1].get("step2") == "7"
    assert r.find(".//song/title//arbitrary-text").text == "Test"


def test_feed_midi():
    from clover_midi.capture import feed_midi
    cap = ChordCapturer()
    for n in [60, 64, 67, 71]:
        feed_midi(cap, [0x90, n, 100])     # note-on
    det = None
    for n in [60, 64, 67, 71]:
        det = feed_midi(cap, [0x80, n, 0]) # note-off
    assert det == ("C", "maj7", "none", "none")
