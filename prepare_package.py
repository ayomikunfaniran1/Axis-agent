"""
Prepare a zip archive of the project for upload (excludes large/dev files).
Run: python prepare_package.py
"""
import os
import zipfile
from datetime import datetime

ROOT = os.path.dirname(__file__)
EXCLUDE = {"axis-agent.zip", "axis-agent.tar.gz", ".git", "venv", ".venv", "__pycache__", "actions.log"}

def should_exclude(path):
    parts = set(p for p in path.split(os.sep) if p)
    return bool(parts & EXCLUDE)

def make_zip(dest_name=None):
    if dest_name is None:
        dest_name = os.path.join(ROOT, f"axis-agent-{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}.zip")
    with zipfile.ZipFile(dest_name, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for dirpath, dirnames, filenames in os.walk(ROOT):
            # skip excluded directories in-place so os.walk doesn't descend
            dirnames[:] = [d for d in dirnames if not should_exclude(os.path.join(dirpath, d))]
            for f in filenames:
                rel = os.path.relpath(os.path.join(dirpath, f), ROOT)
                if should_exclude(rel):
                    continue
                z.write(os.path.join(dirpath, f), rel)
    return dest_name

if __name__ == "__main__":
    out = make_zip()
    print("Created:", out)
