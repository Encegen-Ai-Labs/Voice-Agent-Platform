import os
from uuid import UUID
import logging
from fastapi import APIRouter, Request, Response
from twilio.twiml.voice_response import VoiceResponse

from app.database import SessionLocal
from app.models.call import Call
from app.models.phone_number import PhoneNumber

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
    call_id = request.query_params.get(
    "call_id"
    )
    print("INCOMING CALL query_params:", request.query_params)
    print("INCOMING CALL call_id:", call_id)
    print("INCOMING CALL url:", request.url)
    logger.info(
        "Incoming call request url=%s query_params=%s call_id=%s",
        request.url,
        request.query_params,
        call_id,
    )
    response = VoiceResponse()
    response.say("Hello, I am your AI assistant. How can I help you today?")
    response.pause(length=1)
    connect = response.connect()
    connect.stream(url=f"wss://{host}/ws/call?call_id={call_id}", track="inbound_track")
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


from twilio.rest import Client


@router.post("/test-call")
async def test_call():
    db = SessionLocal()
    phone_number = db.query(
        PhoneNumber
    ).filter(
        PhoneNumber.number == TWILIO_PHONE_NUMBER
    ).first()

    if not phone_number:

        return {
            "error": "Twilio phone number not mapped to workspace"
        }

    call_record = Call(
    workspace_id=phone_number.workspace_id,
    agent_id=phone_number.agent_id,
    phone_number="+917058326485",
    direction="outbound",
    status="ongoing"
)

    db.add(call_record)

    db.commit()

    db.refresh(call_record)
    client = Client(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN
    )

    call = client.calls.create(
        to="+917058326485",
        from_=TWILIO_PHONE_NUMBER,
        url=f"https://dawn-hydrocodone-trek-cellular.trycloudflare.com/twilio/incoming-call?call_id={str(call_record.id)}" #this should be your ngrok or cloudflare url pointing to the /twilio/incoming-call endpoint
    )

    call_record.twilio_call_sid = call.sid
    db.add(call_record)
    db.commit()

    logger.info(
        "Outbound test call initiated: %s twilio_call_sid=%s",
        call.sid,
        call.sid
    )

    return {
        "message": "Call initiated",
        "call_sid": call.sid
    }

