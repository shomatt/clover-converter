from __future__ import annotations
from dataclasses import dataclass, field
from fractions import Fraction

@dataclass
class Degree:
    value: int            # 9, 11, 13, 5, 3 ...
    alter: int            # -1, 0, +1
    type: str             # "add" | "alter" | "subtract"

@dataclass
class ChordSym:
    root: str | None      # "B", "C#", None=コードなし
    kind: str             # MusicXML harmony-kind
    degrees: list[Degree] = field(default_factory=list)
    bass: str | None = None
    offset: float = 0.0   # 小節内位置
    raw: str = ""         # 元 step2/step3（非破壊用）

@dataclass
class RhythmEvent:
    kind: str             # "slash" | "rest" | "pitch"
    duration: Fraction    # 全音符=1 に正規化
    beam: str = "none"    # begin|continue|end|none
    tie: bool = False
    slur: str | None = None      # "start"|"stop"|None
    articulations: list[str] = field(default_factory=list)
    level: int | None = None  # Clover staff level when kind=="pitch"
    tuplet: str | None = None # "begin"|"continue"|"end" for triplet members, else None

@dataclass
class Symbol:
    type: str             # "rehearsal"|"tempo"|"free-text"
    text: str

@dataclass
class Measure:
    clef: str | None = None
    key_fifths: int | None = None
    time: tuple[int, int] | None = None
    barline_left: str = "single"
    barline_right: str = "single"
    chords: list[ChordSym] = field(default_factory=list)
    events: list[RhythmEvent] = field(default_factory=list)
    symbols: list[Symbol] = field(default_factory=list)
    ending_start: str | None = None   # ending number when this measure begins a volta
    ending_stop: str | None = None    # ending number when this measure ends a volta

@dataclass
class Part:
    measures: list[Measure] = field(default_factory=list)

@dataclass
class Score:
    title: str = ""
    tempo: int | None = None
    parts: list[Part] = field(default_factory=list)
    system_starts: set = field(default_factory=set)
