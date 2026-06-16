"""Unified converter: any-to-any among Clover (.clvz), MusicXML (.musicxml/.xml)
and MIDI (.mid/.midi). Loads the source into the intermediate Score model and
writes it to the requested target format."""
from __future__ import annotations
from pathlib import Path

from clover2xml.model import Score
from clover2xml.reader import parse_score
from clover2xml.writer import build_musicxml
from clover2xml.mxl_reader import parse_musicxml
from clover2xml.clover_writer import write_clover
from clover2xml.midi_io import midi_to_score, score_to_midi

CLVZ = (".clvz",)
MXL = (".musicxml", ".xml")
MIDI = (".mid", ".midi")
INPUT_EXTS = CLVZ + MXL + MIDI
OUTPUT_EXTS = CLVZ + (".musicxml",) + (".mid",)


def _ext(p) -> str:
    return Path(p).suffix.lower()


def load_score(src) -> Score:
    """Read any supported input into a Score."""
    e = _ext(src)
    if e in CLVZ:
        return parse_score(src)
    if e in MXL:
        return parse_musicxml(src)
    if e in MIDI:
        return midi_to_score(src)
    raise ValueError(f"未対応の入力拡張子: {Path(src).suffix}")


def save_score(score: Score, dst) -> None:
    """Write a Score to any supported output."""
    e = _ext(dst)
    if e in CLVZ:
        write_clover(score, dst)
    elif e in (".musicxml", ".xml"):
        Path(dst).write_text(build_musicxml(score), encoding="utf-8")
    elif e in MIDI:
        score_to_midi(score, dst)
    else:
        raise ValueError(f"未対応の出力拡張子: {Path(dst).suffix}")


def convert_file(src, dst) -> None:
    """Convert src → dst, inferring direction from both extensions."""
    save_score(load_score(src), dst)
