#!/usr/bin/env python3
"""
Download a video file from Google Drive and place it in upload/.
Usage: python driver.py <google_drive_url_or_file_id>

Supports:
  https://drive.google.com/file/d/<ID>/view?...
  https://drive.google.com/open?id=<ID>
  https://drive.google.com/uc?id=<ID>
  <bare file ID>
"""
import os
import re
import sys
import shutil
import tempfile
from pathlib import Path

try:
    import gdown
except ImportError:
    sys.exit("Missing dependency: run  pip install gdown  then retry.")

BASE = Path(__file__).resolve().parents[3]
UPLOAD_DIR = BASE / "upload"

VIDEO_EXTS = {".mp4", ".mov", ".avi", ".mkv", ".wmv", ".flv", ".ts", ".webm", ".m4v", ".3gp"}


def extract_file_id(raw: str) -> str:
    """Return the bare Google Drive file ID from any share-link format."""
    # /file/d/<ID>/
    m = re.search(r"/file/d/([a-zA-Z0-9_-]+)", raw)
    if m:
        return m.group(1)
    # ?id=<ID> or &id=<ID>
    m = re.search(r"[?&]id=([a-zA-Z0-9_-]+)", raw)
    if m:
        return m.group(1)
    # Looks like a bare ID already (alphanumeric + _ -)
    if re.fullmatch(r"[a-zA-Z0-9_-]{10,}", raw):
        return raw
    sys.exit(f"Could not extract a Google Drive file ID from: {raw}")


def download(file_id: str, dest_dir: Path) -> Path:
    url = f"https://drive.google.com/uc?id={file_id}"
    print(f"Downloading from Google Drive (id={file_id}) …")
    output = str(dest_dir / "gdrive_download")
    result = gdown.download(url, output, quiet=False, fuzzy=True)
    if result is None:
        sys.exit("Download failed. Check that the file is shared publicly (Anyone with the link).")
    return Path(result)


def main():
    if len(sys.argv) < 2:
        print("Usage: python driver.py <google_drive_url_or_file_id>")
        sys.exit(1)

    raw = sys.argv[1].strip()
    file_id = extract_file_id(raw)

    with tempfile.TemporaryDirectory() as tmp:
        downloaded = download(file_id, Path(tmp))
        ext = downloaded.suffix.lower()

        if ext not in VIDEO_EXTS:
            sys.exit(
                f"Downloaded file '{downloaded.name}' has extension '{ext}', "
                f"which is not a recognised video format.\n"
                f"Supported: {', '.join(sorted(VIDEO_EXTS))}"
            )

        UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
        dest = UPLOAD_DIR / downloaded.name

        # Avoid silently overwriting existing file
        if dest.exists():
            base, suffix = dest.stem, dest.suffix
            i = 1
            while dest.exists():
                dest = UPLOAD_DIR / f"{base}_{i}{suffix}"
                i += 1
            print(f"File already exists; saving as {dest.name}")

        shutil.move(str(downloaded), str(dest))

    print(f"Video saved to: {dest}")
    print("Ready for /run-transcribe or /run-pipeline.")


if __name__ == "__main__":
    main()
