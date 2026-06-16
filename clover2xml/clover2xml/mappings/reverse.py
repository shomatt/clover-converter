"""Reverse mappings: intermediate model values → Clover XML attribute strings.
Inverse of mappings/chords.py and mappings/meta.py. Used by clover_writer.py to
generate .clvz files (MusicXML→Clover and MIDI→Clover share this)."""
from __future__ import annotations
from clover2xml.mappings.chords import KIND

# MusicXML harmony-kind → Clover step2 (invert KIND; first match wins for dup values)
_KIND_INV = {}
for _step2, _kind in KIND.items():
    _KIND_INV.setdefault(_kind, _step2)


def kind_to_step2(kind: str) -> str:
    """major-seventh→maj7, minor→m, dominant→7, ... Unknown→'none'."""
    return _KIND_INV.get(kind, "none")


def degrees_to_step3(degrees) -> str:
    """Reconstruct a Clover step3 string from a list of Degree.
    Handles the special shapes (omit3/sus4/add9) and compound tensions (9(13),
    +5(+9), 9(+11)). v1 note: '9' vs 'add9' both round-trip to 'add9' (musically
    equivalent) — minor, harmless lossiness."""
    if not degrees:
        return "none"
    vals = [(d.value, d.alter, d.type) for d in degrees]
    if vals == [(3, 0, "subtract")]:
        return "omit3"
    if sorted(vals) == sorted([(4, 0, "add"), (3, 0, "subtract")]):
        return "sus4"
    if vals == [(9, 0, "add")]:
        return "add9"

    def _tok(d):
        sign = "+" if d.alter > 0 else "-" if d.alter < 0 else ""
        return f"{sign}{d.value}"

    toks = [_tok(d) for d in degrees]
    if len(toks) == 1:
        return toks[0]
    # compound: main token followed by parenthesised extras, e.g. 9(13), +5(+9)
    return toks[0] + "".join(f"({t})" for t in toks[1:])


def step2_step3_from_raw(raw: str):
    """If a ChordSym still carries its original 'step2=X step3=Y' raw string
    (round-trip from a real .clvz), extract them for lossless reproduction.
    Returns (step2, step3) or None if raw isn't in that form."""
    if not raw or "step2=" not in raw:
        return None
    step2 = step3 = None
    for part in raw.split():
        if part.startswith("step2="):
            step2 = part[len("step2="):]
        elif part.startswith("step3="):
            step3 = part[len("step3="):]
    if step2 is None or step3 is None:
        return None
    return step2, step3


def fifths_to_key(fifths) -> str | None:
    if fifths is None:
        return None
    return f"key-sharp{fifths}" if fifths >= 0 else f"key-flat{-fifths}"


def time_to_type(time) -> str | None:
    if time is None:
        return None
    if time == (4, 4):
        return "time-C"
    return f"time-{time[0]}_{time[1]}"


def clef_to_type(clef) -> str | None:
    return {"G": "clef-g", "F": "clef-f"}.get(clef)


_BARLINE_INV = {
    "regular": "single", "single": "single",
    "light-light": "double", "final": "great-double",
    "none": "transparent",
    "repeat-end": "repeat-backward", "repeat-start": "repeat-forward",
}


def barline_to_clover(value) -> str:
    return _BARLINE_INV.get(value, "single")
