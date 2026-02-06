import sys
from pathlib import Path

# プロジェクトルート（tests の1つ上）を import パスに追加
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
