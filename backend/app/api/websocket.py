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

    async def next_media_chunk() -> bytes | None:
        """Return decoded audio bytes for the next 'media' event, or None for non-media."""
        while True:
            message = await websocket.receive_text()
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
            if chunk is None:
                continue
            audio_buffer.extend(chunk)

            # Keep appending until speech pauses for _PAUSE_TIMEOUT seconds.
            while True:
                try:
                    chunk = await asyncio.wait_for(next_media_chunk(), timeout=_PAUSE_TIMEOUT)
                    if chunk is not None:
                        audio_buffer.extend(chunk)
                except asyncio.TimeoutError:
                    break  # pause detected — process what we have

            min_bytes = int(_MIN_AUDIO_SECONDS * _MULAW_SAMPLE_RATE)
            if len(audio_buffer) >= min_bytes:
                response_audio = await pipeline.process_audio(bytes(audio_buffer))
                await websocket.send_text(json.dumps({
                    "event": "media",
                    "media": {"payload": base64.b64encode(response_audio).decode("utf-8")},
                }))
            else:
                logger.debug("Buffer too short (%d bytes), discarding", len(audio_buffer))

            audio_buffer.clear()

    except WebSocketDisconnect:
        pass
    except Exception as e:
        await websocket.close(code=1011, reason=str(e))
