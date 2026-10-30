from __future__ import annotations
import warnings
from fractions import Fraction
from xml.etree import ElementTree as ET
from clover2xml.model import Score, ChordSym, RhythmEvent

DIVISIONS = 480          # MusicXML divisions per quarter note
TICKS_PER_WHOLE = 960    # Clover internal ticks per whole note
CLEF_LINE = {"G": "2", "F": "4"}
_ART = {"staccato": "staccato", "accent": "accent", "tenuto": "tenuto",
        "marcato": "strong-accent"}


class TieWarning(UserWarning):
    """Clover のタイの相手が無い・高さが違う時の警告（タイは付けずに続行）。"""


_STEPS = "CDEFGAB"
_SHARP_ORDER = "FCGDAEB"
_FLAT_ORDER = "BEADGCF"


def _level_to_pitch(level, key_fifths):
    diatonic = 34 + level          # B4 = 4*7 + 6 = 34
    step = _STEPS[diatonic % 7]
    octave = diatonic // 7
    alter = 0
    k = key_fifths or 0
    if k > 0 and step in _SHARP_ORDER[:k]:
        alter = 1
    elif k < 0 and step in _FLAT_ORDER[:-k]:
        alter = -1
    return step, octave, alter
_TYPES = [(Fraction(1, 1), "whole"), (Fraction(1, 2), "half"),
          (Fraction(1, 4), "quarter"), (Fraction(1, 8), "eighth"),
          (Fraction(1, 16), "16th"), (Fraction(1, 32), "32nd"),
          (Fraction(1, 64), "64th")]

def _sub(parent: ET.Element, tag: str, text=None, **attrib) -> ET.Element:
    el = ET.SubElement(parent, tag, {k: str(v) for k, v in attrib.items()})
    if text is not None:
        el.text = str(text)
    return el

def _duration_ticks(frac: Fraction) -> int:
    return int(frac * 4 * DIVISIONS)

def _type_name(frac: Fraction) -> str:
    best = min(_TYPES, key=lambda t: abs(float(t[0]) - float(frac)))
    return best[1]

def _type_and_dots(frac: Fraction):
    """(type, dots) for a note value; dotted values (3/8, 7/16 ...) get <dot/>s."""
    for base, name in _TYPES:
        for dots in range(4):
            if base * (2 - Fraction(1, 2 ** dots)) == frac:
                return name, dots
    return _type_name(frac), 0

def _sub_type(n: ET.Element, frac: Fraction) -> None:
    """Emit <type> followed by any <dot/>s."""
    name, dots = _type_and_dots(frac)
    _sub(n, "type", name)
    for _ in range(dots):
        _sub(n, "dot")

def _root_step_alter(root: str):
    step = root[0]
    alter = root.count("#") - root.count("b")
    return step, alter

def _add_harmony(measure: ET.Element, c: ChordSym) -> None:
    h = _sub(measure, "harmony")
    if c.kind == "other" and c.raw:
        h.append(ET.Comment(f" clover: {c.raw} "))
    step, alter = _root_step_alter(c.root)
    root = _sub(h, "root")
    _sub(root, "root-step", step)
    if alter:
        _sub(root, "root-alter", alter)
    # use-symbols="yes" requests symbol rendering (△ for maj7, - for minor, ø for
    # half-dim, o/+ etc.) — matches Clover's look in MuseScore/Dorico/Finale/Sibelius.
    if c.kind == "other":
        kel = _sub(h, "kind", "other", **{"use-symbols": "yes"})
        kel.set("text", c.raw)
    else:
        _sub(h, "kind", c.kind, **{"use-symbols": "yes"})
    for d in c.degrees:
        deg = _sub(h, "degree")
        _sub(deg, "degree-value", d.value)
        _sub(deg, "degree-alter", d.alter)
        _sub(deg, "degree-type", d.type)
    if c.bass:
        bstep, balter = _root_step_alter(c.bass)
        bass = _sub(h, "bass")
        _sub(bass, "bass-step", bstep)
        if balter:
            _sub(bass, "bass-alter", balter)

