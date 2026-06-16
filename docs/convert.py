"""In-browser conversion bridge (runs inside Pyodide).

All conversion happens client-side — file bytes are written only to Pyodide's
in-memory filesystem, never uploaded. Rule-based; embeds no song data.
Supports Clover (.clvz), MusicXML (.musicxml/.xml) and MIDI (.mid) in any
direction via the clover2xml engine.
"""
import io
import zipfile
from pathlib import Path

from clover2xml.engine import convert_file

_TMP = Path("/tmp/clvconv")
_TMP.mkdir(parents=True, exist_ok=True)

# target key (from the UI) → output extension
TARGET_EXT = {"musicxml": ".musicxml", "clvz": ".clvz", "mid": ".mid"}


def convert(filename, data, target):
    """filename: original name (for its extension). data: bytes or str.
    target: 'musicxml' | 'clvz' | 'mid'. Returns str (musicxml) or bytes."""
    src_ext = Path(filename).suffix.lower() or ".clvz"
    out_ext = TARGET_EXT[target]
    src = _TMP / ("in" + src_ext)
    if isinstance(data, str):
        src.write_text(data, encoding="utf-8")
    else:
        src.write_bytes(bytes(data))
    out = _TMP / ("out" + out_ext)
    convert_file(src, out)
    if out_ext == ".musicxml":
        return out.read_text(encoding="utf-8")
    return out.read_bytes()


def make_zip(entries):
    """entries: list of (filename, bytes_or_str) -> zip bytes."""
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for name, payload in entries:
            if isinstance(payload, str):
                payload = payload.encode("utf-8")
            zf.writestr(name, bytes(payload))
    return buf.getvalue()
