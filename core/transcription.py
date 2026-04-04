"""
core/transcription.py
Audio capture (JACK or sounddevice fallback) and real-time speech-to-text
using faster-whisper (preferred) with a Vosk fallback.

Runs in a background QThread and emits Qt signals for the UI.
"""

import logging
import queue
import threading
import time
import numpy as np
from typing import Optional

from PyQt6.QtCore import QThread, pyqtSignal

from core.openai_realtime import (
    OpenAIRealtimeTranscriber,
    OpenAIRealtimeTranscriptionConfig,
)

logger = logging.getLogger(__name__)
SUPPORTED_AUDIO_BACKENDS = {"auto", "jack", "sounddevice"}

# ── Model backend selection ───────────────────────────────────────────────────

def _try_faster_whisper():
    try:
        from faster_whisper import WhisperModel
        return WhisperModel
    except ImportError:
        return None

def _try_vosk():
    try:
        import vosk
        return vosk
    except ImportError:
        return None


# ── Audio backends ────────────────────────────────────────────────────────────

def _try_jack():
    try:
        import jack
        return jack
    except Exception as exc:
        logger.debug("jack unavailable: %s", exc)
        return None

def _try_sounddevice():
    try:
        import sounddevice as sd
        return sd
    except Exception as exc:
        logger.debug("sounddevice unavailable: %s", exc)
        return None


def _normalize_audio_backend(value: Optional[str]) -> str:
    backend = (value or "auto").strip().lower()
    if backend not in SUPPORTED_AUDIO_BACKENDS:
        logger.warning(
            "Unsupported audio backend %r; falling back to 'auto'. Supported values: %s",
            value,
            ", ".join(sorted(SUPPORTED_AUDIO_BACKENDS)),
        )
        return "auto"
    return backend