def _emit_slash(measure: ET.Element, frac: Fraction) -> ET.Element:
    """Emit an unpitched slash note (display B/4) of the given length."""
    n = _sub(measure, "note")
    unp = _sub(n, "unpitched")
    _sub(unp, "display-step", "B")
    _sub(unp, "display-octave", "4")
    _sub(n, "duration", _duration_ticks(frac))
    _sub_type(n, frac)
    _sub(n, "notehead", "slash")
    return n

def _emit_measure_rest(measure: ET.Element, frac: Fraction) -> ET.Element:
    """Emit a full-measure rest (no <type> for a measure rest)."""
    n = _sub(measure, "note")
    _sub(n, "rest", measure="yes")
    _sub(n, "duration", _duration_ticks(frac))
    return n


def _emit_hidden_rest(measure, frac, full=False):
    """Emit a hidden (print-object=no) rest so the bar prints blank."""
    n = _sub(measure, "note", **{"print-object": "no"})
    if full:
        _sub(n, "rest", measure="yes")
    else:
        _sub(n, "rest")
    _sub(n, "duration", _duration_ticks(frac))
    if not full:
        _sub_type(n, frac)


_BARSTYLE = {"light-light": "light-light", "repeat-end": "light-heavy",
             "repeat-start": "heavy-light", "final": "light-heavy", "none": "none"}


def _emit_barline_with_ending(measure, value, location, ending_num=None, ending_type=None):
    if value in (None, "", "regular", "single") and ending_num is None:
        return
    bl = _sub(measure, "barline", location=location)
    if value not in (None, "", "regular", "single"):
        _sub(bl, "bar-style", _BARSTYLE.get(value, "regular"))
        if value == "repeat-end":
            _sub(bl, "repeat", direction="backward")
        elif value == "repeat-start":
            _sub(bl, "repeat", direction="forward")
    if ending_num is not None:
        _sub(bl, "ending", number=ending_num, type=ending_type)

def _sub_duration_ties(n: ET.Element, ev: RhythmEvent, tie_stop: bool, tie_start: bool) -> None:
    """<duration> then <tie>s (MusicXML requires ties right after duration).
    Clover flags the tie on its first note; the next note gets the stop."""
    _sub(n, "duration", _duration_ticks(ev.duration))
    if tie_stop:
        _sub(n, "tie", type="stop")
    if tie_start:
        _sub(n, "tie", type="start")

def _tie_key(ev: RhythmEvent, key_fifths):
    """What a tie must match: the sounding pitch, "slash" for slashes, None for rests."""
    if ev.kind == "pitch":
        return _level_to_pitch(ev.level or 0, key_fifths)
    if ev.kind == "slash":
        return "slash"
    return None

def _drop_tie_start(n: ET.Element) -> None:
    """Remove a tie start (and its <tied>) whose partner turned out to be invalid."""
    for t in n.findall("tie"):
        if t.get("type") == "start":
            n.remove(t)
    notations = n.find("notations")
    if notations is not None:
        for t in notations.findall("tied"):
            if t.get("type") == "start":
                notations.remove(t)
        if not len(notations):
            n.remove(notations)

