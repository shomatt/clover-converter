"""Generate a Clover Chord Systems 2 `.clvz` file (gzip XML, data-struct-version
1.5) from the intermediate Score model. Inverse of reader.py.

v1 scope: chords, key/time/clef, barlines, slash/rest/pitch rhythm, triplets,
line layout. Deferred: rehearsal-mark base64 plist text (symbols emitted empty),
beam computation, multi-page pagination tuning."""
from __future__ import annotations
import gzip
import math
from pathlib import Path
from xml.etree import ElementTree as ET

from clover2xml.model import Score
from clover2xml.plist_text import make_text_plist
from clover2xml.mappings.reverse import (
    kind_to_step2, degrees_to_step3, step2_step3_from_raw,
    fifths_to_key, time_to_type, clef_to_type, barline_to_clover,
)

TICKS_PER_WHOLE = 960
_X_BASE = 1.1          # chord x at timing 0
_X_PER_TICK = 0.0208   # chord x grows ~linearly with timing (verified from real files)


def _sub(parent, tag, text=None, **attrib):
    el = ET.SubElement(parent, tag, {k: str(v) for k, v in attrib.items()})
    if text is not None:
        el.text = str(text)
    return el


def _ticks(frac) -> int:
    return int(round(float(frac) * TICKS_PER_WHOLE))


def _emit_text_block(parent, text, font_size=20):
    """Emit Clover's dual text representation: the NSKeyedArchiver base64 plist
    AND a plain <formatted-texts> fallback, mirroring real files."""
    _sub(parent, "base64-formatted-texts", make_text_plist(text, float(font_size)),
         **{"platform-type": "MAC"})
    fts = _sub(parent, "formatted-texts")
    ft = _sub(fts, "formatted-text", **{
        "font-family": "LucidaGrande", "font-size": font_size,
        "font-style": "Normal", "font-weight": "Normal",
        "color": "#FF000000", "underline": "0", "line-through": "0"})
    _sub(ft, "arbitrary-text", text)


# model Symbol.type -> Clover text-symbol type ("reharsal" is Clover's own spelling)
_SYMBOL_TYPE = {"rehearsal": "reharsal", "free-text": "free-text",
                "navigation": "free-text", "dynamic": "free-text"}


def _chord_value_attrs(c):
    """step1/step2/step3/base for a ChordSym. Prefer the original raw step2/step3
    (lossless round-trip) when present; otherwise derive from kind/degrees."""
    step1 = c.root or "none"
    raw = step2_step3_from_raw(c.raw)
    if raw is not None:
        step2, step3 = raw
    else:
        step2 = kind_to_step2(c.kind)
        step3 = degrees_to_step3(c.degrees)
    base = c.bass or "none"
    return step1, step2, step3, base


def _emit_chords(part1, measure):
    chords = _sub(part1, "chords")
    for c in measure.chords:
        timing = int(round(c.offset))
        x = _X_BASE + timing * _X_PER_TICK
        ch = _sub(chords, "chord", type="chord", scale="1",
                  x=round(x, 4), y="-0.5", width="3.3", height="2.8", timing=timing)
        s1, s2, s3, base = _chord_value_attrs(c)
        _sub(ch, "chord-value", step1=s1, step2=s2, step3=s3, base=base)


def _emit_harmonies(part1, measure):
    harms = _sub(part1, "harmonies")
    timing = 0
    for ev in measure.events:
        dur = _ticks(ev.duration)
        tag = "triplet-harmony" if ev.tuplet else "harmony"
        attrib = dict(beam="none", stem_height="2.54237", timing=timing,
                      duration=dur, stem_direction="up")
        h = ET.SubElement(harms, tag)
        h.set("beam", "none")
        h.set("stem-height", "2.54237")
        h.set("timing", str(timing))
        h.set("duration", str(dur))
        h.set("stem-direction", "up")
        if ev.tuplet:
            h.set("tuplet", ev.tuplet)
            h.set("number", "0")
        notes = _sub(h, "notes")
        if ev.kind == "slash":
            _sub(notes, "slash", stemless="false")
        elif ev.kind == "pitch":
            _sub(notes, "pitch", level=ev.level if ev.level is not None else 0,
                 head="normal")
        else:
            _sub(notes, "rest")
        timing += dur


def _line_partitions(score, n_measures):
    """Number of measures per printed <line>, from system_starts (or 4-per-line)."""
    starts = sorted(score.system_starts) if score.system_starts else []
    if not starts:
        # default 4 per line
        out = []
        rem = n_measures
        while rem > 0:
            out.append(min(4, rem)); rem -= 4
        return out
    bounds = [0] + [s for s in starts if 0 < s < n_measures] + [n_measures]
    return [bounds[i + 1] - bounds[i] for i in range(len(bounds) - 1)]


def build_clover_xml(score) -> str:
    root = ET.Element("clover", {
        "data-struct-version": "1.5", "platform-type": "MAC",
        "platform-version": "12.0", "software-version": "2.1.0",
        "custom-font-id": "Default", "custom-font-name": "Default",
    })
    root.set("xml:space", "preserve")

    _sub(root, "history")

    measures = score.parts[0].measures if score.parts else []
    parts = _line_partitions(score, len(measures))

    # Clover requires enough page capacity for all printed lines: total a-page
    # (per-page line capacity) must be >= number of <line> elements, or the file
    # fails to open. Verified empirically: a-page is ~10-12; one page per ~8 lines
    # with capacity 12 is safely sufficient.
    pages = _sub(root, "pages")
    n_pages = max(1, math.ceil(len(parts) / 8))
    for _ in range(n_pages):
        _sub(pages, "page", **{"a-page": 12})

    lines = _sub(root, "lines")
    song = _sub(lines, "song", partition="1", parts="1", rows="1")
    if score.title:
        title = _sub(song, "title", type="song-property")
        _emit_text_block(title, score.title, font_size=28)
    for p in parts:
        _sub(lines, "line", partition=p, parts="1")

    msets = _sub(root, "measure-sets")
    for mm in measures:
        ms = _sub(msets, "measure-set")
        part1 = _sub(ms, "part1", width="0.25")
        _sub(part1, "barline-left", barline_to_clover(mm.barline_left))
        _sub(part1, "barline-right", barline_to_clover(mm.barline_right))
        if mm.clef and clef_to_type(mm.clef):
            _sub(part1, "clef", type=clef_to_type(mm.clef))
        if mm.key_fifths is not None:
            _sub(part1, "key", type=fifths_to_key(mm.key_fifths))
        if mm.time is not None:
            _sub(part1, "time", type=time_to_type(mm.time))
        syms = _sub(part1, "symbols")
        for sym in mm.symbols:
            if sym.type == "tempo":
                continue  # tempo handled separately; skip here
            ctype = _SYMBOL_TYPE.get(sym.type, "free-text")
            ts = _sub(syms, "text-symbol", type=ctype, x="-5.0", y="-2.5")
            _emit_text_block(ts, sym.text, font_size=14)
        _emit_chords(part1, mm)
        _emit_harmonies(part1, mm)

    ET.indent(root)
    body = ET.tostring(root, encoding="unicode")
    return f'<?xml version="1.0" encoding="utf-8"?>\n{body}\n'


def write_clover(score, out_path) -> None:
    xml = build_clover_xml(score)
    Path(out_path).parent.mkdir(parents=True, exist_ok=True)
    with gzip.open(out_path, "wb") as f:
        f.write(xml.encode("utf-8"))
