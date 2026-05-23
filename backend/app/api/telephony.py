import os
from uuid import UUID
import logging
from fastapi import APIRouter, Request, Response
from twilio.twiml.voice_response import VoiceResponse

from app.database import SessionLocal
from app.models.call import Call
from app.models.phone_number import PhoneNumber

from fastapi import Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.core.security import get_current_user
from app.schemas.telephony import OutboundCallRequest

from app.services.agent_service import get_agent
from app.services.call_service import create_call

from app.schemas.call import CallCreate

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
    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")

    host = PUBLIC_BASE_URL.replace("https://","").replace("http://","")
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


@router.post("/outbound-call")
async def outbound_call(
    payload: OutboundCallRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db)
):

    workspace_id = current_user["workspace_id"]

    agent = get_agent(
        db,
        workspace_id,
        payload.agent_id
    )

    phone_number = (
            db.query(PhoneNumber)
            .filter(
                PhoneNumber.agent_id == agent.id,
                PhoneNumber.workspace_id == workspace_id
            )
            .first()
            )

    if not phone_number:

        raise HTTPException(
            status_code=400,
            detail="No Twilio phone number assigned to this agent"
        )

    call_data = CallCreate(
        agent_id=agent.id,
        phone_number=payload.phone_number,
        direction="outbound"
    )

    call_record = create_call(
        db,
        workspace_id,
        call_data
    )

    client = Client(
        TWILIO_ACCOUNT_SID,
        TWILIO_AUTH_TOKEN
    )

    PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL")
    call = client.calls.create(
        to=payload.phone_number,
        from_=phone_number.number,
        url=f"{PUBLIC_BASE_URL}/twilio/incoming-call?call_id={str(call_record.id)}"
    )

    call_record.twilio_call_sid = call.sid

    db.commit()

    db.refresh(call_record)

    logger.info(
        "Outbound call initiated: %s",
        call.sid
    )

    return {
        "message": "Call initiated",
        "call_sid": call.sid,
        "call_id": str(call_record.id)
    }