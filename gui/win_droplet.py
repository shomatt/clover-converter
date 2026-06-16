"""Windows drag-and-drop entry for the Clover ⇄ MusicXML converter.

On Windows, dropping files onto an .exe passes their paths as argv, so this
script IS the droplet. It converts each dropped .clvz / .musicxml and shows a
single message box with the result (no console window). Built with PyInstaller
--windowed into "Clover変換.exe" (see .github/workflows/build-apps.yml).
"""
from __future__ import annotations
import sys
from pathlib import Path

# Reuse the shared, cross-platform conversion core.
_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
from clover_batch import gather, convert_path  # noqa: E402


def _notify(title: str, text: str) -> None:
    try:
        import ctypes
        # MB_OK | MB_ICONINFORMATION
        ctypes.windll.user32.MessageBoxW(0, text, title, 0x00000040)
    except Exception:
        print(f"{title}: {text}")


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        _notify("Clover変換",
                "変換する .clvz / .musicxml ファイルを、このアイコンに"
                "ドラッグ&ドロップしてください。")
        return 0
    files = gather(argv)
    if not files:
        _notify("Clover変換", "変換対象（.clvz / .musicxml）が見つかりません。")
        return 1
    ok = err = 0
    errors = []
    for f in files:
        try:
            convert_path(f, None)   # output next to the source
            ok += 1
        except Exception as e:      # noqa: BLE001
            err += 1
            errors.append(f"× {f.name}: {e}")
    msg = f"成功 {ok} 件 / 失敗 {err} 件"
    if errors:
        msg += "\n\n" + "\n".join(errors[:10])
    _notify("Clover変換", msg)
    return 0 if err == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
