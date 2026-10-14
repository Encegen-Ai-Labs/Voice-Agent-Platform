# VoiceForge — AI Voice Agent Platform

A full SaaS voice agent platform. 

---

## 1. What this project does

The core business flow is:

1. User signs up/logs in.
2. User creates a workspace and agent.
3. Agent has a name, system prompt, language, voice, and LLM model.
4. Agent can optionally ingest knowledge base text.
5. Twilio phone number is assigned to the agent.
6. Live calls connect to a WebSocket pipeline.
7. Deepgram converts audio into transcript.
8. Groq generates the reply.
9. Cartesia converts the reply into audio.
10. Audio is streamed back over Twilio/Browser to the caller.

This is a real-time voice assistant platform, not just a UI wrapper around a chat API.

---

## 2. Actual runtime stack used by the code

The active code paths clearly use the following technologies:

- Backend framework: FastAPI
- Database ORM: SQLAlchemy
- DB migrations: Alembic
- Auth: JWT-based auth using custom security helpers
- Frontend: React + Vite + Tailwind CSS
- Telephony: Twilio Voice API + TwiML + Media Streams
- Speech-to-text: Deepgram
- LLM: Groq
- TTS: Cartesia
- Fallback TTS: Edge TTS

### Models actually used

#### STT model
- Deepgram client: `AsyncDeepgramClient` in `backend/app/core/realtime_stt.py`
- Model used: `flux-general-en`
- Audio settings: `encoding="mulaw"`, `sample_rate=8000`, `eager_eot_threshold=0.6`

This is the production live-call transcription model.

#### LLM model
- Groq client: `AsyncGroq` in `backend/app/core/pipeline.py`
- Default agent model: `allam-2-7b`
- In browser voice test code, there is an override that swaps deprecated models to `allam-2-7b`
- Frontend default form value still contains `openai/gpt-oss-20b`, but the server-side logic explicitly treats that and similar entries as deprecated and switches them to `allam-2-7b`

So the actual production model in the app logic is effectively:

- Groq model: `allam-2-7b`

#### TTS model
- Cartesia WebSocket TTS in `backend/app/core/pipeline.py`
- Model used: `sonic-2`
- Default voice id: `79a125e8-cd45-4c13-8a67-188112f4dd22`
- Output format: PCM 16-bit little-endian, 8000 Hz

If `CARTESIA_API_KEY` is missing, the code falls back to Edge TTS.

#### Telephony provider
- Twilio library is used directly in `backend/app/api/telephony.py` and `backend/app/api/websocket.py`
- TwiML `VoiceResponse` is used to answer calls and open Twilio Media Streams

---

## 3. Architecture overview

### Backend runtime flow

The real backend is organized like this:

- `backend/app/main.py` creates the FastAPI app and registers all routers
- `backend/app/database.py` configures SQLAlchemy and DB sessions
- `backend/app/models/` defines the database schema
- `backend/app/schemas/` defines validation and response objects
- `backend/app/services/` contains the business logic layer
- `backend/app/api/` exposes HTTP/WebSocket endpoints
- `backend/app/core/` holds deep infrastructure pieces like STT, TTS, rate limiting, config, and the voice pipeline

### Frontend runtime flow

The frontend is a Vite React app that provides:

- login/register screens
- dashboard panels
- agent CRUD screens
- call history and analytics views
- voice testing UI

The main route setup is in `frontend/src/App.jsx`.

---

## 4. Folder-by-folder guide

### Root

- `.env.example` — environment template for all external secrets and runtime config
- `.gitignore` — repository ignore rules
- `README.md` — project documentation
- `backend/` — FastAPI backend service
- `frontend/` — React + Vite frontend app

### `backend/`

#### `backend/app/`

This is the main application package.

- `backend/app/__init__.py` — package marker
- `backend/app/main.py` — starts FastAPI and registers all routers
- `backend/app/database.py` — DB engine, sessionmaker, and `get_db()`
- `backend/app/core/`
  - `config.py` — environment config loader using `.env`
  - `pipeline.py` — main AI voice pipeline; Groq + Cartesia orchestration
  - `realtime_stt.py` — Deepgram real-time transcription client for phone calls
  - `browser_stt.py` — browser-based STT helper used in voice-test mode
  - `call_prewarm.py` — optimization for prewarming Deepgram before Twilio media streams start
  - `rate_limit.py` — request throttling logic
  - `security.py` — JWT auth and password hash helpers
