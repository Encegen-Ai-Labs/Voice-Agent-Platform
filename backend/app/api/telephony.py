import os
import logging
from fastapi import APIRouter, Request, Response
from twilio.twiml.voice_response import VoiceResponse

logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)

router = APIRouter(prefix="/twilio", tags=["Telephony"])

TWILIO_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
TWILIO_PHONE_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")

if not all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
    logger.warning("Twilio credentials not fully configured — check your .env file")

@router.post("/incoming-call")
async def incoming_call(request: Request):
    host = request.headers.get("host", "localhost")
    response = VoiceResponse()
    response.say("Hello, I am your AI assistant. How can I help you today?")
    response.pause(length=1)
    connect = response.connect()
    connect.stream(url=f"wss://{host}/ws/call", track="inbound_track")
    twiml = str(response)
    print("TWIML:", twiml)
    logger.info("Returning TwiML: %s", twiml)
    return Response(content=twiml, media_type="application/xml")


@router.post("/call-status")
async def call_status(request: Request):
    form = await request.form()
    logger.info(
        "Call status update: sid=%s status=%s",
        form.get("CallSid"),
        form.get("CallStatus"),
    )
    return Response(status_code=204)