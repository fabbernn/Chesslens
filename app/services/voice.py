"""
Voice service — Kokoro AI TTS with pyttsx3 fallback.

Pure-Python service (no Qt deps). Uses background threads for non-blocking
TTS — UI just calls voice.speak(text) and moves on.

Kokoro is the premium voice (human-sounding AI). pyttsx3 is the OS fallback
(Windows SAPI / NSSpeechSynthesizer / espeak).
"""

from __future__ import annotations
import json
import os
import platform
import queue
import subprocess
import tempfile
import threading
import time
from pathlib import Path
from typing import Callable

import numpy as np
import pyttsx3
import soundfile as sf

from app.config import MODELS_DIR


# Where we persist user voice preferences across launches. Lives next to
# the Kokoro models so deleting ~/.chesslens wipes everything cleanly.
SETTINGS_PATH = MODELS_DIR.parent / "voice_settings.json"

# JSON keys for the persisted settings file. Centralised so a typo in one
# place doesn't silently break round-tripping in another.
class _SettingsKeys:
    ENABLED    = "enabled"
    VOLUME     = "volume"
    SPEED      = "speed"
    VOICE      = "voice"
    READ_COLOR = "read_color"

_KEYS = _SettingsKeys()


# ─── Kokoro model files ────────────────────────────────────────────────────────
KOKORO_MODEL     = MODELS_DIR / "kokoro-v1.0.onnx"
KOKORO_VPACK     = MODELS_DIR / "voices-v1.0.bin"
KOKORO_MODEL_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/kokoro-v1.0.onnx"
KOKORO_VPACK_URL = "https://github.com/thewh1teagle/kokoro-onnx/releases/download/model-files-v1.0/voices-v1.0.bin"

KOKORO_VOICES = [
    ("af_heart",   "Heart — US Female ★ Best"),
    ("af_sarah",   "Sarah — US Female"),
    ("af_bella",   "Bella — US Female"),
    ("af_nicole",  "Nicole — US Female (soft)"),
    ("am_adam",    "Adam — US Male"),
    ("am_michael", "Michael — US Male"),
    ("bm_george",  "George — British Male"),
    ("bf_emma",    "Emma — British Female"),
]


# ─────────────────────────────────────────────────────────────────────────────
#  AUDIO PLAYER
# ─────────────────────────────────────────────────────────────────────────────
class AudioPlayer:
    """Tiny OS-native WAV player. Stop-and-replace single-stream model."""

    def __init__(self) -> None:
        self._proc: subprocess.Popen | None = None

    def play(self, path: str) -> None:
        self.stop()
        threading.Thread(target=self._play, args=(path,), daemon=True).start()

    def _play(self, path: str) -> None:
        try:
            sysname = platform.system()
            if sysname == "Windows":
                import winsound
                winsound.PlaySound(path, winsound.SND_FILENAME)
            elif sysname == "Darwin":
                self._proc = subprocess.Popen(
                    ["afplay", path],
                    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                )
                self._proc.wait()
            else:
                for cmd in ("paplay", "aplay"):
                    try:
                        self._proc = subprocess.Popen(
                            [cmd, path],
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                        )
                        self._proc.wait()
                        break
                    except FileNotFoundError:
                        continue
        except Exception:
            pass

    def stop(self) -> None:
        if self._proc is not None:
            try: self._proc.terminate()
            except Exception: pass
            self._proc = None


