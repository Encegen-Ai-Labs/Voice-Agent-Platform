import asyncio
import audioop
import io
import logging
import os
import time
import uuid as _uuid_module
from dataclasses import dataclass
from uuid import UUID
import base64
import json
import websockets

from groq import Groq
from pydub import AudioSegment
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


_SENTENCE_ENDS = {".", "!", "?"}
_MIN_CHUNK_WORDS = 12

_CARTESIA_DEFAULT_VOICE = "79a125e8-cd45-4c13-8a67-188112f4dd22"
_CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY", "")
_CARTESIA_AVAILABLE = bool(_CARTESIA_API_KEY)


@dataclass
class AgentConfig:
    system_prompt: str = (
        "You are a friendly phone assistant. "
        "Reply in ONE complete, natural sentence — 10 to 15 words. "
        "Sound like a real human on a phone call, not a robot. "
        "Always finish the sentence completely — never stop mid-thought. "
        "Never greet or introduce yourself unless asked. "
        "No lists, no bullet points, no filler words like 'Certainly!' or 'Of course!'."
    )
    llm_model: str = "llama-3.3-70b-versatile"
    knowledge_context: str = ""
    language: str = "en"
    tts_voice: str = _CARTESIA_DEFAULT_VOICE
    tts_edge_voice: str = "en-US-AriaNeural"
    agent_id: UUID | None = None
    db: Session | None = None


