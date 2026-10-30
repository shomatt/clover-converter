"""clover2xml（.clvz → MusicXML）の回帰試験。

入力はすべてこの場で組み立てる架空の短い譜面（合成データ）で、書式は
reader.py / clover_writer.py が読み書きする Clover XML（gzip）に合わせている。
出力の MusicXML は文字列比較ではなく、XML として読んで要素を比べる。
"""
from __future__ import annotations

import gzip
import time
from fractions import Fraction
from xml.etree import ElementTree as ET

import pytest

from clover2xml.cli import main as cli_main
from clover2xml.reader import parse_score
from clover2xml.writer import build_musicxml, DIVISIONS

QUARTER = 240           # Clover ティック（全音符 = 960）
WHOLE = 960


# ---------------------------------------------------------------------------
# 架空の譜面を組み立てる道具
# ---------------------------------------------------------------------------

def chord(step1, step2="none", step3="none", base="none", timing=0):
    return (f'<chord type="chord" timing="{timing}">'
            f'<chord-value step1="{step1}" step2="{step2}" step3="{step3}" base="{base}" />'
            f'</chord>')


def note(dur, kind="slash", level=0, extra="", tag="harmony", attrs=""):
    inner = {"slash": '<slash stemless="false" />',
             "rest": "<rest />",
             "pitch": f'<pitch level="{level}" head="normal" />'}[kind]
    return (f'<{tag} beam="none" duration="{dur}" {attrs}>'
            f'<notes>{inner}</notes>{extra}</{tag}>')


def text_symbol(text, typ="reharsal"):
    return (f'<text-symbol type="{typ}"><formatted-texts><formatted-text>'
            f'<arbitrary-text>{text}</arbitrary-text>'
            f'</formatted-text></formatted-texts></text-symbol>')


def measure(chords=(), notes=(), left="single", right="single",
            clef=None, key=None, time_sig=None, symbols=""):
    head = f"<barline-left>{left}</barline-left><barline-right>{right}</barline-right>"
    if clef:
        head += f'<clef type="{clef}" />'
    if key:
        head += f'<key type="{key}" />'
    if time_sig:
        head += f'<time type="{time_sig}" />'
    return (f'<measure-set><part1 width="0.25">{head}'
            f'<symbols>{symbols}</symbols>'
            f'<chords>{"".join(chords)}</chords>'
            f'<harmonies>{"".join(notes)}</harmonies>'
            f'</part1></measure-set>')


def clover_doc(measures, lines=(), title=None, extra_root=""):
    title_xml = ""
    if title is not None:
        title_xml = (f'<title type="song-property"><formatted-texts><formatted-text>'
                     f'<arbitrary-text>{title}</arbitrary-text>'
                     f'</formatted-text></formatted-texts></title>')
    lines_xml = "".join(f'<line partition="{n}" parts="1" />' for n in lines)
    return ('<?xml version="1.0" encoding="utf-8"?>'
            '<clover data-struct-version="1.5" xml:space="preserve">'
            f'<lines><song partition="1" parts="1" rows="1">{title_xml}</song>{lines_xml}</lines>'
            f'{extra_root}<measure-sets>{"".join(measures)}</measure-sets></clover>')


@pytest.fixture
def clvz(tmp_path):
    """文字列/バイト列 → 一時 .clvz のパス。"""
    counter = {"n": 0}

    def _make(doc, gz=True):
        counter["n"] += 1
        p = tmp_path / f"synth{counter['n']}.clvz"
        data = doc.encode("utf-8") if isinstance(doc, str) else doc
        if gz:
            with gzip.open(p, "wb") as f:
                f.write(data)
        else:
            p.write_bytes(data)
        return p
    return _make


def to_xml(path) -> ET.Element:
    """.clvz → MusicXML 文字列 → <score-partwise> 要素。"""
    xml = build_musicxml(parse_score(path))
    assert xml.startswith('<?xml version="1.0" encoding="UTF-8"?>')
    root = ET.fromstring(xml.encode("utf-8"))
    assert root.tag == "score-partwise"
    return root


def convert(clvz, measures, **kw) -> ET.Element:
    return to_xml(clvz(clover_doc(measures, **kw)))


