import audioop
import asyncio
import json
import base64
import logging
import traceback
import time
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from app.core.pipeline import VoicePipeline, AgentConfig

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter(tags=["WebSocket"])

pipeline = VoicePipeline(AgentConfig())

# Twilio sends mulaw at 8000 Hz, 1 byte per sample
_MULAW_SAMPLE_RATE = 8000
_MIN_AUDIO_SECONDS = 0.5    # discard buffers shorter than this
_SPEECH_ENERGY_THRESHOLD = 100  # audioop.rms value above which a chunk counts as speech
_SILENCE_CHUNKS = 8             # consecutive silent chunks before processing (~0.16 s)


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
                logger.info("WebSocket disconnected")
                return _DISCONNECTED
            data = json.loads(message)
            event = data.get("event")
            if event == "media":
                return base64.b64decode(data["media"]["payload"])
            elif event in ("connected", "start", "stop"):
                print(f"TWILIO EVENT: {event} at {time.time()}")
                logger.info("Twilio event: %s", event)
                if event == "stop":
                    return _DISCONNECTED
                return None

    try:
        silence_count = 0

        while True:
            chunk = await next_media_chunk()
            if chunk is _DISCONNECTED:
                print(f"DISCONNECTED at {time.time()}")
                break
            if chunk is None:
                continue

            energy = audioop.rms(chunk, 1)

            if energy > _SPEECH_ENERGY_THRESHOLD:
                audio_buffer.extend(chunk)
                silence_count = 0
                logger.debug("Speech: energy=%d buffer=%d bytes", energy, len(audio_buffer))
            elif len(audio_buffer) > 0:
                silence_count += 1
                logger.debug("Silence %d/%d: energy=%d", silence_count, _SILENCE_CHUNKS, energy)

                if silence_count >= _SILENCE_CHUNKS:
                    logger.info("Silence detected, buffer=%d bytes", len(audio_buffer))
                    min_bytes = int(_MIN_AUDIO_SECONDS * _MULAW_SAMPLE_RATE)
                    if len(audio_buffer) >= min_bytes:
                        try:
                            logger.info("Processing utterance, %d bytes", len(audio_buffer))
                            print(f"PIPELINE START: {time.time()}")
                            start = time.time()

                            async def run_pipeline():
                                return await pipeline.process_audio(bytes(audio_buffer))

                            pipeline_task = asyncio.create_task(run_pipeline())
                            while not pipeline_task.done():
                                try:
                                    await websocket.send_text(json.dumps({"event": "mark", "mark": {"name": "keep-alive"}}))
                                except Exception:
                                    pass
                                await asyncio.sleep(0.5)
                            response_audio = await pipeline_task

                            elapsed = time.time() - start
                            print(f"PIPELINE END: took {elapsed:.2f} seconds")
                            logger.info("Pipeline took %.2f seconds, response audio: %d bytes", elapsed, len(response_audio))
                            await websocket.send_text(json.dumps({
                                "event": "media",
                                "media": {"payload": base64.b64encode(response_audio).decode("utf-8")},
                            }))
                        except Exception as e:
                            logger.error("Pipeline error: %s\n%s", e, traceback.format_exc())
                    else:
                        logger.info("Buffer too short (%d bytes), discarding", len(audio_buffer))

                    audio_buffer.clear()
                    silence_count = 0

    except Exception:
        pass