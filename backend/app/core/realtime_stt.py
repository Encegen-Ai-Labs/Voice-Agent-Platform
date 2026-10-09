import asyncio
import os
from typing import Callable, Coroutine, Any
import time
from deepgram import AsyncDeepgramClient
from deepgram.listen.v2.types import ListenV2TurnInfo, ListenV2FatalError


class RealtimeSTTClient:
   
    def __init__(
        self,
        on_transcript: Callable[[str, str], Coroutine[Any, Any, None]] | None = None,
    ):
        api_key = os.getenv("DEEPGRAM_API_KEY")
        if not api_key:
            raise ValueError("DEEPGRAM_API_KEY is not set in environment")

        self._client = AsyncDeepgramClient(api_key=api_key)
        self._on_transcript = on_transcript

        self._conn = None
        self._ctx = None
        self._listen_task: asyncio.Task | None = None
        self._connected = False
        self._connect_lock = asyncio.Lock()

        self._callback_tasks: set[asyncio.Task] = set()

    async def connect(self) -> None:
        
        async with self._connect_lock:
            if self._connected:
                return

            try:
                start = time.time()
                self._ctx = self._client.listen.v2.connect(
                    model="flux-general-en", 
                    encoding="mulaw",
                    sample_rate=8000,
                    eager_eot_threshold=0.6,
                )
                self._conn = await self._ctx.__aenter__()
                self._connected = True
                print("[RealtimeSTT] Connected to Deepgram v2")
                print(
                    f"[RealtimeSTT] Connect took "
                    f"{time.time() - start:.2f}s"
                )

                self._listen_task = asyncio.create_task(
                    self._listen_loop(),
                    name="deepgram-v2-listener",
                )

                # Warm up the model with ~1s of silent mulaw audio so the
                # FIRST real utterance doesn't pay Deepgram's cold-start cost.
                # This is AWAITED here (not fire-and-forget) because if real
                # Twilio audio starts flowing in parallel with the warmup
                # silence, the two interleave on the same connection and
                # Deepgram receives a jumbled, non-continuous audio stream —
                # which was making the FIRST turn's transcription stall.
                # connect() already runs in the background relative to the
                # rest of websocket setup, so this short, bounded wait does
                # not block anything user-visible (the prerecorded greeting
                # is still playing during this window).
                await self._send_warmup_audio()

            except Exception as exc:
                print(f"[RealtimeSTT] connect() failed: {exc}")
                await self._cleanup()

    async def _send_warmup_audio(self) -> None:
        """Send ~1s of silent mulaw audio in small chunks to pre-warm
        Deepgram's model. Never raises — any failure is just logged.
        """
        try:
            _MULAW_SILENCE_BYTE = 0xFF
            _CHUNK_SIZE = 160          # matches normal Twilio chunk size
            _CHUNKS_PER_SECOND = 50    # 160 bytes * 50 = 8000 bytes/sec @ 8kHz mulaw
            _WARMUP_SECONDS = 1
            silent_chunk = bytes([_MULAW_SILENCE_BYTE]) * _CHUNK_SIZE

            warmup_start = time.time()
            for _ in range(_CHUNKS_PER_SECOND * _WARMUP_SECONDS):
                if not self._connected:
                    # Connection dropped or was closed before warmup finished — bail quietly
                    return
                await self.send_audio(silent_chunk)
                await asyncio.sleep(0.02)  # pace it like real-time audio (20ms/chunk)

            print(
                f"[RealtimeSTT] Warmup audio sent in "
                f"{time.time() - warmup_start:.2f}s"
            )
        except Exception as exc:
            # Warmup is best-effort only — never let it affect the real call
            print(f"[RealtimeSTT] Warmup send failed (non-fatal): {exc}")

    async def send_audio(self, audio_chunk: bytes) -> None:
        
        if not self._connected or self._conn is None:
            return
        try:
            await self._conn.send_media(audio_chunk)
        except Exception as exc:
            print(f"[RealtimeSTT] send_audio error: {exc}")
            self._connected = False

    async def close(self) -> None:
       
        await self._cleanup()

    async def _listen_loop(self) -> None:
        try:
            while self._connected:
                message = await self._conn.recv()
                print(
                    f"[PERF] Deepgram message received "
                    f"at {time.time():.3f}"
                )

                transcript = ""
                event_type = "UNKNOWN"

                if isinstance(message, ListenV2TurnInfo):
                    transcript = (message.transcript or "").strip()
                    event_type = str(message.event)

                elif isinstance(message, ListenV2FatalError):
                    print(f"[RealtimeSTT FATAL] {message}")
                    self._connected = False
                    break

                elif hasattr(message, "transcript"):
                    transcript = (getattr(message, "transcript", "") or "").strip()
                    event_type = str(getattr(message, "event", "UNKNOWN"))

                elif isinstance(message, dict):
                    transcript = (message.get("transcript", "") or "").strip()
                    event_type = str(message.get("event", "UNKNOWN"))

                if event_type == "TurnResumed":
                    print(f"[RealtimeSTT] TurnResumed — suppressing, waiting for real EndOfTurn")
                    continue

                if transcript:
                    print(
                        f"[RealtimeSTT] {event_type}: "
                        f"{transcript!r} "
                        f"at {time.time():.3f}"
                    )

                if not transcript:
                    continue

                if self._on_transcript:
                    self._fire_callback(transcript, event_type)

        except asyncio.CancelledError:
            pass
        except Exception as exc:
            print(f"[RealtimeSTT LOOP ERROR] {exc}")
            self._connected = False

    def _fire_callback(self, transcript: str, event_type: str) -> None:
     
        task = asyncio.create_task(
            self._on_transcript(transcript, event_type),
            name=f"stt-cb-{event_type}",
        )
        self._callback_tasks.add(task)
        task.add_done_callback(self._callback_tasks.discard)

    async def _cleanup(self) -> None:
        self._connected = False

        for task in list(self._callback_tasks):
            if not task.done():
                task.cancel()
        if self._callback_tasks:
            await asyncio.gather(*self._callback_tasks, return_exceptions=True)
        self._callback_tasks.clear()

        # Cancel the listener task
        if self._listen_task and not self._listen_task.done():
            self._listen_task.cancel()
            try:
                await self._listen_task
            except (asyncio.CancelledError, Exception):
                pass
        self._listen_task = None

        if self._conn is not None:
            try:
                await self._conn.send_close_stream()
            except Exception:
                pass

        if self._ctx is not None:
            try:
                await self._ctx.__aexit__(None, None, None)
            except Exception:
                pass

        self._ctx = None
        self._conn = None
        print("[RealtimeSTT] Closed")