def measures_of(root):
    return root.findall("./part/measure")


def sounding_notes(m):
    """小節内の <note>（<chord/> 付きの同時発音を除く）。"""
    return [n for n in m.findall("note") if n.find("chord") is None]


def bar_divisions(m):
    return sum(int(n.findtext("duration")) for n in sounding_notes(m))


def pitch_of(n):
    p = n.find("pitch")
    return (p.findtext("step"), int(p.findtext("alter") or 0), int(p.findtext("octave")))


def harmony_of(h):
    root = h.find("root")
    bass = h.find("bass")
    return {
        "root": root.findtext("root-step") + {1: "#", -1: "b", 0: ""}[int(root.findtext("root-alter") or 0)],
        "kind": h.findtext("kind"),
        "bass": None if bass is None else
        bass.findtext("bass-step") + {1: "#", -1: "b", 0: ""}[int(bass.findtext("bass-alter") or 0)],
        "degrees": [(int(d.findtext("degree-value")), int(d.findtext("degree-alter")),
                     d.findtext("degree-type")) for d in h.findall("degree")],
    }


# 音価の期待値: Clover ティック → (MusicXML duration, type, 付点の数)
NOTE_VALUES = [
    (960, 1920, "whole", 0),
    (480, 960, "half", 0),
    (240, 480, "quarter", 0),
    (120, 240, "eighth", 0),
    (60, 120, "16th", 0),
    (30, 60, "32nd", 0),
]
DOTTED_VALUES = [
    (720, 1440, "half", 1),
    (360, 720, "quarter", 1),
    (180, 360, "eighth", 1),
    (90, 180, "16th", 1),
    (840, 1680, "half", 2),
]


def note_value(n):
    return int(n.findtext("duration")), n.findtext("type"), len(n.findall("dot"))


# ---------------------------------------------------------------------------
# 1. 全体の骨格
# ---------------------------------------------------------------------------

def test_skeleton_and_title(clvz):
    root = convert(clvz, [measure(chords=[chord("C")])] * 3, title="Test Tune")
    assert root.get("version") == "4.0"
    assert root.findtext("./work/work-title") == "Test Tune"
    assert root.find("./part-list/score-part").get("id") == "P1"
    ms = measures_of(root)
    assert [m.get("number") for m in ms] == ["1", "2", "3"]
    assert all(m.findtext("./attributes/divisions") == str(DIVISIONS) for m in ms)


def test_untitled_when_no_title(clvz):
    root = convert(clvz, [measure(chords=[chord("C")])])
    assert root.findtext("./work/work-title") == "Untitled"


# ---------------------------------------------------------------------------
# 2. 音符・休符・スラッシュ
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("ticks,dur,typ,dots", NOTE_VALUES)
def test_plain_note_values(clvz, ticks, dur, typ, dots):
    n_per_bar = WHOLE // ticks
    root = convert(clvz, [measure(notes=[note(ticks)] * n_per_bar)])
    notes = sounding_notes(measures_of(root)[0])
    assert len(notes) == n_per_bar
    assert {note_value(n) for n in notes} == {(dur, typ, dots)}


@pytest.mark.parametrize("ticks,dur,typ,dots", DOTTED_VALUES)
def test_dotted_note_values(clvz, ticks, dur, typ, dots):
    # 付点音符 + 残りを 1 個で埋める（どちらも単純音価に限らない）
    root = convert(clvz, [measure(notes=[note(ticks, "pitch", 0),
                                         note(WHOLE - ticks, "rest")])])
    first = sounding_notes(measures_of(root)[0])[0]
    assert note_value(first) == (dur, typ, dots)


def test_slash_rest_pitch_kinds(clvz):
    root = convert(clvz, [measure(notes=[note(QUARTER, "slash"), note(QUARTER, "rest"),
                                         note(QUARTER, "pitch", 0), note(QUARTER, "pitch", -7)])])
    a, b, c, d = sounding_notes(measures_of(root)[0])
    assert a.findtext("./notehead") == "slash"
    assert a.findtext("./unpitched/display-step") == "B"
    assert a.findtext("./unpitched/display-octave") == "4"
    assert b.find("rest") is not None and b.find("pitch") is None
    assert pitch_of(c) == ("B", 0, 4)      # level 0 = 第3線 B4（ト音記号）
    assert pitch_of(d) == ("B", 0, 3)      # 7 段下 = 1 オクターブ下


