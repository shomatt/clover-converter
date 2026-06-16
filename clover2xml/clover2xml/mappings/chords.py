from __future__ import annotations
import re
from clover2xml.model import ChordSym, Degree

# step2 → MusicXML harmony-kind
KIND = {
    "none": "major",
    "m": "minor",
    "7": "dominant",
    "maj7": "major-seventh",
    "m7": "minor-seventh",
    "m6": "minor-sixth",
    "m7-5": "half-diminished",
    "dim": "diminished",
    "dim7": "diminished-seventh",
    "mmaj7": "minor-major-seventh",
    "aug": "augmented",
    "6": "major-sixth",
    "sus4": "suspended-fourth",
}

def _root(step1: str) -> str | None:
    if step1 in ("none", ""):
        return None
    return step1  # "B", "C#", "F#" 等はそのまま（writer 側で step/alter 分解）

def _tension_degree(tok: str) -> Degree | None:
    m = re.fullmatch(r"([+\-]?)(\d+)", tok)
    if not m:
        return None
    alter = {"+": 1, "-": -1, "": 0}[m.group(1)]
    val = int(m.group(2))
    typ = "alter" if val == 5 else "add"   # +5/-5 alter the 5th; 9/11/13/2 are additions
    return Degree(val, alter, typ)

def _degrees(step3: str) -> tuple[list[Degree], list[str]]:
    """step3 を degree 群に変換。複合テンション (9(13) 等) にも対応。未対応は警告で返す。"""
    if step3 in ("none", ""):
        return [], []
    if step3 == "omit3":
        return [Degree(3, 0, "subtract")], []
    if step3 == "sus4":
        return [Degree(4, 0, "add"), Degree(3, 0, "subtract")], []
    if step3 == "add9":
        return [Degree(9, 0, "add")], []
    tokens = re.findall(r"[+\-]?\d+", step3)   # "9(13)"->['9','13'], "+5(+9)"->['+5','+9']
    degs, warn = [], []
    for tok in tokens:
        d = _tension_degree(tok)
        if d:
            degs.append(d)
        else:
            warn.append(tok)
    if not tokens:
        warn.append(step3)
    return degs, warn

def chord_value_to_sym(step1: str, step2: str, step3: str, base: str) -> ChordSym | None:
    if step1 in ("none", "") and step2 in ("none", ""):
        return None
    raw = f"step2={step2} step3={step3}"
    kind = KIND.get(step2)
    if kind is None:
        kind = "other"
    degs, warn = _degrees(step3)
    if warn:
        raw += f" (unmapped step3: {','.join(warn)})"
    bass = None if base in ("none", "") else base
    return ChordSym(root=_root(step1), kind=kind, degrees=degs, bass=bass, raw=raw)
