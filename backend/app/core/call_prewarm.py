"""
Registry for pre-warmed RealtimeSTTClient (Deepgram) connections, keyed by
call_id. This lets us start connecting + warming Deepgram the moment a call
is created (in the /incoming-call webhook), instead of waiting until the
Twilio Media Stream WebSocket actually connects — which today only happens
AFTER Twilio finishes speaking the <Say> greeting out loud, eating 2+
seconds of dead air before the AI can hear the caller.

Safety: if a call never reaches /ws/call (no answer, voicemail, busy,
webhook retried, etc.), the pre-warmed connection is automatically closed
after PREWARM_TTL_SECONDS so we never leak open Deepgram sessions.
"""

import asyncio
import logging
import time

logger = logging.getLogger(__name__)

PREWARM_TTL_SECONDS = 45  # generous upper bound on ring time before cleanup

# call_id -> {"client": RealtimeSTTClient, "created_at": float, "claimed": bool}
_registry: dict[str, dict] = {}
_registry_lock = asyncio.Lock()


async def start_prewarm(call_id: str, client_factory) -> None:
    """
    Kick off connecting + warming a RealtimeSTTClient for this call_id in
    the background. `client_factory` is a zero-arg callable that returns a
    fresh, unconnected RealtimeSTTClient instance (caller passes this in to
    avoid a circular import between this module and realtime_stt.py).
    """
    if not call_id:
        return
    print(f"[Prewarm DEBUG] start_prewarm called with call_id={call_id!r} (type={type(call_id)})")

    async with _registry_lock:
        if call_id in _registry:
            # Already pre-warming (e.g. webhook retried by Twilio) — don't double-start
            return
        client = client_factory()
        _registry[call_id] = {
            "client": client,
            "created_at": time.time(),
            "claimed": False,
        }

    async def _connect_and_schedule_cleanup():
        try:
            await client.connect()
            logger.info("[Prewarm] Deepgram pre-warmed for call_id=%s", call_id)
        except Exception as exc:
            logger.error("[Prewarm] Failed to pre-warm call_id=%s: %s", call_id, exc)

        # Schedule TTL cleanup regardless of connect success/failure
        await asyncio.sleep(PREWARM_TTL_SECONDS)
        async with _registry_lock:
            entry = _registry.get(call_id)
            if entry is not None and not entry["claimed"]:
                logger.info(
                    "[Prewarm] call_id=%s never claimed within %ss — closing and evicting",
                    call_id, PREWARM_TTL_SECONDS,
                )
                _registry.pop(call_id, None)
                try:
                    await entry["client"].close()
                except Exception as exc:
                    logger.warning("[Prewarm] Cleanup close failed for call_id=%s: %s", call_id, exc)

    asyncio.create_task(_connect_and_schedule_cleanup(), name=f"prewarm-{call_id}")


async def claim_prewarmed(call_id: str | None):
    """
    Called from the /ws/call handler. If a pre-warmed, still-valid client
    exists for this call_id, mark it claimed and return it (already
    connected and warmed — caller should NOT call .connect() again).
    Returns None if nothing was pre-warmed (caller should fall back to
    creating a fresh RealtimeSTTClient as before).
    """
    if not call_id:
        return None
    print(f"[Prewarm DEBUG] claim_prewarmed called with call_id={call_id!r} (type={type(call_id)})")
    print(f"[Prewarm DEBUG] current registry keys: {list(_registry.keys())!r}")

    async with _registry_lock:
        entry = _registry.pop(call_id, None)

    if entry is None:
        return None

    entry["claimed"] = True
    client = entry["client"]

    # If the underlying connection somehow isn't actually connected
    # (e.g. Deepgram connect failed silently earlier), treat as a miss
    # so the caller falls back to a fresh connect attempt.
    if not getattr(client, "_connected", False):
        logger.warning(
            "[Prewarm] call_id=%s pre-warmed client not connected — caller will fall back",
            call_id,
        )
        try:
            await client.close()
        except Exception:
            pass
        return None

    logger.info("[Prewarm] call_id=%s claimed pre-warmed Deepgram connection", call_id)
    return client