@pytest.mark.parametrize("level,expected", [
    (0, ("B", 0, 4)), (1, ("C", 0, 5)), (-1, ("A", 0, 4)), (-6, ("C", 0, 4)),
    (5, ("G", 0, 5)), (-13, ("C", 0, 3)),
])
def test_pitch_levels_in_c(clvz, level, expected):
    root = convert(clvz, [measure(key="key-sharp0", notes=[note(WHOLE, "pitch", level)])])
    assert pitch_of(sounding_notes(measures_of(root)[0])[0]) == expected


def test_beam_and_articulations(clvz):
    notes = [note(120, "slash", attrs='beam="begin"').replace('beam="none" ', ""),
             note(120, "slash", attrs='beam="end"').replace('beam="none" ', ""),
             note(QUARTER, "slash", extra='<articulations><a type="staccato" /><a type="accent" /></articulations>'),
             note(QUARTER, "slash", extra='<articulations><a type="marcato" /><a type="fermata" /></articulations>'),
             note(QUARTER, "slash", extra='<articulations><a type="tenuto" /></articulations>')]
    root = convert(clvz, [measure(notes=notes)])
    n = sounding_notes(measures_of(root)[0])
    assert n[0].findtext("beam") == "begin" and n[1].findtext("beam") == "end"
    assert n[2].find("beam") is None
    assert [a.tag for a in n[2].find("./notations/articulations")] == ["staccato", "accent"]
    assert [a.tag for a in n[3].find("./notations/articulations")] == ["strong-accent"]
    assert n[3].find("./notations/fermata") is not None
    assert [a.tag for a in n[4].find("./notations/articulations")] == ["tenuto"]


def test_triplets(clvz):
    trip = [note(80, "slash", tag="triplet-harmony", attrs=f'tuplet="{t}"')
            for t in ("begin", "continue", "end")]
    root = convert(clvz, [measure(notes=trip + [note(QUARTER)] * 3)])
    n = sounding_notes(measures_of(root)[0])
    for t in n[:3]:
        assert note_value(t) == (160, "eighth", 0)
        assert t.findtext("./time-modification/actual-notes") == "3"
        assert t.findtext("./time-modification/normal-notes") == "2"
    assert n[0].find("./notations/tuplet").get("type") == "start"
    assert n[1].find("./notations/tuplet") is None
    assert n[2].find("./notations/tuplet").get("type") == "stop"
    assert n[3].find("time-modification") is None
    assert bar_divisions(measures_of(root)[0]) == 1920


def test_tie_has_matching_stop(clvz):
    # 小節をまたぐタイ: 開始の音に tie start、次の音に tie stop が要る
    root = convert(clvz, [measure(notes=[note(WHOLE, "pitch", 0, extra="<tie />")]),
                          measure(notes=[note(WHOLE, "pitch", 0)]),
                          measure(notes=[note(WHOLE, "pitch", 0)])])
    n1, n2, n3 = [sounding_notes(m)[0] for m in measures_of(root)]
    assert [t.get("type") for t in n1.findall("tie")] == ["start"]
    assert [t.get("type") for t in n2.findall("tie")] == ["stop"]
    assert n3.findall("tie") == []
    assert [t.get("type") for t in n1.findall("./notations/tied")] == ["start"]
    assert [t.get("type") for t in n2.findall("./notations/tied")] == ["stop"]


def test_tie_chain_within_measure(clvz):
    root = convert(clvz, [measure(notes=[note(480, "pitch", 0, extra="<tie />"),
                                         note(QUARTER, "pitch", 0, extra="<tie />"),
                                         note(QUARTER, "pitch", 0)])])
    n = sounding_notes(measures_of(root)[0])
    assert [sorted(t.get("type") for t in x.findall("tie")) for x in n] == \
        [["start"], ["start", "stop"], ["stop"]]


