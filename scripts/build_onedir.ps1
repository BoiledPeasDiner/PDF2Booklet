
    # PowerShell: build onedir (folder distribution)
    if (Get-Command uv -ErrorAction SilentlyContinue) {
      uv run pyinstaller --noconfirm --windowed --name "PDF2Booklet" --icon assets\icon.ico app\gui\main.py
      exit $LASTEXITCODE
    }

    .\.venv\Scripts\Activate.ps1
    pyinstaller --noconfirm --windowed --name "PDF2Booklet" --icon assets\icon.ico app\gui\main.py
