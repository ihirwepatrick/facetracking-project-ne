#!/usr/bin/env python3
"""Download ArcFace ONNX model and MediaPipe face landmarker model."""

import shutil
import sys
import urllib.request
import zipfile
from pathlib import Path

from src import config
from src.face_mesh import FACE_LANDMARKER_URL, ensure_face_landmarker_model

ARCFACE_URL = (
    "https://sourceforge.net/projects/insightface.mirror/files/v0.7/buffalo_l.zip/download"
)
MIN_ZIP_BYTES = 100_000_000  # buffalo_l.zip is ~170 MB; reject partial downloads


def _download_file(url: str, dest: Path) -> None:
    """Download url to dest with a simple progress indicator."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"Downloading to {dest} ...")

    def _report(block_num: int, block_size: int, total_size: int) -> None:
        if total_size > 0:
            pct = min(100, block_num * block_size * 100 // total_size)
            print(f"\r  {pct:3d}% ({block_num * block_size // (1024 * 1024)} MB)", end="", flush=True)

    urllib.request.urlretrieve(url, dest, reporthook=_report)
    print()


def download_arcface() -> bool:
    config.ensure_dirs()
    if config.ARCFACE_MODEL_PATH.exists():
        print(f"OK ArcFace model already exists: {config.ARCFACE_MODEL_PATH}")
        return True

    zip_path = config.PROJECT_ROOT / "buffalo_l.zip"
    if zip_path.exists() and zip_path.stat().st_size < MIN_ZIP_BYTES:
        print(f"Removing incomplete download ({zip_path.stat().st_size // (1024 * 1024)} MB)")
        zip_path.unlink()

    print("Downloading ArcFace model (~170 MB)...")
    print(f"  {ARCFACE_URL}")

    try:
        if not zip_path.exists():
            _download_file(ARCFACE_URL, zip_path)
        if not zip_path.exists() or zip_path.stat().st_size < MIN_ZIP_BYTES:
            print("ERROR: Download failed or file is too small.")
            return False

        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(config.PROJECT_ROOT)

        src_model = config.PROJECT_ROOT / "w600k_r50.onnx"
        if src_model.exists():
            shutil.copy(str(src_model), str(config.ARCFACE_MODEL_PATH))
            print(f"OK ArcFace model saved to {config.ARCFACE_MODEL_PATH}")
        zip_path.unlink(missing_ok=True)
        for name in ("w600k_r50.onnx", "1k3d68.onnx", "2d106det.onnx", "det_10g.onnx", "genderage.onnx"):
            (config.PROJECT_ROOT / name).unlink(missing_ok=True)
        return config.ARCFACE_MODEL_PATH.exists()
    except Exception as exc:
        print(f"ERROR: {exc}")
        return False


def download_models() -> bool:
    print("=" * 60)
    print(" Model Download")
    print("=" * 60)
    ok_arc = download_arcface()
    try:
        ensure_face_landmarker_model()
        ok_landmark = config.FACE_LANDMARKER_MODEL_PATH.exists()
    except Exception as exc:
        print(f"Face landmarker download failed: {exc}")
        ok_landmark = False
    if ok_arc and ok_landmark:
        print("\nOK All models ready.")
        return True
    print("\nERROR Some models missing. See errors above.")
    return False


if __name__ == "__main__":
    sys.exit(0 if download_models() else 1)
