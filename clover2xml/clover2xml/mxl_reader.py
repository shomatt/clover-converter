"""Parse a MusicXML 4.0 (score-partwise) file into the intermediate Score model.
Inverse of writer.py. Robust to files from MuseScore/Sibelius/our own writer.

Round-trip target: chord (root, kind), key, time, measure count, title, tempo,
clef and system breaks survive .clvz -> model -> MusicXML -> model. Minor losses
in degree/offset detail are acceptable for v1."""
from __future__ import annotations
from fractions import Fraction
from defusedxml.ElementTree import parse as xml_parse

from clover2xml.model import (
    Score, Part, Measure, ChordSym, RhythmEvent, Degree, Symbol,
)

_STEPS = "CDEFGAB"
TICKS_PER_WHOLE = 960   # Clover internal ticks per whole note

# articulation tag name -> Clover articulation name
_ART = {"staccato": "staccato", "accent": "accent", "tenuto": "tenuto",
        "strong-accent": "marcato"}


def _level_from_pitch(step, octave):
    """Inverse of writer's _level_to_pitch: B4 = 34 base. Ignore alter
    (Clover level is diatonic)."""
    return (octave * 7 + _STEPS.index(step)) - 34


def _text(el):
    if el is None:
        return ""
    return (el.text or "").strip()


def _alter_suffix(alter_el):
    """root-alter / bass-alter element -> '#' (+1) / 'b' (-1) / '' (0 or absent)."""
    if alter_el is None:
        return ""
    try:
        a = int(float(_text(alter_el)))
    except (TypeError, ValueError):
        return ""
    if a > 0:
        return "#" * a
    if a < 0:
        return "b" * (-a)
    return ""


def _step_with_alter(parent, step_tag, alter_tag):
    """Build a root/bass string like 'C', 'C#', 'Bb' from a <root>/<bass> element."""
    if parent is None:
        return None
    step_el = parent.find(step_tag)
    if step_el is None or not _text(step_el):
        return None
    return _text(step_el) + _alter_suffix(parent.find(alter_tag))


def _parse_harmony(h) -> ChordSym | None:
    root = _step_with_alter(h.find("root"), "root-step", "root-alter")
    kind = _text(h.find("kind")) or "major"
    bass = _step_with_alter(h.find("bass"), "bass-step", "bass-alter")
    degrees = []
    for deg in h.findall("degree"):
        val_t = _text(deg.find("degree-value"))
        if not val_t:
            continue
        try:
            value = int(float(val_t))
        except ValueError:
            continue
        alter_t = _text(deg.find("degree-alter"))
        try:
            alter = int(float(alter_t)) if alter_t else 0
        except ValueError:
            alter = 0
        dtype = _text(deg.find("degree-type")) or "add"
        degrees.append(Degree(value, alter, dtype))
    return ChordSym(root=root, kind=kind, degrees=degrees, bass=bass)


def _note_fraction(note, divisions) -> Fraction:
    """<duration> (in divisions) -> Fraction, whole note = 1."""
    dur_t = _text(note.find("duration"))
    if not dur_t:
        return Fraction(0)
    try:
        d = int(float(dur_t))
    except ValueError:
        return Fraction(0)
    denom = (divisions or 1) * 4
    return Fraction(d, denom)


def _classify_note(note):
    """Return RhythmEvent kind and level for a <note>."""
    if note.find("rest") is not None:
        return "rest", None
    notehead = note.find("notehead")
    if note.find("unpitched") is not None or (
        notehead is not None and _text(notehead) == "slash"
    ):
        return "slash", None
    pitch = note.find("pitch")
    if pitch is not None:
        step = _text(pitch.find("step"))
        oct_t = _text(pitch.find("octave"))
        if step and oct_t:
            try:
                level = _level_from_pitch(step, int(float(oct_t)))
            except (ValueError, KeyError):
                level = None
            return "pitch", level
        return "pitch", None
    # default: treat as rest-like
    return "rest", None


def _parse_note(note, divisions) -> RhythmEvent:
    kind, level = _classify_note(note)
    duration = _note_fraction(note, divisions)

    beam = "none"
    beam_el = note.find("beam")
    if beam_el is not None and _text(beam_el):
        beam = _text(beam_el)

    tie = False
    for t in note.findall("tie"):
        if t.get("type") == "start":
            tie = True

    notations = note.find("notations")
    slur = None
    articulations = []
    tuplet = None
    if notations is not None:
        slur_el = notations.find("slur")
        if slur_el is not None and slur_el.get("type"):
            slur = slur_el.get("type")
        tup_el = notations.find("tuplet")
        if tup_el is not None:
            tuplet = "begin" if tup_el.get("type") == "start" else "end"
        arts_el = notations.find("articulations")
        if arts_el is not None:
            for a in list(arts_el):
                name = _ART.get(a.tag)
                if name:
                    articulations.append(name)
        if notations.find("fermata") is not None:
            articulations.append("fermata")

    # time-modification with no notations tuplet marker => middle of a tuplet
    if tuplet is None and note.find("time-modification") is not None:
        tm = note.find("time-modification")
        actual = _text(tm.find("actual-notes"))
        if actual == "3":
            tuplet = "continue"

    return RhythmEvent(
        kind=kind, duration=duration, beam=beam, tie=tie, slur=slur,
        articulations=articulations, level=level, tuplet=tuplet,
    )


