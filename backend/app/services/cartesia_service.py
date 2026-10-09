import httpx
import os
from app.core.config import settings


class CartesiaService:
    BASE_URL = "https://api.cartesia.ai"

    @classmethod
    async def get_voices(cls):
        headers = {
            "X-API-Key": os.getenv("CARTESIA_API_KEY"),
            "Cartesia-Version": "2024-06-10",
        }

        async with httpx.AsyncClient(timeout=20) as client:
            response = await client.get(
                f"{cls.BASE_URL}/voices",
                headers=headers,
            )

        response.raise_for_status()

        voices = response.json()

        return [
            {
                "id": voice["id"],
                "name": voice["name"],
                "description": voice.get("description"),
                "gender": voice.get("gender"),
                "language": voice.get("language"),
                "is_public": voice.get("is_public"),
            }
            for voice in voices
        ]