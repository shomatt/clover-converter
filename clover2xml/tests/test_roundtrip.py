"""Public test suite — exercises both conversion directions using only a
SYNTHETIC sample (no real song data). This is the suite shipped with the
published source."""
from pathlib import Path

from clover2xml.reader import parse_score
from clover2xml.writer import build_musicxml
from clover2xml.mxl_reader import parse_musicxml
from clover2xml.clover_writer import write_clover
from clover2xml.engine import convert_file
from clover2xml.midi_io import score_to_midi, midi_to_score

FIX = Path(__file__).parent / "fixtures"


def test_clvz_to_musicxml():
    score = parse_score(FIX / "demo.clvz")
    assert len(score.parts[0].measures) == 8
    xml = build_musicxml(score)
    assert "<score-partwise" in xml
    assert "use-symbols" in xml          # chord symbols use △/− glyphs


def test_chord_vocabulary():
    score = parse_score(FIX / "demo.clvz")
    chords = [(c.root, c.kind) for m in score.parts[0].measures for c in m.chords]
    assert ("C", "major-seventh") in chords
    assert ("A", "minor-seventh") in chords
    assert ("G", "dominant") in chords


def test_full_roundtrip(tmp_path):
    # .clvz -> MusicXML -> .clvz, chords preserved
    score = parse_score(FIX / "demo.clvz")
    mxl = tmp_path / "demo.musicxml"
    mxl.write_text(build_musicxml(score), encoding="utf-8")
    s2 = parse_musicxml(mxl)
    out = tmp_path / "demo.clvz"
    write_clover(s2, out)
    s3 = parse_score(out)
    chords = [(c.root, c.kind) for m in s3.parts[0].measures for c in m.chords]
    assert ("C", "major-seventh") in chords
    assert ("G", "dominant") in chords


def test_midi_export_import_roundtrip():
    # .clvz -> MIDI -> Score, chords preserved
    score = parse_score(FIX / "demo.clvz")
    orig = [(c.root, c.kind) for m in score.parts[0].measures for c in m.chords]
    back = midi_to_score(score_to_midi(score))
    got = [(c.root, c.kind) for m in back.parts[0].measures for c in m.chords]
    assert got == orig


def test_engine_midi(tmp_path):
    mid = tmp_path / "demo.mid"
    convert_file(FIX / "demo.clvz", mid)        # export
    assert mid.read_bytes()[:4] == b"MThd"
    clvz = tmp_path / "x.clvz"
    convert_file(mid, clvz)                       # import
    chords = [(c.root, c.kind) for m in parse_score(clvz).parts[0].measures
              for c in m.chords]
    assert ("C", "major-seventh") in chords
