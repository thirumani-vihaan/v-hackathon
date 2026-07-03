"""T011 acceptance: launch the Streamlit UI, confirm HTTP 200, then terminate.

Tries port 8502 first, then 8602. Uses the venv python that runs this script.
"""
import os
import sys
import time
import subprocess

ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
sys.path.insert(0, ROOT)


def _try_port(port):
    import requests
    app = os.path.join(ROOT, "ui", "app.py")
    cmd = [
        sys.executable, "-m", "streamlit", "run", app,
        "--server.port", str(port),
        "--server.headless", "true",
        "--server.address", "127.0.0.1",
        "--browser.gatherUsageStats", "false",
    ]
    proc = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE,
                            stderr=subprocess.STDOUT)
    try:
        deadline = time.time() + 40
        url = f"http://127.0.0.1:{port}/"
        while time.time() < deadline:
            if proc.poll() is not None:
                out = proc.stdout.read().decode("utf-8", "ignore")[-800:]
                print(f"streamlit exited early on port {port}:\n{out}")
                return False
            try:
                r = requests.get(url, timeout=2)
                if r.status_code == 200:
                    print(f"HTTP 200 from {url}")
                    return True
            except Exception:
                pass
            time.sleep(1)
        print(f"timeout waiting for HTTP 200 on port {port}")
        return False
    finally:
        try:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except Exception:
                proc.kill()
        except Exception:
            pass


def main():
    for port in (8502, 8602):
        print(f"--- trying streamlit on port {port} ---")
        if _try_port(port):
            print("T011 PASS: streamlit served HTTP 200")
            return 0
    print("T011 FAIL: streamlit did not serve 200 on 8502/8602")
    return 1


if __name__ == "__main__":
    sys.exit(main())
