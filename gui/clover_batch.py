"""clover-batch — headless batch converter (no GUI / no Tk).

Takes file and/or folder paths as arguments and converts each between Clover
.clvz, MusicXML and MIDI (direction by extension), writing outputs next to the
source (or into --out DIR). Prints a one-line summary so the calling droplet
can show it in a notification.

  clover-batch [--out DIR] PATH [PATH ...]

Default targets (drag-and-drop):
  .clvz            -> .musicxml
  .musicxml / .xml -> .clvz
  .mid  / .midi    -> .clvz      (MIDI import)
MIDI export (.mid) and any other combination: use the web tool or `cloverconv`.
"""
from __future__ import annotations
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
for p in (_ROOT / "clover2xml",):
    if p.exists() and str(p) not in sys.path:
        sys.path.insert(0, str(p))

from clover2xml.engine import convert_file, INPUT_EXTS

# default output format per input extension (drag-and-drop convenience)
_TARGET = {
    ".clvz": ".musicxml",
    ".musicxml": ".clvz",
    ".xml": ".clvz",
    ".mid": ".clvz",
    ".midi": ".clvz",
}


def convert_path(src: Path, out_dir: Path | None) -> Path:
    src = Path(src)
    tgt = _TARGET.get(src.suffix.lower())
    if tgt is None:
        raise ValueError(f"未対応の拡張子: {src.suffix}")
    dst_dir = Path(out_dir) if out_dir else src.parent
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = dst_dir / (src.stem + tgt)
    convert_file(src, dst)
    return dst


def gather(paths) -> list[Path]:
    files: list[Path] = []
    for p in paths:
        p = Path(p)
        if p.is_dir():
            for f in sorted(p.rglob("*")):
                if f.suffix.lower() in INPUT_EXTS:
                    files.append(f)
        elif p.suffix.lower() in INPUT_EXTS:
            files.append(p)
    return files


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    out_dir = None
    if argv and argv[0] == "--out":
        out_dir = Path(argv[1])
        argv = argv[2:]
    if not argv:
        print("使い方: clover-batch [--out DIR] <ファイル/フォルダ...>", file=sys.stderr)
        return 2
    files = gather(argv)
    if not files:
        print("変換対象（.clvz / .musicxml / .mid）が見つかりません。")
        return 1
    ok = err = 0
    for f in files:
        try:
            dst = convert_path(f, out_dir)
            print(f"OK  {f.name} -> {dst.name}", file=sys.stderr)
            ok += 1
        except Exception as e:  # noqa: BLE001
            print(f"ERR {f.name}: {e}", file=sys.stderr)
            err += 1
    print(f"成功 {ok} 件 / 失敗 {err} 件")
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
