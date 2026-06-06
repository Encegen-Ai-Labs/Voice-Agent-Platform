import audioop
import asyncio
import json
import base64
import logging
import traceback
import time
from datetime import datetime, timezone
from app.schemas.call import CallUpdate
from app.services.call_service import update_call

from fastapi import (
    APIRouter,
    WebSocket,
    WebSocketDisconnect
)

from app.core.pipeline import (
    VoicePipeline,
    AgentConfig
)

import os
import wave

from uuid import UUID

from app.database import SessionLocal
from app.models.call import Call

from app.models.agent import Agent

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter(tags=["WebSocket"])



# Twilio sends mulaw at 8000 Hz, 1 byte per sample
_MULAW_SAMPLE_RATE = 8000

_MIN_AUDIO_SECONDS = 0.5
_SPEECH_ENERGY_THRESHOLD = 100
_SILENCE_CHUNKS = 8


@router.websocket("/ws/call")
async def websocket_call(
    websocket: WebSocket
):

    await websocket.accept()

    call_id = websocket.query_params.get(
        "call_id"
    )

    pipeline = VoicePipeline(
    AgentConfig()
    )    
    twilio_call_sid = None

    print("WEBSOCKET CALL_ID:", call_id)
    logger.info("WebSocket call_id=%s", call_id)

    audio_buffer = bytearray()

    full_recording = bytearray()

    conversation_history = []

    stream_sid = None

    ai_speaking = False

    _DISCONNECTED = object()

    async def next_media_chunk():
        nonlocal stream_sid

        while True:

            try:

                message = await websocket.receive_text()

            except (
                WebSocketDisconnect,
                RuntimeError
            ):

                logger.info(
                    "WebSocket disconnected"
                )

                return _DISCONNECTED

            data = json.loads(message)

            event = data.get("event")

            if event == "media":

                return base64.b64decode(
                    data["media"]["payload"]
                )

            elif event in (
                "connected",
                "start",
                "stop"
            ):
                if event == "start":

                    stream_sid = data.get(
                        "streamSid"
                    )

                    print("FULL START EVENT DATA:", data)
                    logger.info("Full start event: %s", data)

                    nonlocal twilio_call_sid
                    twilio_call_sid = data.get(
                        "callSid"
                    )
                    if not twilio_call_sid:
                        start_data = data.get("start", {})
                        twilio_call_sid = start_data.get("callSid")
                        print("EXTRACTED FROM START SUBOBJECT:", twilio_call_sid)
                    try:

                        db = SessionLocal()

                        call = db.query(Call).filter(
                            Call.twilio_call_sid == twilio_call_sid
                        ).first()

                        if call:

                            agent = db.query(Agent).filter(
                                Agent.id == call.agent_id,
                                Agent.workspace_id == call.workspace_id
                            ).first()

                            if agent:

                                pipeline.config.system_prompt = (
                                    agent.system_prompt
                                    or AgentConfig.system_prompt
                                )

                                pipeline.config.llm_model = (
                                    agent.llm_model
                                    or AgentConfig.llm_model
                                )

                                pipeline.config.language = (
                                    agent.language
                                    or AgentConfig.language
                                )

                                pipeline.config.agent_id = agent.id

                                pipeline.config.db = db

                    except Exception as e:

                        logger.error(
                            "KB pipeline init failed: %s",
                            e
                        )
                    finally:

                        if 'db' in locals():

                            db.close()

                    print(
                        "STREAM SID:",
                        stream_sid
                    )

                    print(
                        "TWILIO CALL SID:",
                        twilio_call_sid
                    )

                print(
                    f"TWILIO EVENT: {event} at {time.time()}"
                )

                logger.info(
                    "Twilio event: %s",
                    event
                )

                if event == "stop":

                    return _DISCONNECTED

                return None

    try:

        silence_count = 0

        while True:

            chunk = await next_media_chunk()

            if chunk is _DISCONNECTED:

                print(
                    f"DISCONNECTED at {time.time()}"
                )
                print("SAVING RECORDING...")
                print("RECORDING BYTES:", len(full_recording))

                break

            if chunk is None:

                continue
            full_recording.extend(chunk)
            if ai_speaking:

                continue

            
            pcm_chunk = audioop.ulaw2lin(
                chunk,
                2
            )

            energy = audioop.rms(
                pcm_chunk,
                2
            )

        
            if energy > _SPEECH_ENERGY_THRESHOLD:

                audio_buffer.extend(chunk)

                silence_count = 0

                logger.debug(
                    "Speech: energy=%d buffer=%d bytes",
                    energy,
                    len(audio_buffer)
                )

            elif len(audio_buffer) > 0:

                silence_count += 1

                logger.debug(
                    "Silence %d/%d: energy=%d",
                    silence_count,
                    _SILENCE_CHUNKS,
                    energy
                )

                if silence_count >= _SILENCE_CHUNKS:

                    logger.info(
                        "Silence detected, buffer=%d bytes",
                        len(audio_buffer)
                    )

                    min_bytes = int(
                        _MIN_AUDIO_SECONDS *
                        _MULAW_SAMPLE_RATE
                    )

                    if len(audio_buffer) >= min_bytes:
       
                        try:

                            logger.info(
                                "Processing utterance, %d bytes",
                                len(audio_buffer)
                            )
                            print("BUFFER SIZE:", len(audio_buffer))

                            print(
                                f"PIPELINE START: {time.time()}"
                            )

                            start = time.time()

                            async def run_pipeline():

                                return await pipeline.process_audio(
                                    bytes(audio_buffer),
                                    conversation_history
                                )

                            pipeline_task = asyncio.create_task(
                                run_pipeline()
                            )

                            

                            response_audio = await pipeline_task

                            if response_audio is None:

                                audio_buffer.clear()

                                silence_count = 0

                                continue

                           
                            ai_speaking = True

                            try:

                                chunk_size = 1600

                                for i in range(
                                    0,
                                    len(response_audio),
                                    chunk_size
                                ):

                                    chunk = response_audio[
                                        i:i + chunk_size
                                    ]

                                    await websocket.send_json({
                                        "event": "media",
                                        "streamSid": stream_sid,
                                        "media": {
                                            "payload": base64.b64encode(
                                                chunk
                                            ).decode("utf-8")
                                        }
                                    })

                                    await asyncio.sleep(0.02)

                                full_recording.extend(response_audio)
                                print(
                                    "APPENDED AI RESPONSE TO RECORDING:",
                                    len(response_audio),
                                    "bytes"
                                )

                            finally:

                                await asyncio.sleep(0.5)

                                ai_speaking = False

                            if (
                                pipeline.last_transcript
                                and
                                pipeline.last_response
                            ):

                                conversation_history.append({
                                    "role": "user",
                                    "content": pipeline.last_transcript
                                })

                                conversation_history.append({
                                    "role": "assistant",
                                    "content": pipeline.last_response
                                })

                                conversation_history = (
                                    conversation_history[-6:]
                                )

                            if response_audio is None:

                                audio_buffer.clear()

                                silence_count = 0

                                continue

                            elapsed = (
                                time.time() - start
                            )

                            print(
                                f"PIPELINE END: took {elapsed:.2f} seconds"
                            )

                            logger.info(
                                "Pipeline took %.2f seconds, response audio: %d bytes",
                                elapsed,
                                len(response_audio)
                            )


                        except Exception as e:

                            logger.error(
                                "Pipeline error: %s\n%s",
                                e,
                                traceback.format_exc()
                            )

                    else:

                        logger.info(
                            "Buffer too short (%d bytes), discarding",
                            len(audio_buffer)
                        )

                    audio_buffer.clear()

                    silence_count = 0
            
        if full_recording:

            try:

                    cwd = os.getcwd()
                    print("SAVE RECORDING: twilio_call_sid=", twilio_call_sid)
                    print("SAVE RECORDING: recording bytes=", len(full_recording))
                    print("SAVE RECORDING: cwd=", cwd)
                    logger.info(
                        "Saving recording for twilio_call_sid=%s len=%d cwd=%s",
                        twilio_call_sid,
                        len(full_recording),
                        cwd,
                    )

                    recordings_dir = os.path.abspath(
                        "recordings"
                    )

                    os.makedirs(
                        recordings_dir,
                        exist_ok=True
                    )

                    recording_name = (
                        f"{twilio_call_sid}.wav"
                        if twilio_call_sid
                        else f"unknown_{int(time.time())}.wav"
                    )

                    recording_path = os.path.join(
                        recordings_dir,
                        recording_name
                    )

                    with wave.open(
                        recording_path,
                        "wb"
                        ) as wav_file:

                            pcm_audio = audioop.ulaw2lin(
                                bytes(full_recording),
                                2
                            )
                            wav_file.setnchannels(1)
                            wav_file.setsampwidth(2)

                            wav_file.setframerate(8000)

                            wav_file.writeframes(
                                pcm_audio
                            )

                            print("WAV FILE WRITTEN:", recording_path)

                    if twilio_call_sid:
                        recording_db = SessionLocal()

                        try:

                            call = recording_db.query(Call).filter(
                                Call.twilio_call_sid == twilio_call_sid
                            ).first()

                            if call:
                                try:

                                    end_time = datetime.utcnow()

                                    duration = int(
                                        (
                                            end_time - call.start_time
                                        ).total_seconds()
                                    )

                                    update_data = CallUpdate(
                                        status="completed",
                                        recording_url=recording_path,
                                        end_time=end_time,
                                        duration=duration
                                    )

                                    print("UPDATE DATA:", update_data)

                                    updated_call = update_call(
                                        recording_db,
                                        workspace_id=call.workspace_id,
                                        call_id=call.id,
                                        data=update_data
                                    )
                                    recording_db.commit()

                                    recording_db.refresh(updated_call)

                                    print("DB COMMIT SUCCESS")

                                    print("UPDATED CALL:", updated_call)

                                except Exception as e:

                                    print("CALL UPDATE FAILED:", str(e))

                                    
                                    print(traceback.format_exc())
                            else:
                                print(
                                    "RECORDING SAVED: no call found for twilio_call_sid=",
                                    twilio_call_sid,
                                    "; file saved to",
                                    recording_path,
                                )
                                logger.warning(
                                    "Recording saved but no call found for twilio_call_sid=%s to %s",
                                    twilio_call_sid,
                                    recording_path,
                                )

                        finally:

                            recording_db.close()
                    else:
                        print(
                            "RECORDING SAVED: no twilio_call_sid; file saved to",
                            recording_path,
                        )
                        logger.warning(
                            "Recording saved without twilio_call_sid to %s",
                            recording_path,
                        )

            except Exception as e:
                print("RECORDING SAVE ERROR:", str(e))
                print(traceback.format_exc())
                logger.error(
                    "Recording save failed: %s",
                    e
                )
        else:
            print("RECORDING NOT SAVED: no recording bytes")
            logger.warning(
                "Recording not saved because full_recording is empty"
            )
    except Exception as e:

        logger.error(
            "Websocket fatal error: %s\n%s",
            e,
            traceback.format_exc()
        )
