"""
Stockfish service — finds, downloads, and wraps the engine subprocess.

Pure Python — no Qt. The QThread worker that uses this lives in core/analyzer.py.
"""

from __future__ import annotations
import os
import platform
import subprocess
import tarfile
import urllib.request
import zipfile
from pathlib import Path
from typing import Optional

import chess
import chess.engine

from app.config import USER_HOME, ENGINE_DEPTH, ENGINE_HASH_MB, ENGINE_THREADS


# Subprocess creation flags — on Windows we MUST pass CREATE_NO_WINDOW or
# every subprocess (stockfish, `where`, etc.) spawns a black cmd window
# that flashes / sits on top of the app. This was the popup the user saw.
_NO_WINDOW = subprocess.CREATE_NO_WINDOW if platform.system() == "Windows" else 0


# Stockfish 16 official binaries (AVX2 builds for modern CPUs)
_DOWNLOAD_URLS = {
    "Windows": "https://github.com/official-stockfish/Stockfish/releases/download/sf_16/stockfish-windows-x86-64-avx2.zip",
    "Darwin":  "https://github.com/official-stockfish/Stockfish/releases/download/sf_16/stockfish-macos-x86-64-avx2.tar",
    "Linux":   "https://github.com/official-stockfish/Stockfish/releases/download/sf_16/stockfish-ubuntu-x86-64-avx2.tar",
}


def find_engine() -> Optional[Path]:
    """Look for an existing Stockfish binary."""
    is_win = platform.system() == "Windows"
    name = "stockfish.exe" if is_win else "stockfish"

    # 1. Our cache
    cached = USER_HOME / name
    if cached.exists():
        return cached

    # 2. On PATH
    cmd = "where" if is_win else "which"
    try:
        result = subprocess.run(
            [cmd, "stockfish"],
            capture_output=True, text=True, timeout=5,
            creationflags=_NO_WINDOW,
        )
        if result.returncode == 0:
            line = result.stdout.strip().splitlines()[0] if result.stdout else ""
            if line:
                return Path(line)
    except Exception:
        pass

    return None


def download_engine(progress_cb=None) -> Optional[Path]:
    """
    Download Stockfish to our cache directory.

    `progress_cb` (optional) receives status strings like "Downloading…", "Extracting…", "Ready".
    Returns the path on success, None on failure.
    """
    def emit(msg: str) -> None:
        if progress_cb:
            try: progress_cb(msg)
            except Exception: pass

    system = platform.system()
    url = _DOWNLOAD_URLS.get(system)
    if url is None:
        emit(f"Unsupported platform: {system}")
        return None

    is_win = system == "Windows"
    is_tar = url.endswith(".tar")
    is_zip = url.endswith(".zip")
    dest_name = "stockfish.exe" if is_win else "stockfish"
    dest = USER_HOME / dest_name

    archive_path = USER_HOME / f"sf_download.{('zip' if is_zip else 'tar')}"

    try:
        emit("Downloading Stockfish (~10 MB)…")
        urllib.request.urlretrieve(url, archive_path)
    except Exception as e:
        emit(f"Download failed: {e}")
        return None

    emit("Extracting…")
    try:
        if is_zip:
            with zipfile.ZipFile(archive_path) as z:
                for n in z.namelist():
                    nl = n.lower()
                    if nl.endswith(".exe") and "stockfish" in nl:
                        with z.open(n) as src, open(dest, "wb") as out:
                            out.write(src.read())
                        break
        else:
            with tarfile.open(archive_path) as t:
                for m in t.getmembers():
                    nl = m.name.lower()
                    if m.isfile() and "stockfish" in nl and not nl.endswith(".md"):
                        f = t.extractfile(m)
                        if f:
                            with open(dest, "wb") as out:
                                out.write(f.read())
                            break

        archive_path.unlink(missing_ok=True)
        if not is_win:
            os.chmod(dest, 0o755)

        if not dest.exists():
            emit("Extraction failed: binary not found in archive")
            return None

        emit("Stockfish ready")
        return dest
    except Exception as e:
        emit(f"Extraction failed: {e}")
        return None


# ─────────────────────────────────────────────────────────────────────────────
#  Engine context manager — used by analysis workers
# ─────────────────────────────────────────────────────────────────────────────
class Engine:
    """
    Thin context-manager wrapper for python-chess's SimpleEngine.

    Usage:
        with Engine(path) as eng:
            info = eng.analyse(board, depth=16)
    """

    def __init__(self, path: Path,
                 depth: int = ENGINE_DEPTH,
                 hash_mb: int = ENGINE_HASH_MB,
                 threads: int = ENGINE_THREADS) -> None:
        self.path = path
        self.depth = depth
        self._cfg = {"Threads": threads, "Hash": hash_mb}
        self._engine: Optional[chess.engine.SimpleEngine] = None

    def __enter__(self) -> "Engine":
        # CREATE_NO_WINDOW prevents the stockfish subprocess from popping
        # a black cmd window on Windows when running from the .exe.
        self._engine = chess.engine.SimpleEngine.popen_uci(
            str(self.path),
            creationflags=_NO_WINDOW,
        )
        self._engine.configure(self._cfg)
        return self

    def __exit__(self, *args) -> None:
        if self._engine is not None:
            try: self._engine.quit()
            except Exception: pass
            self._engine = None

    def analyse(self, board: chess.Board, depth: Optional[int] = None) -> dict:
        """Run one analysis at the configured depth, return python-chess info."""
        if self._engine is None:
            raise RuntimeError("Engine not started — use `with Engine(path)` block")
        limit = chess.engine.Limit(depth=depth or self.depth)
        return self._engine.analyse(board, limit)