class AudioCaptureThread(QThread):
    """
    Captures audio from JACK (preferred) or sounddevice and puts
    numpy float32 chunks into an internal queue consumed by the
    transcription thread.
    """

    status_changed = pyqtSignal(str)   # human-readable status message
    error_occurred = pyqtSignal(str)
    audio_visual   = pyqtSignal(object, float)   # downsampled waveform, normalized level

    SAMPLE_RATE = 16000
    CHUNK_FRAMES = 4096    # ~256 ms at 16 kHz
    VISUAL_POINTS = 96

    def __init__(self, parent=None, device_name: str = "default", backend: str = "auto"):
        super().__init__(parent)
        self.device_name = device_name
        self._audio_queue: queue.Queue[np.ndarray] = queue.Queue(maxsize=50)
        self._stop_event = threading.Event()
        self._backend = "none"
        self._backend_preference = _normalize_audio_backend(backend)
        self._last_visual_emit = 0.0

    @property
    def audio_queue(self) -> queue.Queue:
        return self._audio_queue

    @property
    def backend(self) -> str:
        return self._backend

    def stop(self):
        self._stop_event.set()

    # ── Internal helpers ──────────────────────────────────────────────────────

    def _run_jack(self, jack_mod):
        """Capture audio via JACK client."""
        client = jack_mod.Client("VerseListener")
        port = client.inports.register("input_1")
        self._backend = "JACK"
        self.status_changed.emit("Listening via JACK")

        @client.set_process_callback
        def process(frames):
            if self._stop_event.is_set():
                return
            buf = port.get_array().copy()
            # Resample to mono float32 at 16 kHz if needed
            if client.samplerate != self.SAMPLE_RATE:
                ratio = self.SAMPLE_RATE / client.samplerate
                new_len = int(len(buf) * ratio)
                buf = np.interp(
                    np.linspace(0, len(buf) - 1, new_len),
                    np.arange(len(buf)),
                    buf,
                ).astype(np.float32)
            try:
                self._audio_queue.put_nowait(buf)
            except queue.Full:
                pass  # drop oldest not latest — queue consumer is too slow
            self._emit_audio_visual(buf)

        with client:
            # Auto-connect to system capture if available
            try:
                capture = client.get_ports(is_audio=True, is_output=True, is_physical=True)
                if capture:
                    client.connect(capture[0], port)
                    logger.info("Auto-connected JACK port: %s", capture[0].name)
            except Exception as e:
                logger.warning("JACK auto-connect failed: %s", e)

            logger.info("JACK client started")
            while not self._stop_event.is_set():
                self._stop_event.wait(0.5)

        logger.info("JACK client stopped")

    def _run_sounddevice(self, sd_mod):
        """Capture audio via sounddevice (supports JACK backend on Linux)."""
        self._backend = "sounddevice"
        device = None if self.device_name == "default" else self.device_name

        def callback(indata, frames, time_info, status):
            if status:
                logger.warning("sounddevice status: %s", status)
            if self._stop_event.is_set():
                raise sd_mod.CallbackStop()
            mono = indata[:, 0].copy().astype(np.float32)
            try:
                self._audio_queue.put_nowait(mono)
            except queue.Full:
                pass
            self._emit_audio_visual(mono)

        self.status_changed.emit("Listening via sounddevice")
        with sd_mod.InputStream(
            samplerate=self.SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=self.CHUNK_FRAMES,
            device=device,
            callback=callback,
        ):
            logger.info("sounddevice stream started")
            while not self._stop_event.is_set():
                self._stop_event.wait(0.1)

    def _run_dummy(self):
        """Silent dummy backend when no audio library is available."""
        self._backend = "dummy (no audio library)"
        self.status_changed.emit("No audio backend – install jack or sounddevice")
        silence = np.zeros(self.CHUNK_FRAMES, dtype=np.float32)
        while not self._stop_event.is_set():
            time.sleep(0.256)
            try:
                self._audio_queue.put_nowait(silence.copy())
            except queue.Full:
                pass
            self._emit_audio_visual(silence)

    # ── QThread entry ─────────────────────────────────────────────────────────

    def _emit_audio_visual(self, samples: np.ndarray):
        now = time.monotonic()
        if now - self._last_visual_emit < 0.08:
            return
        if samples.size == 0:
            return

        preview = samples
        step = max(1, len(samples) // self.VISUAL_POINTS)
        preview = preview[::step][:self.VISUAL_POINTS]
        if len(preview) < self.VISUAL_POINTS:
            preview = np.pad(preview, (0, self.VISUAL_POINTS - len(preview)))

        display_wave = np.clip(preview * 3.5, -1.0, 1.0)
        rms_level = float(np.sqrt(np.mean(np.square(samples))))
        normalized_level = max(0.0, min(rms_level * 12.0, 1.0))

        self.audio_visual.emit(display_wave.tolist(), normalized_level)
        self._last_visual_emit = now

    def _requested_backends(self) -> list[str]:
        if self._backend_preference == "auto":
            return ["jack", "sounddevice"]
        return [self._backend_preference]

    def _run_requested_backend(self, backend_name: str) -> bool:
        if backend_name == "jack":
            jack_mod = _try_jack()
            if not jack_mod:
                logger.info("JACK backend not available")
                return False
            self._run_jack(jack_mod)
            return True

        if backend_name == "sounddevice":
            sd_mod = _try_sounddevice()
            if not sd_mod:
                logger.info("sounddevice backend not available")
                return False
            self._run_sounddevice(sd_mod)
            return True

        logger.warning("Unknown audio backend requested: %s", backend_name)
        return False

    def run(self):
        try:
            for backend_name in self._requested_backends():
                try:
                    if self._run_requested_backend(backend_name):
                        return
                except Exception as e:
                    logger.warning("%s backend failed: %s", backend_name, e)
                    if self._backend_preference == "auto":
                        self.status_changed.emit(f"{backend_name} unavailable: {e}")
                        continue

                    self.error_occurred.emit(str(e))
                    return

            if self._backend_preference != "auto":
                self.error_occurred.emit(
                    f"{self._backend_preference} backend unavailable"
                )
            self._run_dummy()

        except Exception as e:
            logger.exception("AudioCaptureThread fatal error")
            self.error_occurred.emit(str(e))


# ─────────────────────────────────────────────────────────────────────────────

class TranscriptionThread(QThread):
    """
    Reads audio chunks from AudioCaptureThread.audio_queue and transcribes
    them using faster-whisper or Vosk, emitting partial/final text segments.
    """

    partial_result = pyqtSignal(str)   # streaming partial text
    final_result   = pyqtSignal(str)   # committed segment
    status_changed = pyqtSignal(str)
    error_occurred = pyqtSignal(str)
    model_loaded   = pyqtSignal(str)   # model name for status bar

    # How many seconds of audio to accumulate before running inference
    INFERENCE_SECONDS = 3.0
    SAMPLE_RATE = AudioCaptureThread.SAMPLE_RATE

    def __init__(
        self,
        audio_queue: "queue.Queue[np.ndarray]",
        whisper_model_name: str = "small.en",
        vosk_model_name: str = "en-us",
        backend: str = "auto",   # "whisper" | "vosk" | "auto"
        parent=None,
    ):
        super().__init__(parent)
        self._audio_queue = audio_queue
        self.whisper_model_name = whisper_model_name
        self.vosk_model_name = vosk_model_name
        self.backend = backend
        self._stop_event = threading.Event()

    def stop(self):
        self._stop_event.set()

    # ── Model loaders ─────────────────────────────────────────────────────────

    def _load_whisper(self):
        WhisperModel = _try_faster_whisper()
        if not WhisperModel:
            return None
        try:
            self.status_changed.emit(f"Loading faster-whisper ({self.whisper_model_name})…")
            model = WhisperModel(
                self.whisper_model_name,
                device="cpu",
                compute_type="int8",
            )
            self.model_loaded.emit(f"faster-whisper/{self.whisper_model_name}")
            logger.info("faster-whisper model loaded: %s", self.whisper_model_name)
            return model
        except Exception as e:
            logger.error("Failed to load faster-whisper: %s", e)
            return None

    def _load_vosk(self):
        vosk_mod = _try_vosk()
        if not vosk_mod:
            return None, None
        try:
            import os, json
            vosk_mod.SetLogLevel(-1)
            model_path = os.path.expanduser(f"~/.vosk/model-{self.vosk_model_name}")
            if not os.path.isdir(model_path):
                logger.warning("Vosk model not found at %s", model_path)
                return None, None
            model = vosk_mod.Model(model_path)
            rec = vosk_mod.KaldiRecognizer(model, self.SAMPLE_RATE)
            self.model_loaded.emit(f"vosk/{self.vosk_model_name}")
            logger.info("Vosk model loaded: %s", model_path)
            return model, rec
        except Exception as e:
            logger.error("Failed to load Vosk: %s", e)
            return None, None

    def _run_openai_realtime(self):
        config = OpenAIRealtimeTranscriptionConfig.from_env()
        transcriber = OpenAIRealtimeTranscriber(
            config=config,
            input_sample_rate=self.SAMPLE_RATE,
            audio_queue=self._audio_queue,
            stop_event=self._stop_event,
            on_partial=self.partial_result.emit,
            on_final=self.final_result.emit,
            on_status=self.status_changed.emit,
            on_error=self.error_occurred.emit,
            on_model_loaded=self.model_loaded.emit,
        )
        transcriber.run()

    # ── Transcription loops ───────────────────────────────────────────────────

    def _run_whisper(self, model):
        import io, wave, tempfile, os
        accumulated = np.array([], dtype=np.float32)
        last_flush = time.time()

        while not self._stop_event.is_set():
            # Drain queue into accumulation buffer
            try:
                chunk = self._audio_queue.get(timeout=0.1)
                accumulated = np.concatenate([accumulated, chunk])
            except queue.Empty:
                pass

            elapsed = time.time() - last_flush
            samples_needed = int(self.INFERENCE_SECONDS * self.SAMPLE_RATE)

            if len(accumulated) >= samples_needed or (elapsed > self.INFERENCE_SECONDS and len(accumulated) > 0):
                audio_buf = accumulated.copy()
                accumulated = np.array([], dtype=np.float32)
                last_flush = time.time()

                # Run inference
                try:
                    segments, info = model.transcribe(
                        audio_buf,
                        language="en",
                        beam_size=3,
                        vad_filter=True,
                        vad_parameters=dict(min_silence_duration_ms=300),
                    )
                    text = " ".join(s.text for s in segments).strip()
                    if text:
                        logger.debug("Transcribed: %s", text)
                        self.final_result.emit(text)
                except Exception as e:
                    logger.warning("Whisper inference error: %s", e)

    def _run_vosk(self, rec):
        import json
        while not self._stop_event.is_set():
            try:
                chunk = self._audio_queue.get(timeout=0.1)
            except queue.Empty:
                continue

            # Vosk expects int16 bytes
            int16_data = (chunk * 32767).astype(np.int16).tobytes()

            if rec.AcceptWaveform(int16_data):
                result = json.loads(rec.Result())
                text = result.get("text", "").strip()
                if text:
                    self.final_result.emit(text)
            else:
                partial = json.loads(rec.PartialResult())
                text = partial.get("partial", "").strip()
                if text:
                    self.partial_result.emit(text)

    def _run_dummy(self):
        """No model available – emit placeholder segments for demo."""
        self.model_loaded.emit("no model (demo)")
        self.status_changed.emit("No STT model found – transcription disabled")
        demo_phrases = [
            "And we read from John chapter 3 verse 16",
            "As Paul wrote in Romans chapter 8 verse 28",
            "Let us turn to Psalms 23 verse 1",
            "From the book of Genesis chapter 1 verse 1",
        ]
        idx = 0
        while not self._stop_event.is_set():
            time.sleep(5)
            if not self._stop_event.is_set():
                self.final_result.emit(demo_phrases[idx % len(demo_phrases)])
                idx += 1

    # ── QThread entry ─────────────────────────────────────────────────────────

    def run(self):
        try:
            if self.backend == "openai_realtime":
                self._run_openai_realtime()
                return

            use_whisper = self.backend in ("auto", "whisper")
            use_vosk    = self.backend in ("auto", "vosk")

            if use_whisper:
                model = self._load_whisper()
                if model:
                    self._run_whisper(model)
                    return

            if use_vosk:
                _, rec = self._load_vosk()
                if rec:
                    self._run_vosk(rec)
                    return

            self._run_dummy()

        except Exception as e:
            logger.exception("TranscriptionThread fatal error")
            self.error_occurred.emit(str(e))
