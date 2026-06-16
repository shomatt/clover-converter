from __future__ import annotations
import re

def time_to_tuple(t: str) -> tuple[int, int]:
    if t in ("time-C", "time_c"):
        return (4, 4)
    m = re.search(r"(\d+)_(\d+)$", t)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    raise ValueError(f"unknown time type: {t}")

def key_to_fifths(k: str) -> int:
    m = re.search(r"(sharp|flat)(\d+)$", k)
    if not m:
        raise ValueError(f"unknown key type: {k}")
    n = int(m.group(2))
    return n if m.group(1) == "sharp" else -n

def clef_to_sign(c: str) -> str:
    table = {"clef-g": "G", "clefToon": "G", "clef-f": "F", "clefHeon": "F"}
    if c not in table:
        raise ValueError(f"unknown clef type: {c}")
    return table[c]

def barline_style(v: str) -> str:
    return {
        "single": "regular",
        "double": "light-light",
        "great-double": "final",        # final/heavy barline
        "transparent": "none",          # invisible barline
        "repeat-backward": "repeat-end",
        "repeat-forward": "repeat-start",
    }.get(v, "regular")
