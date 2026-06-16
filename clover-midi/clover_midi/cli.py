"""midi2clover — play chords on a MIDI keyboard, get a Clover .clvz.

Listens to a MIDI input port, detects each chord you play (captured when you
release the keys), accumulates the progression, and on Ctrl+C writes a .clvz
you can open in Clover."""
from __future__ import annotations
import argparse
import sys
import time

from clover_midi.capture import ChordCapturer, feed_midi, progression_to_score

NAMES = ["C", "C#", "D", "D#", "E", "F", "F#", "G", "G#", "A", "A#", "B"]


def _label(det):
    s1, s2, s3, base = det
    q = "" if s2 == "none" else ("△7" if s2 == "maj7" else "-" + s2[1:] if s2.startswith("m") and s2 != "maj7" else s2)
    t = "" if s3 == "none" else f"({s3})"
    b = "" if base == "none" else f"/{base}"
    return f"{s1}{q}{t}{b}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="midi2clover", description=__doc__)
    ap.add_argument("-o", "--output", help="output .clvz path (required unless --list)")
    ap.add_argument("--port", type=int, default=None, help="MIDI input port index")
    ap.add_argument("--title", default="MIDI Input")
    ap.add_argument("--key", type=int, default=0, help="key signature fifths (+sharps/-flats)")
    ap.add_argument("--per-measure", type=int, default=1, help="chords per bar")
    ap.add_argument("--list", action="store_true", help="list MIDI ports and exit")
    a = ap.parse_args(argv)

    import rtmidi
    midiin = rtmidi.MidiIn()
    ports = midiin.get_ports()
    if a.list:
        for i, p in enumerate(ports):
            print(f"[{i}] {p}")
        return 0
    if not ports:
        print("MIDI入力ポートが見つかりません。MIDIキーボードを接続してください。", file=sys.stderr)
        return 1
    if not a.output:
        ap.error("-o/--output is required (unless --list)")

    idx = a.port if a.port is not None else 0
    cap = ChordCapturer()
    print(f"MIDIポート [{idx}] {ports[idx]} — コードを弾いてください（離すと捕捉）。Ctrl+C で保存終了。",
          file=sys.stderr)

    def cb(event, data=None):
        msg, _dt = event
        det = feed_midi(cap, msg)
        if det:
            print(f"  捕捉 #{len(cap.chords)}: {_label(det)}", file=sys.stderr)

    midiin.open_port(idx)
    midiin.set_callback(cb)
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        pass
    finally:
        midiin.close_port()

    score = progression_to_score(cap.chords, title=a.title, key_fifths=a.key,
                                 per_measure=a.per_measure)
    from clover2xml.clover_writer import write_clover
    write_clover(score, a.output)
    print(f"\n保存: {a.output}  ({len(cap.chords)}コード) — Clover で開いてください。",
          file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
