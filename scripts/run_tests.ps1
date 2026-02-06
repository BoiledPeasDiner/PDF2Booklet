\
    # PowerShell: run lint + tests (uv優先、無ければvenv)
    if (Get-Command uv -ErrorAction SilentlyContinue) {
      uv run ruff check .
      uv run pytest -q
      exit $LASTEXITCODE
    }

    if (Test-Path ".\.venv\Scripts\Activate.ps1") {
      .\.venv\Scripts\Activate.ps1
      ruff check .
      pytest -q
      exit $LASTEXITCODE
    }

    Write-Error "uv も .venv も見つかりません。READMEのセットアップ手順を実行してください。"
    exit 1
