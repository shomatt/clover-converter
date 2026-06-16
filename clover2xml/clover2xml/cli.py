from __future__ import annotations
import argparse, sys
from pathlib import Path
from clover2xml.reader import parse_score
from clover2xml.writer import build_musicxml

def convert_file(src, dst) -> None:
    score = parse_score(src)
    xml = build_musicxml(score)
    Path(dst).write_text(xml, encoding="utf-8")

def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="clover2xml",
                                 description="Convert Clover .clvz to MusicXML")
    ap.add_argument("input", help=".clvz file or directory (with --batch)")
    ap.add_argument("-o", "--output", required=True, help="output file or directory")
    ap.add_argument("--batch", action="store_true", help="convert all .clvz in a directory")
    args = ap.parse_args(argv)

    if args.batch:
        srcdir, outdir = Path(args.input), Path(args.output)
        outdir.mkdir(parents=True, exist_ok=True)
        files = sorted(srcdir.glob("*.clvz"))
        for f in files:
            try:
                convert_file(f, outdir / (f.stem + ".musicxml"))
                print(f"OK  {f.name}", file=sys.stderr)
            except Exception as e:
                print(f"ERR {f.name}: {e}", file=sys.stderr)
        print(f"done: {len(files)} files", file=sys.stderr)
    else:
        convert_file(args.input, args.output)
        print(f"OK  {args.input} -> {args.output}", file=sys.stderr)
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