def test_empty_measure_is_hidden_full_rest(clvz):
    root = convert(clvz, [measure(time_sig="time-3_4")])
    (n,) = measures_of(root)[0].findall("note")
    assert n.get("print-object") == "no"
    assert n.find("rest").get("measure") == "yes"
    assert int(n.findtext("duration")) == 1440


# ---------------------------------------------------------------------------
# 3. コード記号
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("step2,kind", [
    ("none", "major"), ("m", "minor"), ("7", "dominant"), ("maj7", "major-seventh"),
    ("m7", "minor-seventh"), ("m6", "minor-sixth"), ("m7-5", "half-diminished"),
    ("dim", "diminished"), ("dim7", "diminished-seventh"), ("mmaj7", "minor-major-seventh"),
    ("aug", "augmented"), ("6", "major-sixth"), ("sus4", "suspended-fourth"),
])
def test_chord_kinds(clvz, step2, kind):
    root = convert(clvz, [measure(chords=[chord("D", step2)])])
    (h,) = root.iter("harmony")
    assert harmony_of(h)["kind"] == kind
    assert h.find("kind").get("use-symbols") == "yes"


def test_chord_roots_and_bass(clvz):
    root = convert(clvz, [measure(chords=[chord("F#", "m7", base="E")]),
                          measure(chords=[chord("Bb", "maj7", base="D")]),
                          measure(chords=[chord("Eb", "7", base="Bb")])])
    hs = [harmony_of(h) for h in root.iter("harmony")]
    assert [(h["root"], h["kind"], h["bass"]) for h in hs] == [
        ("F#", "minor-seventh", "E"), ("Bb", "major-seventh", "D"), ("Eb", "dominant", "Bb")]


@pytest.mark.parametrize("step3,degrees", [
    ("9", [(9, 0, "add")]),
    ("-9", [(9, -1, "add")]),
    ("+11", [(11, 1, "add")]),
    ("13", [(13, 0, "add")]),
    ("-5", [(5, -1, "alter")]),
    ("9(13)", [(9, 0, "add"), (13, 0, "add")]),
    ("+5(+9)", [(5, 1, "alter"), (9, 1, "add")]),
    ("add9", [(9, 0, "add")]),
    ("omit3", [(3, 0, "subtract")]),
])
def test_chord_tensions(clvz, step3, degrees):
    root = convert(clvz, [measure(chords=[chord("G", "7", step3)])])
    (h,) = root.iter("harmony")
    assert harmony_of(h)["degrees"] == degrees


def test_unknown_chord_quality_becomes_other(clvz):
    root = convert(clvz, [measure(chords=[chord("C", "xyz")])])
    (h,) = root.iter("harmony")
    assert h.findtext("kind") == "other"


def test_no_chord_value_is_skipped(clvz):
    root = convert(clvz, [measure(chords=[chord("none", "none")])])
    assert list(root.iter("harmony")) == []


def test_two_chords_without_rhythm_split_bar(clvz):
    # リズム無しの小節に 1・3 拍目のコード → 2 分の隠し休符 2 個、コードは各休符の前
    root = convert(clvz, [measure(chords=[chord("F", timing=480), chord("C", timing=0)])])
    m = measures_of(root)[0]
    seq = [(c.tag, c.findtext("./root/root-step")) for c in m if c.tag in ("harmony", "note")]
    assert seq == [("harmony", "C"), ("note", None), ("harmony", "F"), ("note", None)]
    rests = m.findall("note")
    assert [note_value(n) for n in rests] == [(960, "half", 0), (960, "half", 0)]
    assert all(n.get("print-object") == "no" for n in rests)


@pytest.mark.parametrize("offset,first,second", [
    (240, (480, "quarter", 0), (1440, "half", 1)),
    (720, (1440, "half", 1), (480, "quarter", 0)),
])
def test_chord_on_off_beat_hidden_rest_values(clvz, offset, first, second):
    root = convert(clvz, [measure(chords=[chord("C"), chord("G", timing=offset)])])
    m = measures_of(root)[0]
    assert [note_value(n) for n in m.findall("note")] == [first, second]
    assert bar_divisions(m) == 1920


