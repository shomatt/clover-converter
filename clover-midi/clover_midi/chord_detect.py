"""Chord detection has moved into the clover2xml package (so MIDI import/export
work without rtmidi). This module re-exports it for backward compatibility."""
from clover2xml.chord_detect import (  # noqa: F401
    NAMES,
    detect_chord,
    detect_chord_sym,
    chord_to_notes,
)
