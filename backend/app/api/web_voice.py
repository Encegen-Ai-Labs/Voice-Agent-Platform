import logging
import asyncio
import json
import base64
import time
from fastapi import APIRouter, Depends, WebSocket, WebSocketDisconnect, Query, status
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from app.core.security import get_current_user
from app.database import get_db
from app.services.agent_service import get_agent
from app.core.browser_stt import BrowserSTTClient
from app.core.pipeline import VoicePipeline, AgentConfig
from app.models.agent import Agent
from app.models.knowledge_base import KnowledgeBase  # 🌟 ADD THIS


logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/api/voice-test", tags=["Voice Test"])

# In-memory session store mapping tokens to active parameters
voice_test_sessions = {}

@router.post("/session")
async def create_voice_test_session(
    payload: dict,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Validates workspace access for the chosen agent and returns a short-lived token.
    """
    workspace_id = current_user["workspace_id"]
    agent_id = payload.get("agent_id")
    
    if not agent_id:
        return JSONResponse(
            content={"error": "Missing agent_id"}, 
            status_code=status.HTTP_400_BAD_REQUEST
        )
        
    # Verify agent belongs to this workspace
    agent = get_agent(db, workspace_id, agent_id)
    if not agent:
        return JSONResponse(
            content={"error": "Agent not found in this workspace"}, 
            status_code=status.HTTP_404_NOT_FOUND
        )

    # Generate a simple secure token string
    session_token = f"test_token_{int(time.time())}_{agent_id}"
    
    voice_test_sessions[session_token] = {
        "workspace_id": workspace_id,
        "agent_id": agent_id,
        "expires_at": time.time() + 300  # 5 minutes expiration
    }
    
    return {"token": session_token}


@router.websocket("/ws")
async def browser_voice_ws(
    websocket: WebSocket,
    token: str = Query(...),
    db: Session = Depends(get_db)
):
    """
    WebSocket endpoint ingesting binary PCM16 16kHz from browser 
    and returning text transcripts + Cartesia audio base64 JSON.
    """
    await websocket.accept()
    logger.info("[WebVoice] WebSocket connection attempt with token.")

    # 1. Validate Token (Safe Read Only)
    session = voice_test_sessions.get(token)
    if not session or time.time() > session["expires_at"]:
        logger.warning("[WebVoice] Invalid or expired session token. Closing.")
        await websocket.close(code=4003)
        return

    workspace_id = session["workspace_id"]
    agent_id = session["agent_id"]

    # Fetch agent configuration explicitly to fix the undefined 'agent' bug
    agent = get_agent(db, workspace_id, agent_id)
    if not agent:
        logger.error("[WebVoice] Stored agent not found upon socket initialization.")
        await websocket.close(code=4004)
        return

    # 2. Setup State Tracking Flags (CRITICAL: Placed BEFORE inner function definitions)
    interrupt_event = asyncio.Event()
    ai_speaking = False
    conversation_history = []
    
    last_processed_sentence = None
    last_processed_time = 0.0
    response_task = None
    
    # Initialize pipeline with configuration extracted from DB
    # Initialize pipeline with configuration extracted from DB
    selected_model = agent.llm_model

    # Hot-swap old deprecated versatile string seamlessly
    if selected_model == "llama-3.1-8b-versatile":
        selected_model = "llama-3.3-70b-versatile"

    # 🌟 FETCH KNOWLEDGE BASE DOCUMENTS
    kb_entries = (
        db.query(KnowledgeBase)
        .filter(KnowledgeBase.agent_id == agent.id)
        .order_by(KnowledgeBase.created_at.desc())
        .limit(3)
        .all()
    )
    # Stitch the retrieved documents into a single context string
    compiled_knowledge = "\n".join(e.content for e in kb_entries if e.content)

    agent_config = AgentConfig(
            system_prompt=agent.system_prompt,
            llm_model=selected_model,
            knowledge_context=compiled_knowledge,
            language=getattr(agent, "language", "en"),
            tts_voice=agent.voice or AgentConfig.tts_voice,
            agent_id=agent.id,
            db=db,
        )
    logger.info(
            "[WebVoice] Using voice: %s",
            agent_config.tts_voice,
        )

    pipeline = VoicePipeline(config=agent_config)
    
    async def run_response_pipeline(turn_transcript: str, history_snapshot: list):
        """Runs the LLM + TTS pipeline concurrently without freezing execution loops"""
        nonlocal ai_speaking, conversation_history
        ai_speaking = True
        assistant_parts = []
        
        try:
            async for sentence, _ in pipeline.stream_audio_sentences(turn_transcript, history_snapshot):
                if interrupt_event.is_set():
                    break
                    
                assistant_parts.append(sentence)
                
                # Push real-time text delta to frontend
                await websocket.send_json({"type": "text_delta", "text": sentence})

                # Stream matching browser-compatible raw audio frames
                async for chunk in pipeline._synthesize_cartesia_stream_browser(sentence):
                    if interrupt_event.is_set():
                        break
                    
                    await websocket.send_json({
                        "type": "audio",
                        "payload": base64.b64encode(chunk).decode("utf-8")
                    })
                    
            if assistant_parts and not interrupt_event.is_set():
                full_response = " ".join(assistant_parts)
                conversation_history.append({"role": "user", "content": turn_transcript})
                conversation_history.append({"role": "assistant", "content": full_response})
                conversation_history = conversation_history[-6:]
                
        except Exception as err:
            logger.error("[WebVoice WS] Pipeline streaming loop broke: %s", err)
        finally:
            ai_speaking = False

    async def on_browser_transcript(transcript: str, event_type: str) -> None:
        """Fortified turn detection callback handler with absolute task shielding"""
        nonlocal ai_speaking, interrupt_event, conversation_history
        nonlocal last_processed_sentence, last_processed_time, response_task
        
        transcript = transcript.strip()
        if not transcript:
            return

        # 1. Drop duplicate stream updates immediately
        if event_type == "Update":
            if transcript == last_processed_sentence:
                return
            last_processed_sentence = transcript
            return  # Partial updates should never spin up pipelines

        logger.info("[WebVoice STT] [%s] %r", event_type, transcript)

        # 2. Handle Live Audio Interruption / Barge-in
        if ai_speaking and event_type not in ("EndOfTurn", "EagerEndOfTurn"):
            # STABILIZATION FILTER: Drop short bleed-over single-word hallucinations
            if len(transcript.split()) <= 1 or transcript.lower() in ["yeah", "two", "and", "four"]:
                return

            logger.info("[WebVoice WS] Legitimate Barge-in detected — aborting generation threads")
            interrupt_event.set()
            if response_task and not response_task.done():
                response_task.cancel()
            await websocket.send_json({"type": "clear"})
            ai_speaking = False
            return

        # 3. Only process definitive turn signals
        if event_type in ("EndOfTurn", "EagerEndOfTurn"):
            await websocket.send_json({"type": "user_transcript", "text": transcript})
            
            last_update_transcript = ""
        else:
            return

        interrupt_event.clear()
        ai_speaking = True

        # 4. TRIPLE-LOCK GATEKEEPER: Drop duplicate execution storms safely
        now = time.time()
        time_elapsed = now - last_processed_time

        # Filter out short room-noise/ambient feedback pops at the end of a turn
        if len(transcript.split()) <= 1 and transcript.lower() in ["yeah", "two", "and", "four"]:
            logger.info("[WebVoice WS] Dropped trailing microphone acoustic bleed turn.")
            return

        # If the text is identical and arrived within 1.5 seconds of the last turn, bypass
        if transcript == last_processed_sentence and time_elapsed < 1.5:
            logger.info("[WebVoice WS] Dropped trailing duplicate %s signal safely.", event_type)
            return

        # Lock this phrase and timestamp immediately
        last_processed_sentence = transcript
        last_processed_time = now

        # 5. Clean up genuine historical tasks from a previous, older conversation turn
        if response_task and not response_task.done():
            response_task.cancel()
            try:
                await asyncio.wait_for(response_task, timeout=0.1)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass

        interrupt_event.clear()
        history_snapshot = list(conversation_history)
        
        # 6. Instantiate background task using global running loop context reference
        loop = asyncio.get_running_loop()
        response_task = loop.create_task(
            run_response_pipeline(transcript, history_snapshot)
        )

    # Instantiate your separated 16kHz STT client
    browser_stt = BrowserSTTClient(on_transcript=on_browser_transcript)
    await browser_stt.connect()
    logger.info("[WebVoice] Browser STT Engine fully initialized.")

    # Consume token from cache map only after successful infrastructure boot
    voice_test_sessions.pop(token, None)

    # 3. Main Binary Ingestion Loop
    try:
        while True:
            # Handles raw binary websocket frames containing PCM16 Mono 16kHz audio data
            message = await websocket.receive()
            
            if "bytes" in message:
                audio_chunk = message["bytes"]
                if audio_chunk:
                    await browser_stt.send_audio(audio_chunk)
            elif "text" in message:
                try:
                    data = json.loads(message["text"])
                    if data.get("command") == "stop":
                        break
                except json.JSONDecodeError:
                    continue
                    
    except WebSocketDisconnect:
        logger.info("[WebVoice WS] Browser client disconnected session cleanly.")
    except Exception as exc:
        logger.error("[WebVoice WS] Runtime error in ingestion loop: %s", exc)
    finally:
        if response_task and not response_task.done():
            response_task.cancel()
        try:
            await browser_stt.close()
        except Exception:
            pass
        logger.info("[WebVoice WS] Cleaned up voice session assets.")