def test_chords_interleaved_with_rhythm(clvz):
    root = convert(clvz, [measure(chords=[chord("C"), chord("A", "m7", timing=480)],
                                  notes=[note(QUARTER)] * 4)])
    m = measures_of(root)[0]
    seq = [c.tag for c in m if c.tag in ("harmony", "note")]
    assert seq == ["harmony", "note", "note", "harmony", "note", "note"]


def test_chord_after_short_rhythm_fills_with_slashes(clvz):
    # リズムが小節の前半だけ、後半にコード → 後半はスラッシュで埋める
    root = convert(clvz, [measure(chords=[chord("C"), chord("G", timing=480)],
                                  notes=[note(480, "pitch", 0)])])
    m = measures_of(root)[0]
    notes = sounding_notes(m)
    assert len(notes) == 2
    assert notes[1].findtext("notehead") == "slash"
    assert bar_divisions(m) == 1920
    hs = list(m.iter("harmony"))
    assert [h.findtext("./root/root-step") for h in hs] == ["C", "G"]


# ---------------------------------------------------------------------------
# 4. 調・拍子・音部記号
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("key,fifths", [
    ("key-sharp0", 0), ("key-sharp1", 1), ("key-sharp4", 4), ("key-sharp7", 7),
    ("key-flat1", -1), ("key-flat3", -3), ("key-flat7", -7),
])
def test_key_signatures(clvz, key, fifths):
    root = convert(clvz, [measure(key=key, chords=[chord("C")])])
    assert measures_of(root)[0].findtext("./attributes/key/fifths") == str(fifths)


@pytest.mark.parametrize("key,level,expected", [
    ("key-sharp1", 4, ("F", 1, 5)),      # ト長調の F → F#
    ("key-sharp1", 1, ("C", 0, 5)),      # C はそのまま
    ("key-sharp2", 1, ("C", 1, 5)),      # ニ長調の C → C#
    ("key-flat1", 0, ("B", -1, 4)),      # ヘ長調の B → Bb
    ("key-flat2", 3, ("E", -1, 5)),      # 変ロ長調の E → Eb
    ("key-flat2", -1, ("A", 0, 4)),      # A はそのまま
])
def test_key_applies_to_pitches(clvz, key, level, expected):
    root = convert(clvz, [measure(key=key, notes=[note(WHOLE, "pitch", level)])])
    assert pitch_of(sounding_notes(measures_of(root)[0])[0]) == expected


def test_key_carries_over_and_changes(clvz):
    root = convert(clvz, [measure(key="key-sharp1", notes=[note(WHOLE, "pitch", 4)]),
                          measure(notes=[note(WHOLE, "pitch", 4)]),
                          measure(key="key-sharp0", notes=[note(WHOLE, "pitch", 4)])])
    ms = measures_of(root)
    assert [pitch_of(sounding_notes(m)[0]) for m in ms] == [("F", 1, 5), ("F", 1, 5), ("F", 0, 5)]
    assert ms[1].find("./attributes/key") is None       # 変わらない小節には出さない
    assert ms[2].findtext("./attributes/key/fifths") == "0"


@pytest.mark.parametrize("time_sig,beats,beat_type,bar", [
    ("time-C", 4, 4, 1920), ("time-4_4", 4, 4, 1920), ("time-3_4", 3, 4, 1440),
    ("time-2_4", 2, 4, 960), ("time-6_8", 6, 8, 1440), ("time-5_4", 5, 4, 2400),
    ("time-2_2", 2, 2, 1920),
])
def test_time_signatures(clvz, time_sig, beats, beat_type, bar):
    root = convert(clvz, [measure(time_sig=time_sig, chords=[chord("C")]),
                          measure(chords=[chord("G")])])
    m1, m2 = measures_of(root)
    assert m1.findtext("./attributes/time/beats") == str(beats)
    assert m1.findtext("./attributes/time/beat-type") == str(beat_type)
    assert m2.find("./attributes/time") is None
    # 前の拍子が引き継がれ、隠し休符が小節を満たす
    assert bar_divisions(m1) == bar and bar_divisions(m2) == bar


def test_time_change_midway(clvz):
    root = convert(clvz, [measure(time_sig="time-C", chords=[chord("C")]),
                          measure(time_sig="time-3_4", chords=[chord("F")]),
                          measure(chords=[chord("G")])])
    assert [bar_divisions(m) for m in measures_of(root)] == [1920, 1440, 1440]


