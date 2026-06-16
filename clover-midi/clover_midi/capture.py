"""Turn a stream of MIDI note-on/off events into a sequence of detected chords,
and assemble them into a Clover Score. A chord is captured when all currently
held keys are released — the largest simultaneously-held set during that press
is the chord."""
from __future__ import annotations

from clover_midi.chord_detect import detect_chord
from clover2xml.model import Score, Part, Measure
from clover2xml.mappings.chords import chord_value_to_sym


class ChordCapturer:
    def __init__(self, min_notes: int = 3):
        self.min_notes = min_notes
        self._held: set[int] = set()
        self._max: set[int] = set()
        self.chords: list[tuple] = []   # list of (step1, step2, step3, base)

    def note_on(self, pitch: int):
        self._held.add(pitch)
        if len(self._held) > len(self._max):
            self._max = set(self._held)

    def note_off(self, pitch: int):
        self._held.discard(pitch)
        if not self._held:               # full release → capture
            if len(self._max) >= self.min_notes:
                det = detect_chord(sorted(self._max))
                if det:
                    self.chords.append(det)
            self._max = set()
            return self.chords[-1] if self.chords else None
        return None


def feed_midi(capturer, message):
    """Process a raw MIDI message [status, data1, data2]. note-on (vel>0) →
    note_on; note-off / note-on(vel 0) → note_off. Returns a detected chord
    tuple if a chord was just captured (on full release), else None."""
    if len(message) < 3:
        return None
    cmd = message[0] & 0xF0
    if cmd == 0x90 and message[2] > 0:
        capturer.note_on(message[1])
    elif cmd == 0x80 or (cmd == 0x90 and message[2] == 0):
        return capturer.note_off(message[1])
    return None


def progression_to_score(chords, title="MIDI Input", key_fifths=0,
                         tempo=120, per_measure=1) -> Score:
    """Build a Score with the detected chords, `per_measure` chords per bar."""
    measures = []
    for i in range(0, max(len(chords), 1), per_measure):
        chunk = chords[i:i + per_measure]
        m = Measure(
            clef="G" if i == 0 else None,
            key_fifths=key_fifths if i == 0 else None,
            time=(4, 4) if i == 0 else None,
        )
        step = 960 // max(per_measure, 1)
        for j, ch in enumerate(chunk):
            sym = chord_value_to_sym(*ch)
            if sym is not None:
                sym.offset = j * step
                m.chords.append(sym)
        measures.append(m)
    return Score(title=title, tempo=tempo, parts=[Part(measures=measures)])