def _add_note(measure: ET.Element, ev: RhythmEvent, key_fifths, tie_stop=False,
              tie_start=None) -> ET.Element:
    if tie_start is None:
        tie_start = ev.tie and ev.kind != "rest"
    n = _sub(measure, "note")
    # type/duration: for tuplet members the DISPLAYED note value is duration*3/2
    disp = ev.duration * Fraction(3, 2) if ev.tuplet else ev.duration
    if ev.kind == "rest":
        _sub(n, "rest")
        _sub_duration_ties(n, ev, tie_stop, tie_start)
        _sub_type(n, disp)
    elif ev.kind == "pitch":
        step, octave, alter = _level_to_pitch(ev.level or 0, key_fifths)
        p = _sub(n, "pitch")
        _sub(p, "step", step)
        if alter:
            _sub(p, "alter", alter)
        _sub(p, "octave", octave)
        _sub_duration_ties(n, ev, tie_stop, tie_start)
        _sub_type(n, disp)
    else:  # slash
        unp = _sub(n, "unpitched")
        _sub(unp, "display-step", "B")
        _sub(unp, "display-octave", "4")
        _sub_duration_ties(n, ev, tie_stop, tie_start)
        _sub_type(n, disp)
        _sub(n, "notehead", "slash")
    if ev.tuplet:
        tm = _sub(n, "time-modification")
        _sub(tm, "actual-notes", 3)
        _sub(tm, "normal-notes", 2)
    if ev.beam in ("begin", "continue", "end"):
        _sub(n, "beam", ev.beam, number="1")
    if ev.slur or ev.tuplet or ev.articulations or tie_start or tie_stop:
        notations = _sub(n, "notations")
        if tie_stop:
            _sub(notations, "tied", type="stop")
        if tie_start:
            _sub(notations, "tied", type="start")
        if ev.tuplet == "begin":
            _sub(notations, "tuplet", type="start")
        elif ev.tuplet == "end":
            _sub(notations, "tuplet", type="stop")
        if ev.slur:
            _sub(notations, "slur", type=ev.slur)
        arts = [a for a in ev.articulations if a in _ART]
        if "fermata" in ev.articulations:
            _sub(notations, "fermata")
        if arts:
            ael = _sub(notations, "articulations")
            for a in arts:
                _sub(ael, _ART[a])
    return n

