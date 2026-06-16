from __future__ import annotations
import gzip
from fractions import Fraction
from pathlib import Path
from defusedxml.ElementTree import fromstring   # XXE/billion-laughs 対策(外部由来ファイル)


def load_clover_xml(path) -> "Element":
    """`.clvz`(gzip) を解凍して <clover> ルート要素を返す。"""
    with gzip.open(path, "rb") as f:
        data = f.read()
    return fromstring(data)


TICKS_PER_WHOLE = 960   # 実データで確認済(960=全音符)。


def ticks_to_fraction(ticks: int) -> Fraction:
    """Clover 内部ティックを全音符=1 の Fraction に正規化。"""
    return Fraction(int(ticks), TICKS_PER_WHOLE)


from clover2xml.model import Score, Part, Measure, ChordSym, RhythmEvent, Symbol
from clover2xml.mappings.meta import time_to_tuple, key_to_fifths, clef_to_sign, barline_style
from clover2xml.mappings.chords import chord_value_to_sym
from clover2xml.text import extract_plain_text

def _text(el):
    t = el.text
    return (t or "").strip()

# Clover navigation/dynamic <symbol> types → (Symbol.type, display text).
# push8/push16 are Clover-specific キメ marks with no clean MusicXML equivalent → skipped.
_SYMBOL_TEXT = {"fine": ("navigation", "Fine"), "rit": ("navigation", "rit."),
                "crescendo": ("dynamic", "cresc."), "decrescendo": ("dynamic", "dim.")}

def _parse_measure(ms) -> Measure:
    part = ms.find("part1")
    m = Measure()
    bl = part.find("barline-left");  m.barline_left = barline_style(_text(bl)) if bl is not None else "regular"
    br = part.find("barline-right"); m.barline_right = barline_style(_text(br)) if br is not None else "regular"
    clef = part.find("clef")
    if clef is not None and clef.get("type"):
        m.clef = clef_to_sign(clef.get("type"))
    key = part.find("key")
    if key is not None and key.get("type"):
        m.key_fifths = key_to_fifths(key.get("type"))
    time = part.find("time")
    if time is not None and time.get("type"):
        m.time = time_to_tuple(time.get("type"))
    for ch in part.iter("chord"):
        cv = ch.find("chord-value")
        if cv is None:
            continue
        sym = chord_value_to_sym(cv.get("step1", "none"), cv.get("step2", "none"),
                                 cv.get("step3", "none"), cv.get("base", "none"))
        if sym is not None:
            sym.offset = float(ch.get("timing", "0") or 0)
            m.chords.append(sym)
    for h in part.iter():
        if h.tag not in ("harmony", "triplet-harmony"):
            continue
        notes = h.find("notes")
        kind = "rest"
        level = None
        if notes is not None:
            if notes.find("slash") is not None:
                kind = "slash"
            elif notes.find("pitch") is not None:
                kind = "pitch"
                lv = notes.find("pitch").get("level")
                level = int(lv) if lv is not None else 0
            # else stays "rest"
        dur = ticks_to_fraction(int(h.get("duration", "0") or 0))
        arts_el = h.find("articulations")
        arts = [a.get("type") for a in list(arts_el)] if arts_el is not None else []
        arts = [a for a in arts if a]
        ev = RhythmEvent(
            kind=kind, duration=dur, beam=h.get("beam", "none") or "none",
            tie=(h.find("tie") is not None),
            slur=("start" if h.find("slur") is not None else None),
            articulations=arts, level=level,
            tuplet=(h.get("tuplet") if h.tag == "triplet-harmony" else None),
        )
        m.events.append(ev)
    for ts in part.iter("text-symbol"):
        ft = ts.find("formatted-texts")
        txt = extract_plain_text(ft) if ft is not None else ""
        if txt:
            typ = {"reharsal": "rehearsal", "free-text": "free-text"}.get(ts.get("type"), "free-text")
            m.symbols.append(Symbol(type=typ, text=txt))
    speed = part.find(".//speed")
    if speed is not None and _text(speed):
        m.symbols.append(Symbol(type="tempo", text=_text(speed)))
    for vol in part.iter("volta"):
        t = vol.get("type")
        num_el = vol.find("arbitrary-text")
        num = (num_el.text.strip() if num_el is not None and num_el.text else "1")
        if t == "volta-begin":
            m.ending_start = num
        elif t == "volta-end":
            m.ending_stop = num
    for sym in part.iter("symbol"):
        info = _SYMBOL_TEXT.get(sym.get("type"))
        if info:
            m.symbols.append(Symbol(type=info[0], text=info[1]))
    return m

def parse_score(path) -> Score:
    root = load_clover_xml(path)
    title = ""
    song = root.find(".//song")
    if song is not None:
        ft = song.find(".//formatted-texts")
        if ft is not None:
            title = extract_plain_text(ft)
    tempo = None
    for sp in root.iter("speed"):
        if _text(sp).isdigit():
            tempo = int(_text(sp)); break
    measures = [_parse_measure(ms) for ms in root.iter("measure-set")]
    line_lengths = []
    lines_el = root.find("lines")
    if lines_el is not None:
        for ln in lines_el.findall("line"):
            p = ln.get("partition")
            if p and p.isdigit():
                line_lengths.append(int(p))
    system_starts = set()
    acc = 0
    for length in line_lengths:
        if acc != 0:
            system_starts.add(acc)
        acc += length
    return Score(title=title, tempo=tempo, parts=[Part(measures=measures)],
                 system_starts=system_starts)
