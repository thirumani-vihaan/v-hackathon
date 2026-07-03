"""T013 acceptance: run the full test suite (>=14 tests) via pytest."""
import os
import sys
import re
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def main():
    proc = subprocess.run(
        [sys.executable, "-m", "pytest",
         os.path.join("tests", "test_all.py"), "-q", "--no-header"],
        cwd=ROOT, capture_output=True, text=True)
    out = proc.stdout
    print(out[-2500:])
    if proc.returncode != 0:
        print(proc.stderr[-1500:])
        return 1
    # count passed
    m = re.search(r"(\d+) passed", out)
    passed = int(m.group(1)) if m else 0
    if passed < 14:
        print(f"T013 FAIL: only {passed} tests passed (need >=14)")
        return 1
    print(f"T013 PASS: {passed} tests passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
