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


MAGIC_TO_EXT = {
    b"\x00\x00\x00": ".mp4",   # ftyp box (checked below)
    b"\x1a\x45\xdf\xa3": ".mkv",
    b"\x52\x49\x46\x46": ".avi",
    b"\x46\x4c\x56": ".flv",
    b"\x00\x00\x01\xba": ".ts",
    b"\x00\x00\x01\xb3": ".ts",
}

def _detect_ext(path: Path) -> str:
    """Return file extension from magic bytes, or empty string if unknown."""
    try:
        with open(path, "rb") as f:
            header = f.read(12)
        # MP4/MOV/M4V share ISO Base Media ftyp box at offset 4
        if header[4:8] in (b"ftyp", b"moov", b"mdat", b"free", b"skip"):
            brand = header[8:12]
            if brand.startswith(b"qt"):
                return ".mov"
            return ".mp4"
        if header[:4] == b"\x1a\x45\xdf\xa3":
            return ".mkv"
        if header[:4] == b"RIFF" and header[8:12] == b"AVI ":
            return ".avi"
        if header[:3] == b"FLV":
            return ".flv"
        if header[:4] in (b"\x00\x00\x01\xba", b"\x00\x00\x01\xb3"):
            return ".ts"
        if header[:4] == b"\x1a\x45\xdf\xa3":
            return ".webm"
    except Exception:
        pass
    return ""


def download(file_id: str, dest_dir: Path) -> Path:
    print(f"Downloading from Google Drive (id={file_id}) …")
    output = str(dest_dir / "gdrive_download")
    result = gdown.download(id=file_id, output=output, quiet=False)
    if result is None:
        sys.exit("Download failed. Check that the file is shared publicly (Anyone with the link).")
    downloaded = Path(result)
    # If gdown didn't give us an extension, detect from magic bytes
    if not downloaded.suffix:
        ext = _detect_ext(downloaded)
        if ext:
            renamed = downloaded.with_name(downloaded.name + ext)
            downloaded.rename(renamed)
            downloaded = renamed
    return downloaded


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
