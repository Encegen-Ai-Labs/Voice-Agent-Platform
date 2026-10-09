import logging
import os
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session
from twilio.rest import Client
from twilio.twiml.voice_response import VoiceResponse

from app.core.security import get_current_user
from app.core.realtime_stt import RealtimeSTTClient
from app.core.call_prewarm import start_prewarm
from app.database import get_db
from app.models.phone_number import PhoneNumber
from app.schemas.call import CallCreate
from app.schemas.telephony import OutboundCallRequest
from app.services.agent_service import get_agent
from app.services.call_service import create_call

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix="/twilio", tags=["Telephony"])

_ACCOUNT_SID = os.getenv("TWILIO_ACCOUNT_SID")
_AUTH_TOKEN = os.getenv("TWILIO_AUTH_TOKEN")
_TWILIO_NUMBER = os.getenv("TWILIO_PHONE_NUMBER")
_PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

if not all([_ACCOUNT_SID, _AUTH_TOKEN, _TWILIO_NUMBER]):
    logger.warning(
        "[Telephony] Twilio credentials incomplete — "
        "TWILIO_ACCOUNT_SID / TWILIO_AUTH_TOKEN / TWILIO_PHONE_NUMBER"
    )

if not _PUBLIC_BASE_URL:
    logger.warning(
        "[Telephony] PUBLIC_BASE_URL is not set — incoming calls will fail"
    )

@router.post("/incoming-call")
async def incoming_call(request: Request) -> Response:
    
    if not _PUBLIC_BASE_URL:
        logger.error("[Telephony] incoming_call: PUBLIC_BASE_URL not configured")
        return Response(
            content="Server misconfiguration: PUBLIC_BASE_URL missing",
            status_code=500,
        )

    try:
        call_id = request.query_params.get("call_id")
        logger.info("[Telephony] Incoming call call_id=%s", call_id)

        # Start connecting + warming Deepgram NOW, in the background, while
        # Twilio is about to speak the <Say> greeting. Previously this only
        # started once the Media Stream WebSocket connected — which Twilio
        # only does AFTER <Say> finishes — costing 2+ seconds of dead air
        # where the caller could be talking into a stream that wasn't
        # listening yet. This closes that gap. If the call never reaches
        # /ws/call (no answer, voicemail, etc.), call_prewarm's TTL cleanup
        # closes the connection automatically so nothing leaks.
        if call_id:
            await start_prewarm(call_id, RealtimeSTTClient)

        host = (
            _PUBLIC_BASE_URL
            .removeprefix("https://")
            .removeprefix("http://")
        )
        websocket_url = f"wss://{host}/ws/call?call_id={call_id}"

        response = VoiceResponse()
        response.say(
            "Hello, I am your AI assistant"
            "Please tell me how I can help you today."
        )

        connect = response.connect()
        stream = connect.stream(url=websocket_url, track="inbound_track")
        # Twilio Media Streams does not reliably forward query string
        # parameters on the wss:// URL itself through to the WebSocket
        # connection. The supported, reliable way to pass custom data is
        # via <Parameter> child elements, which Twilio delivers in the
        # "start" event payload as start.customParameters.call_id.
        stream.parameter(name="call_id", value=str(call_id))

        twiml = str(response)
        logger.info("[Telephony] TwiML generated for call_id=%s", call_id)
        logger.debug("[Telephony] TwiML: %s", twiml)

        return Response(content=twiml, media_type="application/xml")

    except Exception as exc:
        logger.error(
            "[Telephony] incoming_call failed: %s\n%s",
            exc,
            __import__("traceback").format_exc(),
        )
        return Response(
            content="Internal server error",
            status_code=500,
        )

@router.post("/outbound-call")
async def outbound_call(
    payload: OutboundCallRequest,
    current_user: dict = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> dict:
  
    if not _PUBLIC_BASE_URL:
        raise HTTPException(
            status_code=500,
            detail="Server misconfiguration: PUBLIC_BASE_URL missing",
        )

    workspace_id = current_user["workspace_id"]

    agent = get_agent(db, workspace_id, payload.agent_id)

    phone_number = (
        db.query(PhoneNumber)
        .filter(
            PhoneNumber.agent_id == agent.id,
            PhoneNumber.workspace_id == workspace_id,
        )
        .first()
    )
    if not phone_number:
        raise HTTPException(
            status_code=400,
            detail="No Twilio phone number assigned to this agent",
        )

    call_record = create_call(
        db,
        workspace_id,
        CallCreate(
            agent_id=agent.id,
            phone_number=payload.phone_number,
            direction="outbound",
        ),
    )

    client = Client(_ACCOUNT_SID, _AUTH_TOKEN)

    webhook_url = (
        f"{_PUBLIC_BASE_URL}/twilio/incoming-call"
        f"?call_id={call_record.id}"
    )

    twilio_call = client.calls.create(
        to=payload.phone_number,
        from_=phone_number.number,
        url=webhook_url,
    )

    call_record.twilio_call_sid = twilio_call.sid
    db.commit()
    db.refresh(call_record)

    logger.info(
        "[Telephony] Outbound call initiated: sid=%s call_id=%s to=%s",
        twilio_call.sid,
        call_record.id,
        payload.phone_number,
    )

    return {
        "message": "Call initiated",
        "call_sid": twilio_call.sid,
        "call_id": str(call_record.id),
    }