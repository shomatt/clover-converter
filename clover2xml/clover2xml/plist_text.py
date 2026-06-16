"""Generate the macOS NSKeyedArchiver base64 plist that Clover stores for text
(song title, rehearsal marks). Clover keeps BOTH this binary plist and a plain
<formatted-texts> fallback; we emit both. The plist encodes a single-run
NSAttributedString with an NSFont attribute, mirroring real Clover files."""
from __future__ import annotations
import base64
import plistlib


def make_text_plist(text: str, font_size: float = 20.0,
                    font_name: str = "LucidaGrande") -> str:
    """Return the base64 of an NSKeyedArchiver-encoded NSAttributedString."""
    U = plistlib.UID
    objects = [
        "$null",
        {"NSString": U(2), "$class": U(9), "NSAttributes": U(3)},
        text,
        {"NS.keys": [U(4)], "NS.objects": [U(5)], "$class": U(8)},
        "NSFont",
        {"NSSize": float(font_size), "NSfFlags": 16, "NSName": U(6), "$class": U(7)},
        font_name,
        {"$classname": "NSFont", "$classes": ["NSFont", "NSObject"]},
        {"$classname": "NSDictionary", "$classes": ["NSDictionary", "NSObject"]},
        {"$classname": "NSAttributedString",
         "$classes": ["NSAttributedString", "NSObject"]},
    ]
    plist = {
        "$version": 100000,
        "$archiver": "NSKeyedArchiver",
        "$top": {"root": U(1)},
        "$objects": objects,
    }
    data = plistlib.dumps(plist, fmt=plistlib.FMT_BINARY)
    return base64.b64encode(data).decode("ascii")


def decode_text_plist(b64: str) -> str:
    """Inverse: pull the string out of such a plist (for tests/round-trip)."""
    pl = plistlib.loads(base64.b64decode(b64))
    objs = pl["$objects"]
    root_uid = pl["$top"]["root"]
    root = objs[root_uid.data if hasattr(root_uid, "data") else int(root_uid)]
    s_uid = root["NSString"]
    return objs[s_uid.data if hasattr(s_uid, "data") else int(s_uid)]