def build_musicxml(score: Score) -> str:
    root = ET.Element("score-partwise", {"version": "4.0"})
    work = _sub(root, "work")
    _sub(work, "work-title", score.title or "Untitled")
    plist = _sub(root, "part-list")
    sp = _sub(plist, "score-part", id="P1")
    _sub(sp, "part-name", "Chart")
    part = _sub(root, "part", id="P1")
    active_time = (4, 4)
    active_key = None
    # (note element, tie key, measure number) of a note whose tie start still
    # awaits its partner; the next note stops it only if the pitch matches.
    pending = None

    def break_tie(reason):
        nonlocal pending
        if pending is not None:
            _drop_tie_start(pending[0])
            warnings.warn(f"measure {pending[2]}: tie dropped ({reason})",
                          TieWarning, stacklevel=3)
            pending = None
    for mi, mm in enumerate(score.parts[0].measures):
        if mm.time is not None:
            active_time = mm.time
        active_key = mm.key_fifths if mm.key_fifths is not None else active_key
        beats, beat_type = active_time
        bar_ticks = TICKS_PER_WHOLE * beats // beat_type
        meas = _sub(part, "measure", number=mi + 1)
        if mi in score.system_starts:
            _sub(meas, "print", **{"new-system": "yes"})
        attrs = ET.Element("attributes")
        _sub(attrs, "divisions", DIVISIONS)
        if mm.key_fifths is not None:
            _sub(_sub(attrs, "key"), "fifths", mm.key_fifths)
        if mm.time is not None:
            t = _sub(attrs, "time")
            _sub(t, "beats", mm.time[0])
            _sub(t, "beat-type", mm.time[1])
        if mm.clef in CLEF_LINE:
            cl = _sub(attrs, "clef")
            _sub(cl, "sign", mm.clef)
            _sub(cl, "line", CLEF_LINE[mm.clef])
        if len(attrs):
            meas.append(attrs)
        if mi == 0 and score.tempo:
            d = _sub(meas, "direction", placement="above")
            dt = _sub(d, "direction-type")
            mt = _sub(dt, "metronome")
            _sub(mt, "beat-unit", "quarter")
            _sub(mt, "per-minute", score.tempo)
            _sub(d, "sound", tempo=score.tempo)

        chords = sorted([c for c in mm.chords if c.root], key=lambda c: c.offset)

        # 1) left barline (Bug D) + ending start
        _emit_barline_with_ending(meas, mm.barline_left, "left",
                                  mm.ending_start, "start" if mm.ending_start else None)

        # 2) directions for symbols (Bug C)
        for sym in mm.symbols:
            if sym.type == "rehearsal":
                d = _sub(meas, "direction", placement="above")
                _sub(_sub(d, "direction-type"), "rehearsal", sym.text)
            elif sym.type in ("free-text", "navigation", "dynamic"):
                d = _sub(meas, "direction", placement="above")
                _sub(_sub(d, "direction-type"), "words", sym.text)
                if sym.type == "navigation" and sym.text == "Fine":
                    _sub(d, "sound", fine="yes")
            # skip sym.type == "tempo" (global tempo emitted at measure 0)

        # 3) interleave harmony + notes (Bugs A, B)
        if mm.events:
            pos = 0
            ci = 0
            for ev in mm.events:
                while ci < len(chords) and chords[ci].offset <= pos:
                    _add_harmony(meas, chords[ci]); ci += 1
                tk = _tie_key(ev, active_key)
                stop = pending is not None and tk == pending[1]
                if pending is not None and not stop:
                    break_tie("next note is a rest" if tk is None
                              else "next note has a different pitch")
                if ev.tie and tk is None:
                    warnings.warn(f"measure {mi + 1}: tie on a rest dropped",
                                  TieWarning, stacklevel=2)
                start = ev.tie and tk is not None
                n = _add_note(meas, ev, active_key, tie_stop=stop, tie_start=start)
                pending = (n, tk, mi + 1) if start else None
                pos += int(ev.duration * TICKS_PER_WHOLE)
            remaining = chords[ci:]
            if remaining and pos < bar_ticks:
                by_off = {}
                for c in remaining:
                    key = max(int(c.offset), pos)
                    by_off.setdefault(key, []).append(c)
                offs = sorted(by_off)
                if offs[0] != pos:
                    offs = [pos] + offs
                bounds = offs + [bar_ticks]
                for i, start in enumerate(offs):
                    seg = bounds[i + 1] - start
                    if seg <= 0:
                        continue
                    for c in by_off.get(start, []):
                        _add_harmony(meas, c)
                    break_tie("no following note")
                    _emit_slash(meas, Fraction(seg, TICKS_PER_WHOLE))
            else:
                for c in remaining:
                    _add_harmony(meas, c)
        elif chords:
            break_tie("no following note")
            offsets = sorted({int(c.offset) for c in chords})
            if not offsets or offsets[0] != 0:
                offsets = [0] + offsets
            by_off = {}
            for c in chords:
                by_off.setdefault(int(c.offset), []).append(c)
            bounds = offsets + [bar_ticks]
            single = len(offsets) == 1
            for i, start in enumerate(offsets):
                seg = bounds[i + 1] - start
                if seg <= 0:
                    continue
                for c in by_off.get(start, []):
                    _add_harmony(meas, c)
                _emit_hidden_rest(meas, Fraction(seg, TICKS_PER_WHOLE), full=single)
        else:
            break_tie("no following note")
            _emit_hidden_rest(meas, Fraction(bar_ticks, TICKS_PER_WHOLE), full=True)

        # 4) right barline + ending stop
        _emit_barline_with_ending(meas, mm.barline_right, "right",
                                  mm.ending_stop, "stop" if mm.ending_stop else None)
    break_tie("no following note")
    ET.indent(root)
    body = ET.tostring(root, encoding="unicode")
    doctype = ('<!DOCTYPE score-partwise PUBLIC '
               '"-//Recordare//DTD MusicXML 4.0 Partwise//EN" '
               '"http://www.musicxml.org/dtds/partwise.dtd">')
    return f'<?xml version="1.0" encoding="UTF-8"?>\n{doctype}\n{body}\n'