@pytest.mark.parametrize("clef,sign,line", [
    ("clef-g", "G", "2"), ("clefToon", "G", "2"), ("clef-f", "F", "4"), ("clefHeon", "F", "4"),
])
def test_clefs(clvz, clef, sign, line):
    root = convert(clvz, [measure(clef=clef, chords=[chord("C")])])
    m = measures_of(root)[0]
    assert m.findtext("./attributes/clef/sign") == sign
    assert m.findtext("./attributes/clef/line") == line


# ---------------------------------------------------------------------------
# 5. 小節線・繰り返し・カッコ（volta）
# ---------------------------------------------------------------------------

def barlines(m):
    return {b.get("location"): b for b in m.findall("barline")}


@pytest.mark.parametrize("clover,style", [
    ("double", "light-light"), ("great-double", "light-heavy"), ("transparent", "none"),
])
def test_right_barline_styles(clvz, clover, style):
    root = convert(clvz, [measure(right=clover, chords=[chord("C")])])
    bl = barlines(measures_of(root)[0])
    assert set(bl) == {"right"}
    assert bl["right"].findtext("bar-style") == style
    assert bl["right"].find("repeat") is None


def test_single_barline_emits_nothing(clvz):
    root = convert(clvz, [measure(chords=[chord("C")])])
    assert measures_of(root)[0].findall("barline") == []


def test_repeat_barlines(clvz):
    root = convert(clvz, [measure(left="repeat-forward", chords=[chord("C")]),
                          measure(chords=[chord("F")]),
                          measure(right="repeat-backward", chords=[chord("G")])])
    m1, m2, m3 = measures_of(root)
    l = barlines(m1)["left"]
    assert l.findtext("bar-style") == "heavy-light"
    assert l.find("repeat").get("direction") == "forward"
    assert m2.findall("barline") == []
    r = barlines(m3)["right"]
    assert r.findtext("bar-style") == "light-heavy"
    assert r.find("repeat").get("direction") == "backward"
    # 左小節線は小節の最初の音より前
    kids = list(m1)
    assert kids.index(l) < kids.index(m1.find("note"))


def test_volta_endings(clvz):
    v1b = '<volta type="volta-begin"><arbitrary-text>1</arbitrary-text></volta>'
    v1e = '<volta type="volta-end"><arbitrary-text>1</arbitrary-text></volta>'
    v2b = '<volta type="volta-begin"><arbitrary-text>2</arbitrary-text></volta>'
    root = convert(clvz, [measure(left="repeat-forward", chords=[chord("C")]),
                          measure(right="repeat-backward", chords=[chord("G")], symbols=v1b + v1e),
                          measure(chords=[chord("C")], symbols=v2b)])
    m1, m2, m3 = measures_of(root)
    left2, right2 = barlines(m2)["left"], barlines(m2)["right"]
    assert left2.find("ending").attrib == {"number": "1", "type": "start"}
    assert right2.find("ending").attrib == {"number": "1", "type": "stop"}
    assert right2.find("repeat").get("direction") == "backward"
    assert barlines(m3)["left"].find("ending").attrib == {"number": "2", "type": "start"}


# ---------------------------------------------------------------------------
# 6. 記号・テンポ・段組
# ---------------------------------------------------------------------------

def test_rehearsal_free_text_and_navigation(clvz):
    syms = (text_symbol("A") + text_symbol("to Coda", "free-text")
            + '<symbol type="fine" /><symbol type="crescendo" /><symbol type="push8" />')
    root = convert(clvz, [measure(chords=[chord("C")], symbols=syms)])
    m = measures_of(root)[0]
    assert [r.text for r in m.iter("rehearsal")] == ["A"]
    assert [w.text for w in m.iter("words")] == ["to Coda", "Fine", "cresc."]
    assert any(s.get("fine") == "yes" for s in m.iter("sound"))


