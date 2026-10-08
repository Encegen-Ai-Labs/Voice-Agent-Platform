import os
import asyncio
import httpx
from dotenv import load_dotenv

load_dotenv()

DEEPGRAM_API_KEY = os.getenv("DEEPGRAM_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")
CARTESIA_API_KEY = os.getenv("CARTESIA_API_KEY")
TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")

async def check_deepgram():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.deepgram.com/v1/projects", headers={"Authorization": f"Token {DEEPGRAM_API_KEY}"})
        if response.status_code == 200:
            print("✅ Deepgram API Key: Working")
        else:
            print(f"❌ Deepgram API Key: Failed ({response.status_code})")

async def check_groq():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.groq.com/openai/v1/models", headers={"Authorization": f"Bearer {GROQ_API_KEY}"})
        if response.status_code == 200:
            print("✅ Groq API Key: Working")
        else:
            print(f"❌ Groq API Key: Failed ({response.status_code})")

async def check_cartesia():
    async with httpx.AsyncClient() as client:
        response = await client.get("https://api.cartesia.ai/voices", headers={"X-API-Key": CARTESIA_API_KEY, "Cartesia-Version": "2024-06-10"})
        if response.status_code == 200:
            print("✅ Cartesia API Key: Working")
        else:
            print(f"❌ Cartesia API Key: Failed ({response.status_code})")

async def check_twilio():
    async with httpx.AsyncClient() as client:
        url = f"https://api.twilio.com/2010-04-01/Accounts/{TWILIO_ACCOUNT_SID}.json"
        response = await client.get(url, auth=(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN))
        if response.status_code == 200:
            print("✅ Twilio Credentials: Working")
        else:
            print(f"❌ Twilio Credentials: Failed ({response.status_code})")

async def main():
    print("Checking API Keys...\n" + "-"*40)
    await asyncio.gather(
        check_deepgram(),
        check_groq(),
        check_cartesia(),
        check_twilio()
    )
    print("-" * 40 + "\nDone.")

asyncio.run(main())