- `backend/app/api/`
  - `auth.py` — login/register endpoints
  - `agents.py` — CRUD for agents and Cartesia voice fetch
  - `calls.py` — call listing and management endpoints
  - `analytics.py` — analytics endpoints
  - `telephony.py` — Twilio inbound/outbound call endpoints
  - `websocket.py` — Twilio live-call WebSocket route
  - `web_voice.py` — browser voice test WebSocket route
  - `workspaces.py` — workspace endpoints
  - `phone_numbers.py` — phone number management
  - `api_keys.py` — API key management
  - `knowledge_base.py` — knowledge base upload/search logic
  - `voice.py` — voice catalog endpoints
- `backend/app/models/`
  - `user.py` — user record
  - `workspace.py` — workspace org container
  - `agent.py` — AI agent definition
  - `phone_number.py` — Twilio number assignment
  - `call.py` — call records and metadata
  - `voice.py` — TTS voice catalog row
  - `knowledge_base.py` — uploaded knowledge content
  - `api_key.py` — API key storage
  - `usage_record.py` — usage tracking
- `backend/app/schemas/`
  - request and response Pydantic models for auth, agents, calls, analytics, etc.
- `backend/app/services/`
  - `auth_service.py` — register/login business logic
  - `agent_service.py` — CRUD operations for agents
  - `call_service.py` — call record creation/updates
  - `analytics_service.py` — call metrics for dashboard and analytics
  - `cartesia_service.py` — Cartesia voice catalog API
  - `voice_service.py` — voice list filtering
  - `voice_sync_service.py` — sync Cartesia voice list into DB
  - `workspace_service.py` — workspace logic
  - `knowledge_base_service.py` — knowledge upload operations
  - `phone_number_service.py` — Twilio phone-number transactions
  - `api_key_service.py` — API keys service layer

#### `backend/alembic/`

- migration tooling for SQLAlchemy schema changes
- used when evolving the database schema over time
- not the app runtime itself, but important for database maintenance

#### `backend/requirements.txt`

Contains the Python dependencies for the backend. This is the place to update when adding new backend packages.

#### `backend/test_llm.py`, `backend/testing_pr.py`, `backend/verify_keys.py`

These appear to be developer utility scripts for testing external APIs or validating keys. They are not part of the main application flow and can be ignored for normal app development unless you are debugging a third-party API integration.

---

### `frontend/`

- `frontend/package.json` — React dependencies and scripts
- `frontend/vite.config.js` — Vite dev server config
- `frontend/index.html` — app entry HTML
- `frontend/src/main.jsx` — React bootstrap entry
- `frontend/src/App.jsx` — route configuration and layout
- `frontend/src/pages/`
  - `Dashboard.jsx` — admin dashboard summary
  - `Agents.jsx` — create/edit/delete agents, attach voice and knowledge base
  - `Calls.jsx` — historical call management
  - `Analytics.jsx` — analytics page
  - `Settings.jsx` — preference/settings page
  - `VoiceTest.jsx` — browser-based voice testing interface
  - `Login.jsx`, `Register.jsx` — auth pages
- `frontend/src/components/`
  - layout and reusable UI components
  - `Sidebar.jsx`, `TopBar.jsx`, and `ui/` shadcn-like components
- `frontend/src/services/`
  - `api.js` — axios instance with auth token handling
  - `voice.js` — voice list fetching helper
- `frontend/src/lib/utils.js` — utility helpers
- `frontend/src/index.css` and `frontend/src/App.css` — styling layers

---

## 5. Main API and app flow

### Authentication

- `/auth/register`
- `/auth/login`

This creates a user and a workspace automatically via `register_user()` in `auth_service.py`.

### Agent management

- `/agents`
- `/agents/{agent_id}`
- `/agents/voices`

Used to create or edit voice agents and retrieve available Cartesia voices.

### Twilio telephony

- `/twilio/incoming-call`
- `/twilio/outbound-call`

Used to receive Twilio webhooks and initiate outbound calls. Twilio is the telephony layer for live voice interactions.

### Real-time call connection

- `/ws/call`
- `/api/voice-test/ws`

These are the WebSocket endpoints that actually process live audio, transcribe with Deepgram, and stream responses back to the user.

### Health check

- `/health`
- `/`