# ─────────────────────────────────────────────────────────────────────────────
#  VOICE
# ─────────────────────────────────────────────────────────────────────────────
class Voice:
    """Kokoro AI voice with pyttsx3 fallback. Thread-safe; non-blocking."""

    def __init__(self, on_status: Callable[[str, bool], None] | None = None,
                 on_speak: Callable[[str], None] | None = None) -> None:
        self.enabled = False
        self.paused  = False   # session-only, NOT persisted
        self._vol    = 0.85
        # "both" | "white" | "black" — which side's moves trigger callouts
        self.read_color = "both"
        self._on_status = on_status or (lambda m, err=False: None)
        # on_speak fires the moment a new line begins (used for subtitles).
        # Empty string signals "stopped speaking, clear subtitles".
        self._on_speak  = on_speak  or (lambda text: None)

        # Kokoro
        self._kokoro       = None
        self._kvoice       = "af_heart"
        self._kspeed       = 1.0
        self._player       = AudioPlayer()
        self._kq: queue.Queue = queue.Queue()
        self._kstop        = threading.Event()
        self.kokoro_ready  = False

        # ── Restore saved preferences BEFORE workers start ─────────────────
        # So the workers see the right defaults (volume, speed, voice).
        self._load_settings()

        threading.Thread(target=self._kokoro_worker, daemon=True).start()
        threading.Thread(target=self._load_kokoro,   daemon=True).start()

        # pyttsx3 fallback — IMPORTANT: SAPI on Windows requires the engine
        # to be created and used on the SAME thread. So we init pyttsx3 inside
        # the worker thread, not on main thread.
        self._pq: queue.Queue = queue.Queue()
        self._peng = None
        self._pending_volume = self._vol
        self._pending_speed  = self._kspeed
        self._pending_voice  = None     # voice id to set when worker boots
        self._pfallback_stop = threading.Event()   # request fallback to stop NOW
        self.fallback_ready = False
        threading.Thread(target=self._fallback_worker, daemon=True).start()

    # ── Settings persistence ─────────────────────────────────────────────────────
    # Settings live in ~/.chesslens/voice_settings.json so they survive
    # restarts. Any setter that changes a persisted field MUST call
    # _save_settings() so the change is durable.
    def _load_settings(self) -> None:
        try:
            if not SETTINGS_PATH.exists():
                self._log("No saved settings — using defaults")
                return
            with open(SETTINGS_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            # Apply with sanity checks — don't trust the file blindly
            self.enabled    = bool(data.get(_KEYS.ENABLED, self.enabled))
            self._vol       = max(0.0, min(1.0, float(data.get(_KEYS.VOLUME, self._vol))))
            self._kspeed    = max(0.5, min(2.0, float(data.get(_KEYS.SPEED,  self._kspeed))))
            self._kvoice    = str(data.get(_KEYS.VOICE, self._kvoice))
            rc = str(data.get(_KEYS.READ_COLOR, self.read_color))
            if rc in ("both", "white", "black", "auto"):
                self.read_color = rc
            self._log(f"Loaded settings: enabled={self.enabled} vol={self._vol} "
                      f"speed={self._kspeed} voice={self._kvoice} "
                      f"read_color={self.read_color}")
        except Exception as e:
            self._log(f"Failed to load settings: {e}")

    def _save_settings(self) -> None:
        try:
            SETTINGS_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {
                _KEYS.ENABLED:    self.enabled,
                _KEYS.VOLUME:     self._vol,
                _KEYS.SPEED:      self._kspeed,
                _KEYS.VOICE:      self._kvoice,
                _KEYS.READ_COLOR: self.read_color,
            }
            # Atomic write: tmp file + rename, so a crash mid-write can't
            # corrupt the JSON.
            tmp = SETTINGS_PATH.with_suffix(".json.tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
            os.replace(tmp, SETTINGS_PATH)
        except Exception as e:
            self._log(f"Failed to save settings: {e}")

    # ── Kokoro lifecycle ───────────────────────────────────────────────────
    def _log(self, msg: str) -> None:
        """Write a line to ~/.chesslens/voice.log so we can debug
        Kokoro load issues in the packaged .exe (no console available)."""
        try:
            from app.config import MODELS_DIR
            log_path = MODELS_DIR.parent / "voice.log"
            log_path.parent.mkdir(parents=True, exist_ok=True)
            with open(log_path, "a", encoding="utf-8") as f:
                f.write(f"{time.strftime('%Y-%m-%d %H:%M:%S')}  {msg}\n")
        except Exception:
            pass

    def _load_kokoro(self) -> None:
        self._log("=== Voice service starting ===")
        self._log(f"Model path: {KOKORO_MODEL} (exists={KOKORO_MODEL.exists()})")
        self._log(f"Vpack path: {KOKORO_VPACK} (exists={KOKORO_VPACK.exists()})")
        if not KOKORO_MODEL.exists() or not KOKORO_VPACK.exists():
            self._on_status("Kokoro models not downloaded yet", False)
            self._log("ABORT: model files missing")
            return
        try:
            self._on_status("Loading Kokoro AI voice…", False)
            self._log("Importing kokoro_onnx...")
            from kokoro_onnx import Kokoro
            self._log("Import OK. Constructing Kokoro instance...")
            self._kokoro = Kokoro(str(KOKORO_MODEL), str(KOKORO_VPACK))
            self.kokoro_ready = True
            self._on_status("Kokoro AI voice ready", False)
            self._log("SUCCESS: Kokoro loaded and ready")
        except Exception as e:
            import traceback
            self._on_status(f"Kokoro failed: {e}", True)
            self._log(f"FAILED to load Kokoro: {e}")
            self._log(traceback.format_exc())

    def _kokoro_worker(self) -> None:
        while True:
            text = self._kq.get()
            if text is None:
                break
            if self._kstop.is_set() or self._kokoro is None:
                continue
            try:
                audio, sr = self._kokoro.create(
                    text, voice=self._kvoice, speed=self._kspeed, lang="en-us"
                )
                if self._kstop.is_set():
                    continue
                vol = max(0.0, min(1.0, self._vol))
                if vol != 1.0:
                    audio = (audio * vol).astype(np.float32)
                tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
                tmp.close()
                sf.write(tmp.name, audio, sr)
                if not self._kstop.is_set():
                    self._player.play(tmp.name)
                duration = len(audio) / sr
                deadline = time.time() + duration + 1.0
                while time.time() < deadline and not self._kstop.is_set():
                    time.sleep(0.05)
                try: os.unlink(tmp.name)
                except Exception: pass
            except Exception:
                pass

    # ── Fallback worker ────────────────────────────────────────────────────
    def _fallback_worker(self) -> None:
        # Initialize pyttsx3 INSIDE this thread. Windows SAPI requires the
        # COM-based engine to live on the same thread that drives it.
        import time
        try:
            self._peng = pyttsx3.init()
            self._peng.setProperty("rate", int(self._pending_speed * 160))
            self._peng.setProperty("volume", self._pending_volume)
            voices = self._peng.getProperty("voices") or []
            for v in voices:
                name = (v.name or "").lower()
                if any(k in name for k in ("zira", "hazel", "female", "aria")):
                    self._peng.setProperty("voice", v.id)
                    break
            self.fallback_ready = True
            self._on_status("Fallback voice ready", False)
        except Exception as e:
            self._on_status(f"Fallback voice error: {e}", True)
            return

        while True:
            text = self._pq.get()
            if text is None:
                break
            if self._peng is None:
                continue
            try:
                # Apply current volume/rate before each utterance
                self._peng.setProperty("volume", self._vol)
                self._peng.setProperty("rate", int(self._kspeed * 160))
                self._peng.say(text)

                # KEY INTERRUPT FIX: replace runAndWait() with startLoop +
                # iterate so we can poll for a new queued line and bail out
                # mid-sentence. pyttsx3.stop() alone is unreliable across
                # threads on Windows SAPI — this is the robust pattern.
                self._peng.startLoop(False)
                while (self._peng.isBusy() and self._pq.empty()
                        and not self._pfallback_stop.is_set()):
                    self._peng.iterate()
                    time.sleep(0.02)
                self._peng.endLoop()

                # If a new line landed in the queue while we were speaking,
                # OR stop was requested — forcibly cancel any tail of current.
                if not self._pq.empty() or self._pfallback_stop.is_set():
                    try:
                        self._peng.stop()
                    except Exception:
                        pass
                self._pfallback_stop.clear()
            except Exception:
                pass

    # ── Public API ─────────────────────────────────────────────────────────
    def speak(self, text: str) -> None:
        if not self.enabled or not text or self.paused:
            return
        # Subtitle hook — fires on EVERY new line, before any audio starts
        try:
            self._on_speak(text)
        except Exception:
            pass
        if self.kokoro_ready and self._kokoro is not None:
            self._kstop.set()
            self._player.stop()
            self._drain(self._kq)
            self._kstop.clear()
            self._kq.put(text)
        elif self.fallback_ready and self._peng is not None:
            # The worker thread polls the queue mid-utterance — putting a new
            # line on the queue causes the current speech to cut off and the
            # new one to start. Just drain & enqueue here.
            self._drain(self._pq)
            self._pq.put(text)

    def stop(self) -> None:
        # Kokoro side
        self._kstop.set()
        self._player.stop()
        self._drain(self._kq)
        # Fallback side — set the event so the worker bails mid-utterance
        self._pfallback_stop.set()
        self._drain(self._pq)
        if self._peng is not None:
            try: self._peng.stop()
            except Exception: pass
        # Tell subtitle subscribers we're silent
        try:
            self._on_speak("")
        except Exception:
            pass

    def toggle(self) -> bool:
        self.enabled = not self.enabled
        if not self.enabled:
            self.stop()
        self._save_settings()
        return self.enabled

    def set_paused(self, paused: bool) -> bool:
        """Pause or resume voice playback. Returns the new paused state.

        When paused: any currently-playing line is stopped IMMEDIATELY and
        no new lines play until resumed. Subtitles also clear.
        """
        self.paused = bool(paused)
        if self.paused:
            self.stop()   # already clears subtitle via _on_speak("")
        return self.paused

    def toggle_pause(self) -> bool:
        return self.set_paused(not self.paused)

    def set_volume(self, v: float) -> None:
        # Just update the value — the worker thread reads it before each speak.
        self._vol = max(0.0, min(1.0, float(v)))
        self._save_settings()

    def set_speed(self, s: float) -> None:
        # Same: update value, worker thread will pick it up.
        self._kspeed = max(0.5, min(2.0, float(s)))
        self._save_settings()

    def set_kokoro_voice(self, voice_id: str) -> None:
        self._kvoice = voice_id
        self._save_settings()

    def set_read_color(self, color: str) -> None:
        if color in ("both", "white", "black", "auto"):
            self.read_color = color
            self._save_settings()

    # ── Helpers ────────────────────────────────────────────────────────────
    @staticmethod
    def _drain(q: queue.Queue) -> None:
        while not q.empty():
            try: q.get_nowait()
            except Exception: break

    # ── Model download ─────────────────────────────────────────────────────
    def download_kokoro(self, cb: Callable[[str, bool], None] | None = None) -> None:
        """Download Kokoro model files in a background thread.

        cb receives (status_msg, done_flag) periodically.
        """
        cb = cb or (lambda m, done=False: None)

        def dl() -> None:
            import urllib.request
            MODELS_DIR.mkdir(parents=True, exist_ok=True)
            files = [
                (KOKORO_MODEL_URL, KOKORO_MODEL, "Kokoro model (~85 MB)"),
                (KOKORO_VPACK_URL, KOKORO_VPACK, "Voice pack (~12 MB)"),
            ]
            for url, dest, label in files:
                if dest.exists() and dest.stat().st_size > 100_000:
                    continue
                cb(f"Downloading {label}…", False)
                try:
                    urllib.request.urlretrieve(url, dest)
                except Exception as e:
                    cb(f"Download failed: {e}", True)
                    return
            cb("Download complete. Loading…", False)
            self._load_kokoro()
            cb("Kokoro ready", True)

        threading.Thread(target=dl, daemon=True).start()
