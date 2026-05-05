import asyncio
import json
import base64
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.pipeline import VoicePipeline, AgentConfig

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])

pipeline = VoicePipeline(AgentConfig())

# Twilio sends mulaw at 8000 Hz, 1 byte per sample
_MULAW_SAMPLE_RATE = 8000
_PAUSE_TIMEOUT = 1.0        # seconds of silence before processing
_MIN_AUDIO_SECONDS = 0.5    # discard buffers shorter than this


@router.websocket("/ws/call")
async def websocket_call(websocket: WebSocket):
    await websocket.accept()
    audio_buffer = bytearray()

    _DISCONNECTED = object()  # sentinel: connection closed

    async def next_media_chunk():
        """Return audio bytes for 'media', None for ignorable events, _DISCONNECTED on close."""
        while True:
            try:
                message = await websocket.receive_text()
            except (WebSocketDisconnect, RuntimeError):
                return _DISCONNECTED
            data = json.loads(message)
            event = data.get("event")
            if event == "media":
                return base64.b64decode(data["media"]["payload"])
            elif event in ("connected", "start", "stop"):
                logger.info("Twilio event: %s", event)
                return None

    try:
        while True:
            # Block until the first chunk of a new utterance arrives.
            chunk = await next_media_chunk()
            if chunk is _DISCONNECTED:
                break
            if chunk is None:
                continue
            audio_buffer.extend(chunk)

            # Keep appending until speech pauses for _PAUSE_TIMEOUT seconds.
            disconnected = False
            while True:
                try:
                    chunk = await asyncio.wait_for(next_media_chunk(), timeout=_PAUSE_TIMEOUT)
                    if chunk is _DISCONNECTED:
                        disconnected = True
                        break
                    if chunk is not None:
                        audio_buffer.extend(chunk)
                except asyncio.TimeoutError:
                    break  # pause detected — process what we have
            if disconnected:
                break

            min_bytes = int(_MIN_AUDIO_SECONDS * _MULAW_SAMPLE_RATE)
            if len(audio_buffer) >= min_bytes:
                try:
                    response_audio = await pipeline.process_audio(bytes(audio_buffer))
                    await websocket.send_text(json.dumps({
                        "event": "media",
                        "media": {"payload": base64.b64encode(response_audio).decode("utf-8")},
                    }))
                except Exception as e:
                    logger.error("Pipeline error: %s", e)
            else:
                logger.debug("Buffer too short (%d bytes), discarding", len(audio_buffer))

            audio_buffer.clear()

    except Exception:
        pass
