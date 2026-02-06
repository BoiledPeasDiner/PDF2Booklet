# PDF2Booklet（Windows）

複数の **PDF + 画像（JPG/PNG）** を読み込み、A4横の **ブックレット（中綴じ面付け）** または **2-in-1（通常順2-up）** のPDFを生成するWindows用GUIアプリです。

- デフォルト出力：**ブックレット**
- 両面印刷想定：**短辺とじ**
- 右プレビュー：**常に通常順2-up**（ブックレット順は表示しません）
- 表紙：プレビュー/2-in-1では「(空白,1)」にできます。ブックレット出力には反映しません（誤印刷防止）。
- HEICは非対応（追加時に分かりやすいエラーを表示）
- パスワード保護PDFは非対応（エラー表示）
- 省サイズON時（高画質寄り）：**dpi=180 / JPEG品質=85**

## 推奨ツール
- VS Code
- Python 3.12（Windows x64）
- （推奨）uv：Pythonバージョン管理＋依存管理＋実行をまとめられます

---

## セットアップ（uv 推奨）
PowerShellでプロジェクト直下：

```powershell
uv python install 3.12
uv python pin 3.12
uv venv
uv pip install -r requirements.txt
```

実行：
```powershell
uv run python -m app.gui.main
```

テスト：
```powershell
uv run pytest
```

---

## セットアップ（uvなし・venvのみ）
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

---

## GUI実行
```powershell
python -m app.gui.main
```

## CLI実行（再現・自動テスト用）
```powershell
python -m app.cli.main --manifest C:\work\manifest.json
```

---

## テスト＆ビルド用スクリプト
- `scripts/run_tests.ps1`：ruff + pytest（uv優先、無ければvenv）
- `scripts/build_onedir.ps1`：フォルダ配布（dist/PDF2Booklet/）
- `scripts/build_onefile.ps1`：単体exe（dist/PDF2Booklet.exe）

---

## exe化（手動コマンド例）
onedir：
```powershell
pyinstaller --noconfirm --windowed --name "PDF2Booklet" --icon assets\icon.ico app\gui\main.py
```

onefile：
```powershell
pyinstaller --noconfirm --windowed --onefile --name "PDF2Booklet" --icon assets\icon.ico app\gui\main.py
```

アイコンは `assets/icon.ico` を差し替えてください。