def test_tempo_in_first_measure_only(clvz):
    sp = "<speed>132</speed>"
    root = convert(clvz, [measure(chords=[chord("C")], symbols=sp),
                          measure(chords=[chord("G")])])
    m1, m2 = measures_of(root)
    assert m1.findtext(".//metronome/per-minute") == "132"
    assert m1.findtext(".//metronome/beat-unit") == "quarter"
    assert m1.find(".//sound").get("tempo") == "132"
    assert m2.find(".//metronome") is None


def test_system_breaks_from_lines(clvz):
    root = convert(clvz, [measure(chords=[chord("C")])] * 7, lines=(4, 2, 1))
    breaks = [m.get("number") for m in measures_of(root)
              if m.find("print") is not None and m.find("print").get("new-system") == "yes"]
    assert breaks == ["5", "7"]


# ---------------------------------------------------------------------------
# 7. 小節数・小節の長さ
# ---------------------------------------------------------------------------

def test_measure_count_and_bar_lengths_mixed(clvz):
    ms = [measure(time_sig="time-C", key="key-flat1", clef="clef-g",
                  chords=[chord("F", "maj7")], notes=[note(QUARTER)] * 4),
          measure(chords=[chord("G", "m7"), chord("C", "7", timing=480)]),
          measure(chords=[chord("F")], notes=[note(360, "pitch", 0), note(120, "pitch", 1),
                                              note(480, "rest")]),
          measure(time_sig="time-3_4", chords=[chord("D", "m")]),
          measure()]
    root = convert(clvz, ms)
    out = measures_of(root)
    assert len(out) == 5
    assert [bar_divisions(m) for m in out] == [1920, 1920, 1920, 1440, 1440]


def test_cli_single_file(clvz, tmp_path):
    src = clvz(clover_doc([measure(chords=[chord("C")])] * 2))
    dst = tmp_path / "out.musicxml"
    assert cli_main([str(src), "-o", str(dst)]) == 0
    root = ET.fromstring(dst.read_bytes())
    assert len(measures_of(root)) == 2


def test_cli_batch_reports_broken_and_converts_rest(clvz, tmp_path, capsys):
    src_dir = tmp_path / "in"
    src_dir.mkdir()
    (src_dir / "good.clvz").write_bytes(clvz(clover_doc([measure(chords=[chord("C")])])).read_bytes())
    (src_dir / "bad.clvz").write_bytes(b"not gzip")
    out_dir = tmp_path / "out"
    assert cli_main([str(src_dir), "-o", str(out_dir), "--batch"]) == 0
    err = capsys.readouterr().err
    assert "ERR bad.clvz" in err and "OK  good.clvz" in err
    assert (out_dir / "good.musicxml").exists()
    assert not (out_dir / "bad.musicxml").exists()


# ---------------------------------------------------------------------------
# 8. 境界: 空・壊れた入力・長さの不一致・極端に長い曲
# ---------------------------------------------------------------------------

def test_zero_byte_file_raises_parse_error(tmp_path):
    p = tmp_path / "empty.clvz"
    p.write_bytes(b"")
    with pytest.raises(ET.ParseError):
        parse_score(p)


def test_gzip_of_empty_raises_parse_error(clvz):
    with pytest.raises(ET.ParseError):
        parse_score(clvz(b""))


def test_not_gzip_raises_bad_gzip(clvz):
    with pytest.raises(gzip.BadGzipFile):
        parse_score(clvz("<clover/>", gz=False))


