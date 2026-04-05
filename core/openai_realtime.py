"""
core/openai_realtime.py
Helpers for OpenAI Realtime transcription using gpt-4o-transcribe.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import queue
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional
from urllib import error as urllib_error
from urllib import request as urllib_request
import numpy as np

logger = logging.getLogger(__name__)


class RealtimeReconnectRequired(RuntimeError):
    """Raised when the Realtime websocket should be re-established."""


def _try_websocket():
    try:
        import websocket

        return websocket
    except Exception as exc:
        logger.debug("websocket-client unavailable: %s", exc)
        return None


def _env_str(name: str, default: str = "") -> str:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip()


def _env_float(name: str, default: float) -> float:
    value = _env_str(name)
    if not value:
        return default
    try:
        return float(value)
    except ValueError:
        logger.warning("Invalid float for %s=%r; using %s", name, value, default)
        return default


def _env_int(name: str, default: int) -> int:
    value = _env_str(name)
    if not value:
        return default
    try:
        return int(value)
    except ValueError:
        logger.warning("Invalid int for %s=%r; using %s", name, value, default)
        return default


def _env_bool(name: str, default: bool = False) -> bool:
    value = _env_str(name)
    if not value:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


@dataclass
class OpenAIRealtimeTranscriptionConfig:
    api_key: str
    model: str = "gpt-4o-transcribe"
    language: str = "en"
    prompt: str = ""
    url: str = "wss://api.openai.com/v1/realtime"
    client_secrets_url: str = "https://api.openai.com/v1/realtime/client_secrets"
    organization: str = ""
    project: str = ""
    input_rate: int = 24000
    noise_reduction: str = "near_field"
    vad_threshold: float = 0.5
    vad_prefix_padding_ms: int = 300
    vad_silence_duration_ms: int = 500
    include_logprobs: bool = False

    @classmethod
    def from_env(cls) -> "OpenAIRealtimeTranscriptionConfig":
        return cls(
            api_key=_env_str("OPENAI_API_KEY"),
            model=_env_str("OPENAI_REALTIME_TRANSCRIBE_MODEL", "gpt-4o-transcribe"),
            language=_env_str("OPENAI_REALTIME_LANGUAGE", "en"),
            prompt=_env_str("OPENAI_REALTIME_PROMPT"),
            url=_env_str("OPENAI_REALTIME_URL", "wss://api.openai.com/v1/realtime"),
            client_secrets_url=_env_str(
                "OPENAI_REALTIME_CLIENT_SECRETS_URL",
                "https://api.openai.com/v1/realtime/client_secrets",
            ),
            organization=_env_str("OPENAI_ORG_ID"),
            project=_env_str("OPENAI_PROJECT_ID"),
            input_rate=_env_int("OPENAI_REALTIME_INPUT_RATE", 24000),
            noise_reduction=_env_str("OPENAI_REALTIME_NOISE_REDUCTION", "near_field"),
            vad_threshold=_env_float("OPENAI_REALTIME_VAD_THRESHOLD", 0.5),
            vad_prefix_padding_ms=_env_int(
                "OPENAI_REALTIME_VAD_PREFIX_PADDING_MS", 300
            ),
            vad_silence_duration_ms=_env_int(
                "OPENAI_REALTIME_VAD_SILENCE_DURATION_MS", 500
            ),
            include_logprobs=_env_bool("OPENAI_REALTIME_INCLUDE_LOGPROBS", False),
        )

    def websocket_url(self) -> str:
        # For transcription-only Realtime sessions authenticated with a client
        # secret, the transcription model is part of the session configuration.
        return self.url

    def api_headers(self, bearer_token: str) -> list[str]:
        headers = [f"Authorization: Bearer {bearer_token}"]
        if self.organization:
            headers.append(f"OpenAI-Organization: {self.organization}")
        if self.project:
            headers.append(f"OpenAI-Project: {self.project}")
        return headers

    def session_config(self) -> dict:
        session = {
            "type": "transcription",
            "audio": {
                "input": {
                    "format": {
                        "type": "audio/pcm",
                        "rate": self.input_rate,
                    },
                    "transcription": {
                        "model": self.model,
                        "language": self.language,
                        "prompt": self.prompt,
                    },
                    "turn_detection": {
                        "type": "server_vad",
                        "threshold": self.vad_threshold,
                        "prefix_padding_ms": self.vad_prefix_padding_ms,
                        "silence_duration_ms": self.vad_silence_duration_ms,
                    },
                }
            },
        }
        if self.noise_reduction.lower() != "none":
            session["audio"]["input"]["noise_reduction"] = {
                "type": self.noise_reduction,
            }
        if self.include_logprobs:
            session["include"] = ["item.input_audio_transcription.logprobs"]
        return session

    def session_update_event(self) -> dict:
        return {
            "type": "session.update",
            "session": self.session_config(),
        }


class OpenAIRealtimeTranscriber:
    WEBSOCKET_IO_TIMEOUT = 10.0
    RECONNECT_DELAY_SECONDS = 1.0

    def __init__(
        self,
        config: OpenAIRealtimeTranscriptionConfig,
        input_sample_rate: int,
        audio_queue: "queue.Queue[np.ndarray]",
        stop_event: threading.Event,
        *,
        on_partial: Callable[[str], None],
        on_final: Callable[[str], None],
        on_status: Callable[[str], None],
        on_error: Callable[[str], None],
        on_model_loaded: Callable[[str], None],
    ):
        self.config = config
        self.input_sample_rate = input_sample_rate
        self.audio_queue = audio_queue
        self.stop_event = stop_event
        self.on_partial = on_partial
        self.on_final = on_final
        self.on_status = on_status
        self.on_error = on_error
        self.on_model_loaded = on_model_loaded
        self._partials: dict[str, str] = {}
        self._connection_closed = threading.Event()
        self._connection_error_message = ""
        self._connection_fatal = False

    def run(self):
        websocket_mod = _try_websocket()
        if not websocket_mod:
            raise RuntimeError(
                "The `websocket-client` package is not installed. "
                "Its import name is `websocket`, so run `pip install websocket-client`."
            )
        if not self.config.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not set. Add it to .env before using openai_realtime."
            )

        first_connection = True
        while not self.stop_event.is_set():
            ws = None
            reader = None
            self._reset_connection_state()
            try:
                self.on_status(f"Connecting to OpenAI Realtime ({self.config.model})…")
                client_secret = self._create_client_secret()
                ws = websocket_mod.create_connection(
                    self.config.websocket_url(),
                    header=self.config.api_headers(client_secret),
                    timeout=self.WEBSOCKET_IO_TIMEOUT,
                    enable_multithread=True,
                )
                ws.settimeout(self.WEBSOCKET_IO_TIMEOUT)

                if first_connection:
                    self.on_model_loaded(f"openai/{self.config.model}")
                    first_connection = False
                self.on_status(f"Transcribing via OpenAI Realtime ({self.config.model})")

                reader = threading.Thread(
                    target=self._reader_loop,
                    args=(ws, websocket_mod),
                    daemon=True,
                )
                reader.start()

                while not self.stop_event.is_set():
                    try:
                        chunk = self.audio_queue.get(timeout=0.1)
                    except queue.Empty:
                        if self._connection_closed.is_set() and self._connection_fatal:
                            raise RuntimeError(
                                self._connection_error_message
                                or "OpenAI Realtime connection closed unexpectedly."
                            )
                        continue

                    if self._connection_closed.is_set():
                        if self._connection_fatal:
                            raise RuntimeError(
                                self._connection_error_message
                                or "OpenAI Realtime connection closed unexpectedly."
                            )
                        raise RealtimeReconnectRequired(
                            self._connection_error_message
                            or "OpenAI Realtime connection dropped."
                        )

                    audio_bytes = self._chunk_to_pcm_bytes(chunk)
                    if not audio_bytes:
                        continue

                    try:
                        ws.send(
                            json.dumps(
                                {
                                    "type": "input_audio_buffer.append",
                                    "audio": base64.b64encode(audio_bytes).decode("ascii"),
                                }
                            )
                        )
                    except (
                        websocket_mod.WebSocketConnectionClosedException,
                        websocket_mod.WebSocketTimeoutException,
                        TimeoutError,
                    ) as exc:
                        raise RealtimeReconnectRequired(
                            f"OpenAI Realtime send interrupted: {exc}"
                        ) from exc

                try:
                    ws.send(json.dumps({"type": "input_audio_buffer.commit"}))
                except Exception:
                    pass
                if reader:
                    reader.join(timeout=1.0)
                return
            except RealtimeReconnectRequired as exc:
                if self.stop_event.is_set():
                    break
                logger.warning("Realtime connection dropped; reconnecting: %s", exc)
                self.on_status("Realtime connection lost; reconnecting…")
                self._drain_audio_queue()
                time.sleep(self.RECONNECT_DELAY_SECONDS)
            finally:
                try:
                    if ws is not None:
                        ws.close()
                except Exception:
                    pass

    def _create_client_secret(self) -> str:
        request_body = json.dumps({"session": self.config.session_config()}).encode("utf-8")
        req = urllib_request.Request(
            self.config.client_secrets_url,
            data=request_body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.config.api_key}",
                "Content-Type": "application/json",
                **self._optional_header_map(),
            },
        )
        try:
            with urllib_request.urlopen(req, timeout=15) as response:
                payload = json.loads(response.read().decode("utf-8"))
        except urllib_error.HTTPError as exc:
            body = exc.read().decode("utf-8", errors="ignore")
            raise RuntimeError(
                f"Failed to create OpenAI transcription session ({exc.code}): {body or exc.reason}"
            ) from exc
        except urllib_error.URLError as exc:
            raise RuntimeError(f"Failed to reach OpenAI: {exc.reason}") from exc

        client_secret = payload.get("value")
        if not client_secret:
            client_secret = payload.get("client_secret", {}).get("value")
        if not client_secret:
            raise RuntimeError("OpenAI did not return a realtime client_secret for transcription.")
        return client_secret

    def _optional_header_map(self) -> dict[str, str]:
        headers: dict[str, str] = {}
        if self.config.organization:
            headers["OpenAI-Organization"] = self.config.organization
        if self.config.project:
            headers["OpenAI-Project"] = self.config.project
        return headers

    def _reset_connection_state(self):
        self._partials.clear()
        self._connection_closed.clear()
        self._connection_error_message = ""
        self._connection_fatal = False

    def _drain_audio_queue(self):
        dropped = 0
        while True:
            try:
                self.audio_queue.get_nowait()
                dropped += 1
            except queue.Empty:
                break
        if dropped:
            logger.info("Dropped %d queued audio chunks during Realtime reconnect", dropped)

    def _reader_loop(self, ws, websocket_mod):
        while not self.stop_event.is_set():
            try:
                message = ws.recv()
            except websocket_mod.WebSocketTimeoutException:
                continue
            except websocket_mod.WebSocketConnectionClosedException:
                self._connection_closed.set()
                return
            except Exception as exc:
                self._connection_error_message = f"OpenAI Realtime connection error: {exc}"
                self._connection_closed.set()
                return

            if not message:
                continue
            if isinstance(message, bytes):
                message = message.decode("utf-8", errors="ignore")

            try:
                event = json.loads(message)
            except json.JSONDecodeError:
                logger.debug("Ignoring non-JSON realtime message: %r", message)
                continue

            event_type = event.get("type", "")

            if event_type == "conversation.item.input_audio_transcription.delta":
                item_id = event.get("item_id", "")
                text = self._partials.get(item_id, "") + event.get("delta", "")
                self._partials[item_id] = text
                self.on_partial(text)
                continue

            if event_type == "conversation.item.input_audio_transcription.completed":
                item_id = event.get("item_id", "")
                self._partials.pop(item_id, None)
                transcript = event.get("transcript", "").strip()
                if transcript:
                    self.on_final(transcript)
                self.on_partial("")
                continue

            if event_type == "error":
                error_obj = event.get("error", {})
                message = (
                    error_obj.get("message")
                    or event.get("message")
                    or "OpenAI Realtime error"
                )
                error_type = error_obj.get("type", "")
                self._connection_error_message = message
                self._connection_fatal = error_type in {
                    "invalid_request_error",
                    "authentication_error",
                    "permission_error",
                }
                self._connection_closed.set()
                if self._connection_fatal:
                    self.on_error(message)
                else:
                    logger.warning("OpenAI Realtime server error: %s", message)
                return

            if event_type in {"session.created", "session.updated"}:
                logger.debug("Realtime session event: %s", event_type)

    def _chunk_to_pcm_bytes(self, chunk: np.ndarray) -> bytes:
        if chunk.size == 0:
            return b""

        audio = chunk.astype(np.float32, copy=False)
        if self.input_sample_rate != self.config.input_rate:
            target_len = int(
                len(audio) * self.config.input_rate / self.input_sample_rate
            )
            if target_len <= 0:
                return b""
            audio = np.interp(
                np.linspace(0, len(audio) - 1, target_len),
                np.arange(len(audio)),
                audio,
            ).astype(np.float32)

        pcm = np.clip(audio, -1.0, 1.0)
        return (pcm * 32767.0).astype(np.int16).tobytes()
