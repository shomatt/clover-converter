"""Chord detection (MIDI notes → Clover step1/2/3/base) and the inverse
(ChordSym → MIDI notes). Pure stdlib — used by MIDI import/export and by the
live MIDI keyboard tool. No rtmidi dependency."""
from __future__ import annotations

from clover2xml.model import ChordSym, Degree

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]

# Clover step2 quality → required intervals from root (semitones), most-specific
# (longest) templates first so a 7th chord beats the triad it contains.
_QUALITIES = [
    ("dim7",  frozenset({0, 3, 6, 9})),
    ("m7-5",  frozenset({0, 3, 6, 10})),
    ("mmaj7", frozenset({0, 3, 7, 11})),
    ("maj7",  frozenset({0, 4, 7, 11})),
    ("m7",    frozenset({0, 3, 7, 10})),
    ("7",     frozenset({0, 4, 7, 10})),
    ("m6",    frozenset({0, 3, 7, 9})),
    ("6",     frozenset({0, 4, 7, 9})),
    ("dim",   frozenset({0, 3, 6})),
    ("aug",   frozenset({0, 4, 8})),
    ("m",     frozenset({0, 3, 7})),
    ("none",  frozenset({0, 4, 7})),
    ("sus4",  frozenset({0, 5, 7})),
]

# leftover interval → tension token (7th intervals 10/11 are part of quality, not tension)
_TENSION = {2: "9", 5: "11", 9: "13", 1: "-9", 3: "+9", 6: "+11", 8: "-13"}


def detect_chord(notes):
    """notes: list of MIDI note numbers. Returns (step1, step2, step3, base) or None."""
    if not notes:
        return None
    pcs = {n % 12 for n in notes}
    bass = min(notes) % 12

    best = None  # (score, root, step2, extra)
    for root in sorted(pcs):
        iv = frozenset((pc - root) % 12 for pc in pcs)
        for step2, tmpl in _QUALITIES:
            if tmpl <= iv:
                extra = iv - tmpl
                score = len(tmpl) * 10 - len(extra) + (3 if root == bass else 0)
                if best is None or score > best[0]:
                    best = (score, root, step2, extra, iv)
    if best is None:
        return (NAMES[bass], "none", "none", "none")

    _, root, step2, extra, iv = best
    step1 = NAMES[root]
    base = NAMES[bass] if bass != root else "none"

    toks = [_TENSION[e] for e in sorted(extra) if e in _TENSION]
    step3 = "none"
    if toks:
        if toks[0] == "9" and not (10 in iv or 11 in iv):
            toks[0] = "add9"
        step3 = toks[0] if len(toks) == 1 else toks[0] + "".join(f"({t})" for t in toks[1:])
    return (step1, step2, step3, base)


def detect_chord_sym(notes):
    """Detect and return a ChordSym (or None)."""
    res = detect_chord(notes)
    if res is None:
        return None
    from clover2xml.mappings.chords import chord_value_to_sym
    return chord_value_to_sym(*res)


# ── inverse: ChordSym → MIDI notes (for MIDI export) ───────────────────
_PC = {"C": 0, "C#": 1, "DB": 1, "D": 2, "D#": 3, "EB": 3, "E": 4, "FB": 4,
       "E#": 5, "F": 5, "F#": 6, "GB": 6, "G": 7, "G#": 8, "AB": 8, "A": 9,
       "A#": 10, "BB": 10, "B": 11, "CB": 11}

# MusicXML harmony-kind → chord intervals from the root (semitones).
_KIND_INTERVALS = {
    "major": [0, 4, 7], "minor": [0, 3, 7], "dominant": [0, 4, 7, 10],
    "major-seventh": [0, 4, 7, 11], "minor-seventh": [0, 3, 7, 10],
    "minor-sixth": [0, 3, 7, 9], "half-diminished": [0, 3, 6, 10],
    "diminished": [0, 3, 6], "diminished-seventh": [0, 3, 6, 9],
    "minor-major-seventh": [0, 3, 7, 11], "augmented": [0, 4, 8],
    "major-sixth": [0, 4, 7, 9], "suspended-fourth": [0, 5, 7],
    "other": [0, 4, 7],
}

# scale degree → semitone above the root
_DEG_SEMI = {2: 2, 3: 4, 4: 5, 5: 7, 6: 9, 7: 11, 9: 14, 11: 17, 13: 21}


def _pc(name):
    if not name:
        return None
    return _PC.get(name.upper())


def chord_to_notes(sym: ChordSym, octave: int = 4) -> list[int]:
    """ChordSym → sorted MIDI note numbers (root-position voicing).
    Root placed at C{octave}=12*(octave+1); bass (if any) one octave below."""
    root = _pc(sym.root)
    if root is None:
        return []
    intervals = list(_KIND_INTERVALS.get(sym.kind, _KIND_INTERVALS["other"]))
    ivset = set(intervals)

    for d in sym.degrees:
        semi = _DEG_SEMI.get(d.value)
        if semi is None:
            continue
        semi += d.alter
        if d.type == "subtract":
            ivset.discard(_DEG_SEMI.get(d.value, semi))
            ivset.discard(semi)
        elif d.type == "alter":
            # replace the natural degree with the altered one (e.g. ♯5/♭5)
            ivset.discard(_DEG_SEMI.get(d.value))
            ivset.add(semi)
        else:  # add
            ivset.add(semi)

    base_midi = 12 * (octave + 1)            # C4 = 60
    notes = sorted(base_midi + root + iv for iv in sorted(ivset))
    bass = _pc(sym.bass)
    if bass is not None:
        notes.insert(0, 12 * octave + bass)   # one octave below
    return notes
