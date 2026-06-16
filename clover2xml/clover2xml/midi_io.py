"""MIDI file ⇄ Score.

Import: read a .mid, detect the chord sounding at each bar, and build a
chord chart (one chord per measure — matching the master-chart philosophy).
Export: render a Score's chords as block chords into an audible .mid.
"""
from __future__ import annotations
import math

from clover2xml.model import Score, Part, Measure
from clover2xml.smf import MidiData, Note, read_smf, write_smf
from clover2xml.chord_detect import detect_chord_sym, chord_to_notes


def _ticks_per_measure(division: int, time_sig) -> int:
    num, den = time_sig
    return int(division * 4 * num / den)


def midi_to_score(source, title: str = "") -> Score:
    """Import a .mid (path or bytes) into a chord-chart Score."""
    md = read_smf(source)
    tpm = _ticks_per_measure(md.division, md.time_sig) or md.division * 4
    beat = max(1, int(md.division * 4 / md.time_sig[1]))

    last = max((n.end for n in md.notes), default=0)
    n_measures = max(1, math.ceil(last / tpm))

    measures = []
    for m in range(n_measures):
        t0 = m * tpm
        # notes sounding at the downbeat; fall back to onsets in beat 1
        active = [n.pitch for n in md.notes if n.start <= t0 < n.end]
        if len(active) < 3:
            onset = [n.pitch for n in md.notes if t0 <= n.start < t0 + beat]
            if len(onset) >= len(active):
                active = onset
        meas = Measure(
            clef="G" if m == 0 else None,
            key_fifths=md.key_fifths if m == 0 else None,
            time=md.time_sig if m == 0 else None,
        )
        if len(active) >= 3:
            sym = detect_chord_sym(sorted(active))
            if sym is not None:
                sym.offset = 0.0
                meas.chords.append(sym)
        measures.append(meas)

    return Score(title=title, tempo=md.bpm, parts=[Part(measures=measures)])


def score_to_midi(score: Score, path=None, division: int = 480) -> bytes:
    """Export a Score's chords as block chords (one per measure) to a .mid."""
    time_sig = (4, 4)
    fifths = 0
    for m in (score.parts[0].measures if score.parts else []):
        if m.time:
            time_sig = m.time
        if m.key_fifths is not None:
            fifths = m.key_fifths
        if m.time or m.key_fifths is not None:
            break

    tpm = _ticks_per_measure(division, time_sig)
    md = MidiData(division=division, time_sig=time_sig, key_fifths=fifths,
                  tempo=int(60_000_000 / (score.tempo or 120)))

    measures = score.parts[0].measures if score.parts else []
    for i, meas in enumerate(measures):
        t0 = i * tpm
        if not meas.chords:
            continue
        # split the bar evenly among its chords (usually one)
        seg = tpm // len(meas.chords)
        for k, sym in enumerate(meas.chords):
            start = t0 + k * seg
            end = start + seg
            for pitch in chord_to_notes(sym):
                md.notes.append(Note(start, end, pitch, velocity=72))

    return write_smf(md, path)