def test_truncated_xml_raises_parse_error(clvz):
    doc = clover_doc([measure(chords=[chord("C")])])
    with pytest.raises(ET.ParseError):
        parse_score(clvz(doc[: len(doc) // 2]))


def test_truncated_gzip_raises(clvz, tmp_path):
    full = clvz(clover_doc([measure(chords=[chord("C")])] * 20)).read_bytes()
    p = tmp_path / "cut.clvz"
    p.write_bytes(full[: len(full) // 2])
    with pytest.raises(EOFError):
        parse_score(p)


def test_external_entity_is_rejected(clvz):
    doc = ('<?xml version="1.0"?><!DOCTYPE clover [<!ENTITY x SYSTEM "file:///etc/hostname">]>'
           '<clover><measure-sets/></clover>')
    with pytest.raises(Exception) as ei:
        parse_score(clvz(doc))
    assert "defusedxml" in type(ei.value).__module__


def test_missing_file_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        parse_score(tmp_path / "nothing.clvz")


@pytest.mark.parametrize("bad,exc", [
    ('<key type="key-xyz" />', ValueError),
    ('<time type="time-waltz" />', ValueError),
    ('<clef type="clef-x" />', ValueError),
])
def test_unknown_attribute_values_raise_value_error(clvz, bad, exc):
    doc = clover_doc([f'<measure-set><part1>{bad}</part1></measure-set>'])
    with pytest.raises(exc):
        parse_score(clvz(doc))


@pytest.mark.parametrize("frag", [
    '<harmonies><harmony duration="abc"><notes><slash /></notes></harmony></harmonies>',
    '<harmonies><harmony duration="960"><notes><pitch level="x" /></notes></harmony></harmonies>',
    '<chords><chord timing="abc"><chord-value step1="C" step2="none" /></chord></chords>',
])
def test_non_numeric_values_raise_value_error(clvz, frag):
    doc = clover_doc([f'<measure-set><part1>{frag}</part1></measure-set>'])
    with pytest.raises(ValueError):
        parse_score(clvz(doc))


def test_measure_set_without_part1_raises(clvz):
    # 現状は AttributeError（分かりにくい）。例外が出て止まることだけを確かめる。
    doc = clover_doc(["<measure-set />"])
    with pytest.raises(Exception):
        parse_score(clvz(doc))


def test_unknown_barline_falls_back_to_regular(clvz):
    root = convert(clvz, [measure(right="wavy", chords=[chord("C")])])
    assert measures_of(root)[0].findall("barline") == []


def test_no_measures_parses_to_empty_score(clvz):
    score = parse_score(clvz(clover_doc([])))
    assert score.parts[0].measures == []
    # MusicXML としての扱いは未決（下の報告を参照）。ここでは例外が出ないことだけを見る。
    build_musicxml(score)


def test_overfull_measure_keeps_all_events(clvz):
    # 4/4 に 5 拍: 例外にはならず、5 拍ぶんそのまま出る
    root = convert(clvz, [measure(time_sig="time-C", notes=[note(QUARTER)] * 5)])
    m = measures_of(root)[0]
    assert len(sounding_notes(m)) == 5
    assert bar_divisions(m) == 2400


def test_underfull_measure_without_chords_keeps_length(clvz):
    # 4/4 に 3 拍、コード無し: 足りない分は埋めず 3 拍で出る
    root = convert(clvz, [measure(time_sig="time-C", notes=[note(QUARTER)] * 3)])
    assert bar_divisions(measures_of(root)[0]) == 1440


def test_very_long_score(clvz):
    n = 3000
    bar = measure(chords=[chord("C", "maj7"), chord("A", "m7", timing=480)],
                  notes=[note(QUARTER)] * 4)
    doc = clover_doc([measure(time_sig="time-C", key="key-sharp0", clef="clef-g",
                              chords=[chord("C")], notes=[note(QUARTER)] * 4)] + [bar] * (n - 1),
                     lines=[4] * (n // 4))
    t0 = time.perf_counter()
    root = to_xml(clvz(doc))
    elapsed = time.perf_counter() - t0
    ms = measures_of(root)
    assert len(ms) == n
    assert ms[-1].get("number") == str(n)
    assert all(bar_divisions(m) == 1920 for m in ms)
    assert len(list(root.iter("harmony"))) == 1 + 2 * (n - 1)
    assert elapsed < 30


# ---------------------------------------------------------------------------
# 9. 既存の合成サンプル（tests/fixtures/demo.clvz）の要点
# ---------------------------------------------------------------------------

def test_demo_fixture_structure():
    from pathlib import Path
    root = to_xml(Path(__file__).parent / "fixtures" / "demo.clvz")
    ms = measures_of(root)
    assert len(ms) == 8
    assert root.findtext("./work/work-title") == "Demo Song (sample)"
    assert all(bar_divisions(m) == 1920 for m in ms)
    assert [r.text for r in root.iter("rehearsal")] == ["A", "B"]
    breaks = [m.get("number") for m in ms if m.find("print") is not None]
    assert breaks == ["5"]
