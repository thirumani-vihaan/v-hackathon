"""T012 acceptance: run schema contract tests via pytest."""
import os
import sys
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest",
         os.path.join("tests", "test_schema_contracts.py"), "-q", "--no-header"],
        cwd=ROOT, capture_output=True, text=True)
    print(proc.stdout[-2000:])
    if proc.returncode != 0:
        print(proc.stderr[-1500:])
        return 1
    print("T012 PASS: schema contract tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
