from __future__ import annotations
import argparse, sys
from pathlib import Path
from clover2xml.mxl_reader import parse_musicxml
from clover2xml.clover_writer import write_clover

_EXTS = ("*.musicxml", "*.xml", "*.mxl")


def convert_file(src, dst) -> None:
    score = parse_musicxml(src)
    write_clover(score, dst)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="xml2clover",
                                 description="Convert MusicXML to Clover .clvz")
    ap.add_argument("input", help="MusicXML file or directory (with --batch)")
    ap.add_argument("-o", "--output", required=True, help="output file or directory")
    ap.add_argument("--batch", action="store_true",
                    help="convert all MusicXML files in a directory")
    args = ap.parse_args(argv)

    if args.batch:
        srcdir, outdir = Path(args.input), Path(args.output)
        outdir.mkdir(parents=True, exist_ok=True)
        files = sorted({f for ext in _EXTS for f in srcdir.glob(ext)})
        for f in files:
            try:
                convert_file(f, outdir / (f.stem + ".clvz"))
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
