import audioop
import io
import os
import time

from uuid import UUID

from sqlalchemy.orm import Session

from app.models.knowledge_base import (
    KnowledgeBase
)

from dataclasses import dataclass

from deepgram import DeepgramClient
from groq import Groq

import gtts

from pydub import AudioSegment


@dataclass
class AgentConfig:

    system_prompt: str = (
    "You are a real-time voice AI assistant. "
    "Keep responses under 15 words. "
    "Be concise, natural, and conversational. "
    "Do not explain too much unless asked."
)

    llm_model: str = "llama-3.3-70b-versatile"

    language: str = "en"

    agent_id: UUID | None = None

    db: Session | None = None


class VoicePipeline:

    def __init__(
        self,
        config: AgentConfig | None = None
    ):

        self.config = config or AgentConfig()

        deepgram_key = os.getenv(
            "DEEPGRAM_API_KEY"
        )

        groq_key = os.getenv(
            "GROQ_API_KEY"
        )

        self.last_transcript = None

        self.last_response = None

        if not deepgram_key:

            raise ValueError(
                "DEEPGRAM_API_KEY is not set in environment"
            )

        if not groq_key:

            raise ValueError(
                "GROQ_API_KEY is not set in environment"
            )

        self._deepgram = DeepgramClient(
            api_key=deepgram_key
        )

        self._groq = Groq(
            api_key=groq_key
        )

    def _transcribe(
        self,
        audio_bytes: bytes
    ) -> str | None:

        try:

            response = (
                self._deepgram.listen.v1.media.transcribe_file(
                    request=audio_bytes,
                    model="nova-2",
                    smart_format=True,
                    language=self.config.language,
                    encoding="mulaw",
                    request_options={
                        "additional_query_parameters": {
                            "sample_rate": 8000
                        }
                    },
                )
            )

            channels = response.results.channels

            if not channels:

                return None

            alternatives = channels[0].alternatives

            if not alternatives:

                return None

            transcript = alternatives[0].transcript

        except Exception as e:

            raise RuntimeError(
                f"STT failed: {e}"
            ) from e

        if not transcript.strip():

            return None

        return transcript
    
    def _build_system_prompt(self) -> str:

        base_prompt = self.config.system_prompt

        if not self.config.agent_id:

            return base_prompt

        if not self.config.db:

            return base_prompt

        knowledge_entries = (
            self.config.db.query(KnowledgeBase)
            .filter(
                KnowledgeBase.agent_id
                == self.config.agent_id
            )
            .order_by(
                KnowledgeBase.created_at.desc()
            )
            .limit(3)
            .all()
        )

        if not knowledge_entries:

            return base_prompt

        knowledge_content = "\n\n".join(
            entry.content
            for entry in knowledge_entries
        )

        return (
            f"{base_prompt}\n\n"
            f"Knowledge Base:\n"
            f"{knowledge_content}"
        )

    def _generate_response(
        self,
        transcript: str,
        conversation_history: list | None = None
    ) -> str:

        try:

            messages = [
                {
                    "role": "system",
                    "content": self._build_system_prompt()
                }
            ]

            if conversation_history:

                messages.extend(
                    conversation_history
                )

            messages.append({
                "role": "user",
                "content": transcript
            })

            completion = (
                self._groq.chat.completions.create(
                    messages=messages,
                    model=self.config.llm_model,
                )
            )

            return (
                completion
                .choices[0]
                .message
                .content
            )

        except Exception as e:

            raise RuntimeError(
                f"LLM failed: {e}"
            ) from e

    async def _synthesize(
        self,
        text: str
    ) -> bytes:

        try:

            mp3_buf = io.BytesIO()

            tts = gtts.gTTS(
                text=text,
                lang=self.config.language
            )

            tts.write_to_fp(
                mp3_buf
            )

            mp3_buf.seek(0)

            audio = AudioSegment.from_file(
                mp3_buf,
                format="mp3"
            )

            audio = (
                audio
                .set_frame_rate(8000)
                .set_channels(1)
                .set_sample_width(2)
            )

            pcm_buf = io.BytesIO()

            audio.export(
                pcm_buf,
                format="s16le"
            )

            pcm_bytes = pcm_buf.getvalue()

            mulaw_audio = audioop.lin2ulaw(
                pcm_bytes,
                2
            )

            return mulaw_audio

        except Exception as e:

            raise RuntimeError(
                f"TTS failed: {e}"
            ) from e

    async def process_audio(
        self,
        audio_bytes: bytes,
        conversation_history: list | None = None
    ) -> bytes | None:

        total_start = time.time()

        stt_start = time.time()

        transcript = self._transcribe(
            audio_bytes
        )

        if transcript is None:

            print(
                "EMPTY TRANSCRIPT DETECTED"
            )

            return None

        print(
            f"STT TOOK: {time.time() - stt_start:.2f}s"
        )

        print(
            f"TRANSCRIPT: {transcript}"
        )

        llm_start = time.time()

        self.last_transcript = transcript

        response_text = self._generate_response(
            transcript,
            conversation_history
        )

        self.last_response = response_text

        print(
            f"LLM TOOK: {time.time() - llm_start:.2f}s"
        )

        print(
            f"LLM RESPONSE: {response_text}"
        )

        tts_start = time.time()

        audio_out = await self._synthesize(
            response_text
        )

        print(
            f"TTS TOOK: {time.time() - tts_start:.2f}s"
        )

        print(
            f"TOTAL PIPELINE: {time.time() - total_start:.2f}s"
        )

        return audio_out