def _parse_attributes(attrs, measure, divisions):
    """Apply <attributes> to measure; return updated divisions."""
    div_t = _text(attrs.find("divisions"))
    if div_t:
        try:
            divisions = int(float(div_t))
        except ValueError:
            pass
    key = attrs.find("key")
    if key is not None:
        fifths_t = _text(key.find("fifths"))
        if fifths_t:
            try:
                measure.key_fifths = int(float(fifths_t))
            except ValueError:
                pass
    time = attrs.find("time")
    if time is not None:
        beats_t = _text(time.find("beats"))
        bt_t = _text(time.find("beat-type"))
        if beats_t and bt_t:
            try:
                measure.time = (int(float(beats_t)), int(float(bt_t)))
            except ValueError:
                pass
    clef = attrs.find("clef")
    if clef is not None:
        sign = _text(clef.find("sign"))
        if sign in ("G", "F"):
            measure.clef = sign
    return divisions


def _normalize_barline(bl):
    """A <barline> element -> normalized barline value matching the clvz reader's
    vocabulary: light-light / final / repeat-end / repeat-start / none / regular."""
    style = _text(bl.find("bar-style"))
    repeat = bl.find("repeat")
    direction = repeat.get("direction") if repeat is not None else None
    if direction == "backward":
        return "repeat-end"
    if direction == "forward":
        return "repeat-start"
    if style == "light-light":
        return "light-light"
    if style == "light-heavy":
        return "final"
    if style == "heavy-light":
        return "repeat-start"
    if style == "none":
        return "none"
    return "regular"


def _parse_direction(direction, measure):
    for dt in direction.findall("direction-type"):
        reh = dt.find("rehearsal")
        if reh is not None:
            txt = _text(reh)
            if txt:
                measure.symbols.append(Symbol(type="rehearsal", text=txt))
            continue
        words = dt.find("words")
        if words is not None:
            txt = _text(words)
            if txt:
                measure.symbols.append(Symbol(type="free-text", text=txt))


def _tempo_from_direction(direction):
    """Return tempo int from a <direction> (via <sound tempo> or metronome), or None."""
    sound = direction.find("sound")
    if sound is not None and sound.get("tempo"):
        try:
            return int(round(float(sound.get("tempo"))))
        except ValueError:
            pass
    for dt in direction.findall("direction-type"):
        metro = dt.find("metronome")
        if metro is not None:
            pm = _text(metro.find("per-minute"))
            if pm:
                try:
                    return int(round(float(pm)))
                except ValueError:
                    pass
    return None


def _parse_measure(meas, divisions):
    """Parse a single <measure>; return (Measure, updated_divisions, new_system)."""
    measure = Measure(barline_left="regular", barline_right="regular")
    new_system = False
    pos = Fraction(0)   # cumulative position in whole notes

    for child in meas:
        tag = child.tag
        if tag == "print":
            if child.get("new-system") == "yes":
                new_system = True
        elif tag == "attributes":
            divisions = _parse_attributes(child, measure, divisions)
        elif tag == "barline":
            location = child.get("location", "right")
            value = _normalize_barline(child)
            if location == "left":
                measure.barline_left = value
            else:
                measure.barline_right = value
            ending = child.find("ending")
            if ending is not None:
                num = ending.get("number")
                etype = ending.get("type")
                if etype == "start":
                    measure.ending_start = num
                elif etype in ("stop", "discontinue"):
                    measure.ending_stop = num
        elif tag == "harmony":
            sym = _parse_harmony(child)
            if sym is not None:
                sym.offset = float(pos) * TICKS_PER_WHOLE
                measure.chords.append(sym)
        elif tag == "note":
            if child.get("print-object") == "no":
                # Invisible filler rest (a master-chart blank bar in MusicXML). A
                # master chart is chords-only by default — do NOT materialize this as
                # a visible rest/note. It still consumes time so harmony offsets after
                # it stay correct.
                if child.find("chord") is None:
                    pos += _note_fraction(child, divisions)
            else:
                ev = _parse_note(child, divisions)
                measure.events.append(ev)
                # only advance position for notes that are not part of a chord stack
                if child.find("chord") is None:
                    pos += ev.duration
        elif tag == "backup":
            pos -= _note_fraction(child, divisions)
        elif tag == "forward":
            pos += _note_fraction(child, divisions)
        elif tag == "direction":
            _parse_direction(child, measure)

    return measure, divisions, new_system


def parse_musicxml(path) -> Score:
    root = xml_parse(str(path)).getroot()

    # title
    title = ""
    work = root.find("work")
    if work is not None:
        title = _text(work.find("work-title"))
    if not title:
        title = _text(root.find("movement-title"))

    # first part only
    part_el = root.find("part")
    measures = []
    tempo = None
    system_starts = set()
    divisions = 1

    if part_el is not None:
        for mi, meas in enumerate(part_el.findall("measure")):
            # tempo: first one found anywhere
            if tempo is None:
                for direction in meas.findall("direction"):
                    t = _tempo_from_direction(direction)
                    if t is not None:
                        tempo = t
                        break
            measure, divisions, new_system = _parse_measure(meas, divisions)
            if new_system:
                system_starts.add(mi)
            measures.append(measure)

    return Score(
        title=title, tempo=tempo, parts=[Part(measures=measures)],
        system_starts=system_starts,
    )
