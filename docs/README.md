# Clover ⇄ MusicXML ⇄ MIDI 変換ツール（Web版）

Clover Chord Systems の `.clvz`、MusicXML、**MIDI（.mid）**を **ブラウザ内で相互変換**するツールです。
入力は拡張子で自動判定し、画面上部の「変換先」で出力形式（MusicXML / Clover / MIDI）を選びます。
**MIDI 取込**（.mid → コード譜）と **MIDI 出力**（譜面 → .mid）に対応。

## プライバシー設計

- **ファイルはアップロードされません。** 変換は Pyodide（ブラウザ内 Python）で実行され、ファイルのバイト列はブラウザのメモリ上だけで処理されます。
- **学習データはありません。** 変換は機械学習ではなく**ルールベース（決定的な変換規則）**です。同梱する `clover2xml` ホイールにはコア変換コードと合成サンプルのみが含まれ、**実楽曲のデータは一切入っていません**（`dist/build_web.sh` のプライバシーゲートで毎回検査）。

## ローカルで動かす

```bash
cd web
python3 -m http.server 8731
# ブラウザで http://localhost:8731/ を開く
```

## 配布用バンドルを作る

```bash
bash dist/build_web.sh
# → dist/out/clover-web/      (静的ホスティングにそのまま置ける)
# → dist/out/clover-web.zip
```

GitHub Pages・Netlify・社内サーバ等にそのまま設置できます。

## 完全オフライン化（任意）

既定では Pyodide 本体のみ jsDelivr CDN から読み込みます（ユーザのファイルは送信されません）。
ネットワークを一切使わせたくない場合は Pyodide を同梱・自己ホストし、`index.html` の
`<script src=".../pyodide.js">` をローカルパスに差し替えてください。

## 構成

| ファイル | 役割 |
|---|---|
| `index.html` / `style.css` | UI |
| `app.js` | Pyodide 起動・ホイール導入・ドラッグ&ドロップ処理 |
| `convert.py` | ブラウザ内で動く変換ブリッジ |
| `wheels/` | `clover2xml`（クリーン版コア）+ `defusedxml` |
| `samples/demo.*` | 合成サンプル（架空のコード進行） |

> MIDI 入力（`midi2clover`）はネイティブ依存（rtmidi）のため Web 版には含めていません。ローカル CLI をご利用ください。
