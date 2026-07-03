"""Bundle evidence artifacts into a single downloadable ZIP."""
import os
import zipfile
from datetime import datetime

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
_DATA = os.path.join(_ROOT, "data")
_DEFAULT_ZIP = os.path.join(_DATA, "evidence_package.zip")


def _latest_pdfs(data_dir: str, limit: int = 5) -> list:
    if not os.path.isdir(data_dir):
        return []
    pdfs = [os.path.join(data_dir, f) for f in os.listdir(data_dir)
            if f.lower().endswith(".pdf")]
    pdfs.sort(key=lambda p: os.path.getmtime(p), reverse=True)
    return pdfs[:limit]


def export_zip(zip_path: str = _DEFAULT_ZIP, data_dir: str = _DATA) -> str:
    """Zip the evidence log, latest PDFs and demo trace into zip_path.

    Returns the zip path. Writes a manifest.txt describing the contents and
    a timestamp. Never raises; missing sources are simply skipped.
    """
    os.makedirs(os.path.dirname(zip_path) or ".", exist_ok=True)
    candidates = []
    log = os.path.join(data_dir, "evidence_log.jsonl")
    if os.path.isfile(log):
        candidates.append(log)
    trace = os.path.join(data_dir, "demo_trace.jsonl")
    if os.path.isfile(trace):
        candidates.append(trace)
    candidates.extend(_latest_pdfs(data_dir))

    manifest = ["IndustrialSafetyAI evidence package",
                f"generated: {datetime.utcnow().isoformat()}Z", "contents:"]
    try:
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
            for path in candidates:
                try:
                    arc = os.path.basename(path)
                    zf.write(path, arcname=arc)
                    manifest.append(f"  - {arc} ({os.path.getsize(path)} bytes)")
                except Exception as e:  # noqa: BLE001
                    manifest.append(f"  ! skipped {path}: {e}")
            if len(manifest) == 3:
                manifest.append("  (no artifacts found yet)")
            zf.writestr("manifest.txt", "\n".join(manifest))
    except Exception as e:  # noqa: BLE001
        return f"ERROR: {e}"
    return zip_path


if __name__ == "__main__":
    print(export_zip())
