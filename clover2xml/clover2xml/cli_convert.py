"""cloverconv — any-to-any converter CLI.

  cloverconv IN OUT          # direction inferred from extensions
  cloverconv --batch DIR -o OUTDIR --to mid

Supports .clvz / .musicxml / .xml / .mid / .midi in any combination.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path

from clover2xml.engine import convert_file, INPUT_EXTS


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="cloverconv", description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("input", help="入力ファイル、または --batch 時は入力フォルダ")
    ap.add_argument("-o", "--output", help="出力ファイル（--batch 時は出力フォルダ）")
    ap.add_argument("--batch", action="store_true", help="フォルダ内を一括変換")
    ap.add_argument("--to", choices=["clvz", "musicxml", "mid"],
                    help="--batch 時の出力形式")
    a = ap.parse_args(argv)

    if a.batch:
        if not a.to:
            ap.error("--batch には --to {clvz,musicxml,mid} が必要です")
        out_dir = Path(a.output) if a.output else Path(a.input)
        out_dir.mkdir(parents=True, exist_ok=True)
        ok = err = 0
        for f in sorted(Path(a.input).rglob("*")):
            if f.suffix.lower() in INPUT_EXTS:
                try:
                    convert_file(f, out_dir / (f.stem + "." + a.to))
                    ok += 1
                except Exception as e:  # noqa: BLE001
                    print(f"ERR {f.name}: {e}", file=sys.stderr)
                    err += 1
        print(f"成功 {ok} 件 / 失敗 {err} 件")
        return 0 if err == 0 else 1

    if not a.output:
        ap.error("出力先 -o/--output を指定してください")
    convert_file(a.input, a.output)
    print(f"{Path(a.input).name} → {Path(a.output).name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
