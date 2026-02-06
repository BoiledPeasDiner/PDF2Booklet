import argparse
from app.core.engine import run_job_from_manifest
from app.core.errors import UserFacingError

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--manifest", required=True)
    args = ap.parse_args()
    try:
        run_job_from_manifest(args.manifest)
        print("OK")
    except UserFacingError as e:
        print(f"ERROR: {e}")
        raise SystemExit(2)

if __name__ == "__main__":
    main()
