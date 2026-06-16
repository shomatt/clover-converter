# Clover ⇄ MusicXML 変換ツール — ビルド用リポジトリ

このリポジトリは、ネイティブアプリ（Windows `.exe` / macOS universal `.app`）を
**GitHub Actions で自動ビルド**するためのソースと CI を含みます。
**実楽曲のデータは一切含まれていません**（テストは合成サンプルのみ）。

## .exe / .app をビルドする手順

1. このリポジトリを自分の GitHub にpush（公開・非公開どちらでも可）
2. **Actions** タブ →「Build native apps」→ **Run workflow**
   （または `git tag v1.0 && git push --tags`）
3. 実行完了後、各 **Artifacts** をダウンロード:
   - `Clover変換-Windows` … `Clover変換.exe`
   - `Clover変換-macOS-universal` … `Clover変換-mac.zip`（Intel + Apple Silicon）

## 使い方（ビルド後）

`.clvz` / `.musicxml` をアプリのアイコンにドラッグ&ドロップ → 元と同じ場所に変換出力。
- Windows: 初回は SmartScreen →「詳細情報」→「実行」
- macOS: 初回は右クリック →「開く」

## 中身

| パス | 役割 |
|---|---|
| `clover2xml/` | 変換コア（`.clvz ⇄ MusicXML`）＋合成データの公開テスト |
| `clover-midi/` | MIDI 入力 →`.clvz`（CLI） |
| `gui/` | ドロップレットのエントリ（`win_droplet.py` / `clover_batch.py` / `build_app.sh` / `droplet.applescript`） |
| `.github/workflows/build-apps.yml` | Win/Mac ビルド CI |

## プライバシー

変換はルールベース（機械学習ではない）。コアに楽曲由来データ（コーパス等）は無く、
このリポジトリにも実楽曲は含めていません。
