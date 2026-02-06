
    # PowerShell: build onefile (single exe)
    if (Get-Command uv -ErrorAction SilentlyContinue) {
      uv run pyinstaller --noconfirm --windowed --onefile --name "PDF2Booklet" --icon assets\icon.ico app\gui\main.py
      exit $LASTEXITCODE
    }

    .\.venv\Scripts\Activate.ps1
    pyinstaller --noconfirm --windowed --onefile --name "PDF2Booklet" --icon assets\icon.ico app\gui\main.py
