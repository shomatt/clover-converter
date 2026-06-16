"""Minimal Standard MIDI File (SMF) reader/writer — stdlib only.

Supports format 0/1 metrical-division files: note on/off, set-tempo, time
signature, key signature meta events. Enough to import a .mid into a chord
chart and to export a chart back to an audible .mid. No external dependency
(keeps the web wheel and the frozen app self-contained)."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class Note:
    start: int      # absolute ticks
    end: int        # absolute ticks
    pitch: int      # MIDI note number
    velocity: int = 80


@dataclass
class MidiData:
    division: int = 480                 # ticks per quarter note
    tempo: int = 500000                 # microseconds per quarter (=120 bpm)
    time_sig: tuple = (4, 4)
    key_fifths: int = 0
    notes: list = field(default_factory=list)   # list[Note]

    @property
    def bpm(self) -> int:
        return round(60_000_000 / self.tempo)


# ── variable-length quantity ──────────────────────────────────────────
def _read_vlq(data: bytes, i: int):
    val = 0
    while True:
        b = data[i]; i += 1
        val = (val << 7) | (b & 0x7F)
        if not (b & 0x80):
            return val, i


def _write_vlq(val: int) -> bytes:
    out = bytearray([val & 0x7F])
    val >>= 7
    while val:
        out.insert(0, (val & 0x7F) | 0x80)
        val >>= 7
    return bytes(out)


# ── reader ────────────────────────────────────────────────────────────
def read_smf(source) -> MidiData:
    """source: path or bytes. Returns MidiData with absolute-tick notes."""
    if isinstance(source, (bytes, bytearray)):
        data = bytes(source)
    else:
        with open(source, "rb") as f:
            data = f.read()

    if data[:4] != b"MThd":
        raise ValueError("有効な MIDI ファイルではありません（MThd ヘッダ無し）")
    division = int.from_bytes(data[12:14], "big")
    if division & 0x8000:
        raise ValueError("SMPTE タイムコード形式は未対応です")

    md = MidiData(division=division or 480)
    on = {}                              # (channel,pitch) -> (start, velocity)
    i = 14
    n = len(data)
    while i < n:
        if data[i:i + 4] != b"MTrk":
            break
        length = int.from_bytes(data[i + 4:i + 8], "big")
        j = i + 8
        end = j + length
        abs_t = 0
        status = 0
        while j < end:
            delta, j = _read_vlq(data, j)
            abs_t += delta
            b = data[j]
            if b & 0x80:
                status = b
                j += 1
            # else: running status, reuse previous status
            if status == 0xFF:           # meta
                mtype = data[j]; j += 1
                mlen, j = _read_vlq(data, j)
                payload = data[j:j + mlen]; j += mlen
                if mtype == 0x51 and mlen == 3:
                    md.tempo = int.from_bytes(payload, "big")
                elif mtype == 0x58 and mlen >= 2:
                    md.time_sig = (payload[0], 1 << payload[1])
                elif mtype == 0x59 and mlen >= 1:
                    md.key_fifths = payload[0] - 256 if payload[0] > 127 else payload[0]
            elif status in (0xF0, 0xF7):  # sysex
                slen, j = _read_vlq(data, j)
                j += slen
            else:
                cmd = status & 0xF0
                ch = status & 0x0F
                d1 = data[j]; j += 1
                if cmd in (0x80, 0x90, 0xA0, 0xB0, 0xE0):
                    d2 = data[j]; j += 1
                else:                     # 0xC0/0xD0 have a single data byte
                    d2 = 0
                if cmd == 0x90 and d2 > 0:
                    on[(ch, d1)] = (abs_t, d2)
                elif cmd == 0x80 or (cmd == 0x90 and d2 == 0):
                    key = (ch, d1)
                    if key in on:
                        start, vel = on.pop(key)
                        md.notes.append(Note(start, abs_t, d1, vel))
        i = end
    md.notes.sort(key=lambda nt: (nt.start, nt.pitch))
    return md


# ── writer ────────────────────────────────────────────────────────────
def write_smf(md: MidiData, path=None) -> bytes:
    """Serialize MidiData to a format-0 SMF. Writes to path if given; returns bytes."""
    track = bytearray()
    events = []  # (abs_tick, order, bytes)  order keeps offs before ons at same tick

    # tempo + time signature + key signature meta at t=0
    den_pow = (md.time_sig[1]).bit_length() - 1
    events.append((0, 0, b"\xFF\x51\x03" + md.tempo.to_bytes(3, "big")))
    events.append((0, 0, bytes([0xFF, 0x58, 0x04, md.time_sig[0], den_pow, 24, 8])))
    sf = md.key_fifths & 0xFF
    events.append((0, 0, bytes([0xFF, 0x59, 0x02, sf, 0])))

    for nt in md.notes:
        events.append((nt.start, 1, bytes([0x90, nt.pitch & 0x7F, nt.velocity & 0x7F])))
        events.append((nt.end, 0, bytes([0x80, nt.pitch & 0x7F, 0])))

    events.sort(key=lambda e: (e[0], e[1]))
    prev = 0
    for abs_t, _order, payload in events:
        track += _write_vlq(abs_t - prev)
        track += payload
        prev = abs_t
    track += b"\x00\xFF\x2F\x00"          # end of track

    header = b"MThd" + (6).to_bytes(4, "big") + (0).to_bytes(2, "big") \
        + (1).to_bytes(2, "big") + md.division.to_bytes(2, "big")
    chunk = b"MTrk" + len(track).to_bytes(4, "big") + bytes(track)
    out = header + chunk
    if path is not None:
        with open(path, "wb") as f:
            f.write(out)
    return out