The FastAPI app exposes a health check plus a root endpoint.

---

## 6. What is important vs. what can be skipped

### Must-have runtime files

These are essential for the actual app to work:

- `backend/app/main.py`
- `backend/app/database.py`
- `backend/app/core/config.py`
- `backend/app/core/pipeline.py`
- `backend/app/core/realtime_stt.py`
- `backend/app/api/telephony.py`
- `backend/app/api/websocket.py`
- `backend/app/models/*.py`
- `backend/app/services/*.py`
- `frontend/src/App.jsx`
- `frontend/src/pages/*.jsx`
- `.env.example`

### Useful but optional / secondary

These are not the core product flow, but are helpful for extension or maintenance:

- `backend/alembic/` — only needed if you are changing DB schema or running migrations
- `backend/app/api/analytics.py` — analytics features are useful but not required for voice runtime
- `backend/app/services/voice_sync_service.py` — used only to sync Cartesia voices into the DB
- `backend/app/core/browser_stt.py` — useful for the browser voice-test path, not the main telephony path
- `frontend/src/pages/VoiceTest.jsx` — demo/testing UI for browser direct voice interaction

### Likely safe to skip for normal development

These appear to be debugging or validation scripts rather than core app code:

- `backend/test_llm.py`
- `backend/testing_pr.py`
- `backend/verify_keys.py`
- `frontend/README.md` — generic Vite template text, not project-specific documentation
- any generated or temporary debug output files if present in repo after experimentation

> In short: if your goal is to understand the app and run the platform, focus on the `backend/app` and `frontend/src` directories; ignore the developer utility scripts unless you are debugging API credentials or testing external integrations.

---

## 7. Environment variables

The `.env.example` file defines the required configuration for the real integrations:

- `DEEPGRAM_API_KEY`
- `GROQ_API_KEY`
- `CARTESIA_API_KEY`
- `TWILIO_ACCOUNT_SID`
- `TWILIO_AUTH_TOKEN`
- `TWILIO_PHONE_NUMBER`
- `DATABASE_URL`
- `JWT_SECRET_KEY`
- `JWT_ALGORITHM`
- `JWT_EXPIRE_MINUTES`
- `APP_ENV`
- `APP_PORT`
- `PUBLIC_BASE_URL`

There is no hidden magic here; everything real is keyed off environment variables.

---

## 8. How to run locally

### Backend

```bash
cd backend
python -m venv venv
# Windows
venv\Scripts\activate
# macOS/Linux
source venv/bin/activate
pip install -r requirements.txt
copy ..\.env.example .env
# or create your own .env with the required keys
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Frontend

```bash
cd frontend
npm install
npm run dev
```

The frontend default API base URL is `http://localhost:8000` unless `VITE_API_URL` is overridden in the frontend environment.

---

## 9. Notable implementation details

- The app uses a live AI voice pipeline rather than a simple REST endpoint response.
- Twilio calls are connected via Media Streams, and the app listens to audio in real time.
- Deepgram is warmed up before the real user audio begins for better latency.
- Cartesia speech generation is done using the WebSocket API, which is optimized for real-time voice output.
- The app treats knowledge-base content as contextual memory for agents.
- The app is multi-tenant in structure: workspaces, users, agents, calls, and phone numbers are linked by IDs.

---

## 10. Summary

This project is a SaaS-style AI voice agent platform with a working production path built around:

- FastAPI backend
- React frontend
- Twilio telephony
- Deepgram STT
- Groq LLM
- Cartesia TTS
- SQLAlchemy database

If you are trying to understand the repo quickly, the most important files are:

- `backend/app/main.py`
- `backend/app/core/pipeline.py`
- `backend/app/core/realtime_stt.py`
- `backend/app/api/telephony.py`
- `backend/app/api/websocket.py`
- `backend/app/models/`
- `frontend/src/App.jsx`
- `frontend/src/pages/Agents.jsx`

Everything else in the repo is either support code, migration tooling, or debugging utilities.

---

## 11. Recommended development focus

If you plan to maintain or extend this project, prioritize these areas:

1. voice pipeline quality and latency
2. Twilio integration and call lifecycle reliability
3. LLM prompt tuning and agent config
4. DB model clarity and migrations
5. frontend UX for agent management and analytics
6. environment and credential validation

This is the part of the project that matters for both product value and future development.