class VoicePipeline:

    def __init__(self, config: AgentConfig | None = None):
        self.config = config or AgentConfig()

        groq_key = os.getenv("GROQ_API_KEY")
        if not groq_key:
            raise ValueError("GROQ_API_KEY is not set in environment")

        self._groq = Groq(api_key=groq_key)

        self.last_transcript: str | None = None
        self.last_response: str | None = None

 
    def _build_system_prompt(self) -> str:
        parts = [self.config.system_prompt]

        if self.config.knowledge_context:
            parts.append(
                f"\n\nKnowledge Base (use only if directly relevant):\n"
                f"{self.config.knowledge_context[:1500]}"
            )

        parts.append(
            "\n\nREMINDER: ONE complete natural sentence. 10-15 words. "
            "Finish the thought fully — never leave it hanging."
        )

        return "".join(parts)

    def _collect_full_response(
        self,
        transcript: str,
        conversation_history: list | None = None,
    ) -> str:
        messages = [
            {"role": "system", "content": self._build_system_prompt()}
        ]
        if conversation_history:
            messages.extend(conversation_history[-6:])
        messages.append({"role": "user", "content": transcript})

        try:
            completion = self._groq.chat.completions.create(
                messages=messages,
                model=self.config.llm_model,
                stream=False,
                max_tokens=35,
                temperature=0.15,
                stop=["\n", "  "],
            )
            return (completion.choices[0].message.content or "").strip()
        except Exception as exc:
            raise RuntimeError(f"Groq LLM failed: {exc}") from exc

  
    def _split_into_natural_chunks(self, text: str) -> list[str]:
       
        text = text.strip()
        if not text:
            return []

        if len(text.split()) <= _MIN_CHUNK_WORDS:
            return [text]

        chunks: list[str] = []
        buffer = ""

        for char in text:
            buffer += char
            if char in _SENTENCE_ENDS:
                candidate = buffer.strip()
                word_count = len(candidate.split())
                if word_count >= 6:
                    chunks.append(candidate)
                    buffer = ""

        remainder = buffer.strip()
        if remainder:
            if chunks and len(remainder.split()) < 6:
                # Merge short orphan with previous chunk for smooth delivery
                chunks[-1] = chunks[-1].rstrip() + " " + remainder
            else:
                chunks.append(remainder)

        return chunks if chunks else [text]

    async def _synthesize_cartesia(self, text: str) -> bytes:
        
        ws_url = "wss://api.cartesia.ai/tts/websocket"
        headers = {
            "X-API-Key": _CARTESIA_API_KEY,
            "Cartesia-Version": "2024-06-10",
        }

        request_payload = json.dumps({
            "model_id": "sonic-2",
            "transcript": text,
            "voice": {
                "mode": "id",
                "id": self.config.tts_voice,
            },
            "language": "en",
            "context_id": str(_uuid_module.uuid4()),
            "output_format": {
                "container": "raw",
                "encoding": "pcm_s16le",
                "sample_rate": 8000,   
            },
            "continue": False,
        })

        pcm_chunks: list[bytes] = []

        try:
            async with websockets.connect(ws_url, additional_headers=headers) as ws:
                await ws.send(request_payload)

                while True:
                    raw_msg = await ws.recv()
                    msg = json.loads(raw_msg)

                    msg_type = msg.get("type")

                    if msg_type == "chunk":
                        chunk_b64 = msg.get("data", "")
                        if chunk_b64:
                            pcm_chunks.append(base64.b64decode(chunk_b64))
                        if msg.get("done", False):
                            break

                    elif msg_type == "done":
                        break

                    elif msg_type == "error":
                        raise RuntimeError(
                            f"Cartesia error {msg.get('status_code')}: "
                            f"{msg.get('message', msg)}"
                        )

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            raise RuntimeError(f"Cartesia TTS failed: {exc}") from exc

        if not pcm_chunks:
            raise RuntimeError("Cartesia returned no audio chunks")

        raw_pcm = b"".join(pcm_chunks)
        return audioop.lin2ulaw(raw_pcm, 2)

    async def _synthesize_edge_fallback(self, text: str) -> bytes:
        """Edge TTS fallback — used only when CARTESIA_API_KEY is not set."""
        import edge_tts
        communicate = edge_tts.Communicate(
            text, self.config.tts_edge_voice, rate="-8%", pitch="-3Hz"
        )
        mp3_chunks: list[bytes] = []
        async for chunk in communicate.stream():
            if chunk["type"] == "audio":
                mp3_chunks.append(chunk["data"])
        if not mp3_chunks:
            raise RuntimeError("Edge TTS returned no audio")
        mp3_data = b"".join(mp3_chunks)
        audio = AudioSegment.from_file(io.BytesIO(mp3_data), format="mp3")
        audio = audio.set_frame_rate(8000).set_channels(1).set_sample_width(2)
        return audioop.lin2ulaw(audio.raw_data, 2)

    async def _synthesize(self, text: str) -> bytes:
       
        t0 = time.time()
        try:
            if _CARTESIA_AVAILABLE:
                audio = await self._synthesize_cartesia(text)
                logger.info("[TTS] Cartesia %.2fs | %r", time.time() - t0, text)
            else:
                logger.warning(
                    "[TTS] CARTESIA_API_KEY not set — falling back to Edge TTS. "
                    "Set CARTESIA_API_KEY in .env for production."
                )
                audio = await self._synthesize_edge_fallback(text)
                logger.info("[TTS] EdgeTTS %.2fs | %r", time.time() - t0, text)
            return audio
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            if _CARTESIA_AVAILABLE:
                logger.error("[TTS] Cartesia error (%s) — trying Edge TTS fallback", exc)
                try:
                    return await self._synthesize_edge_fallback(text)
                except Exception as fe:
                    raise RuntimeError(f"Both TTS backends failed: {fe}") from fe
            raise RuntimeError(f"TTS failed: {exc}") from exc

    async def stream_audio_sentences(
        self,
        transcript: str,
        conversation_history: list | None = None,
    ):
      
        logger.info("[Pipeline] stream_audio_sentences ENTER")
        pending_tasks: list[tuple[asyncio.Task, str]] = []

        try:
            llm_start = time.time()
            full_response = await asyncio.to_thread(
                self._collect_full_response, transcript, conversation_history
            )
            logger.info(
                "[Pipeline] LLM %.2fs → %r", time.time() - llm_start, full_response
            )

            if not full_response:
                return

            chunks = self._split_into_natural_chunks(full_response)
            logger.info("[Pipeline] %d TTS chunk(s): %s", len(chunks), chunks)

            for chunk in chunks:
                task = asyncio.create_task(
                    self._synthesize(chunk),
                    name=f"tts-{chunk[:25]}",
                )
                pending_tasks.append((task, chunk))

            for task, chunk in pending_tasks:
                audio = await task
                yield chunk, audio

        except asyncio.CancelledError:
            for task, _ in pending_tasks:
                if not task.done():
                    task.cancel()
            if pending_tasks:
                await asyncio.gather(
                    *(t for t, _ in pending_tasks), return_exceptions=True
                )
            raise


    async def synthesize_sentence(self, sentence: str) -> bytes:
        return await self._synthesize(sentence)

    async def process_transcript(
        self,
        transcript: str,
        conversation_history: list | None = None,
    ) -> bytes | None:
        transcript = transcript.strip()
        if not transcript:
            return None
        response_text = await asyncio.to_thread(
            self._collect_full_response, transcript, conversation_history
        )
        self.last_transcript = transcript
        self.last_response = response_text
        return await self._synthesize(response_text)

    def _generate_response_sync(
        self,
        transcript: str,
        conversation_history: list | None = None,
    ) -> str:
        """Alias kept for any external callers."""
        return self._collect_full_response(transcript, conversation_history)


def _is_valid_sentence(s: str) -> bool:
    cleaned = s.replace(".", "").replace("!", "").replace("?", "").strip()
    return len(cleaned) > 2