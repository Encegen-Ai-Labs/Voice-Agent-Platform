# VoiceForge — AI Voice Agent Platform

A full SaaS voice agent platform. 

---

## Team
- Vishit — Lead Dev (voice pipeline, telephony, architecture)
- Poonam — Frontend (React dashboard, UI)
- Aditya — Backend (FastAPI, database, auth)

---

## Tech Stack
- **Frontend:** React, Tailwind CSS, Shadcn/ui, React Flow
- **Backend:** FastAPI, SQLAlchemy, Alembic, SQLite → Postgres
- **Voice:** Deepgram (STT), Groq (LLM), Edge TTS (TTS)
- **Telephony:** Twilio
- **Hosting:** Railway (backend), Vercel (frontend)

---

## Getting Started

### Prerequisites
- Python 3.11+
- Node.js 18+
- Git

### Setup

1. Clone the repo
git clone https://github.com/YOURUSERNAME/Voice-Agent-Platform.git
cd Voice-Agent-Platform

2. Copy environment variables
cp .env.example .env
Fill in your actual values in .env — ask the lead for the keys.

3. Backend setup
cd backend
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt

4. Frontend setup
cd frontend
npm install
npm run dev

---

## Branch Rules — Read This Before You Touch Git

- NEVER push directly to main or dev
- Always create your own branch for every piece of work
- Branch naming:
  - feature/what-youre-building (e.g. feature/agent-crud)
  - fix/what-youre-fixing (e.g. fix/login-error)
- When done, open a Pull Request into dev and tag the lead to review
- Lead reviews and merges — you do not merge your own PRs

---


## Project Structure

Voice-Agent-Platform/
├── backend/
│   └── app/
│       ├── core/        # Voice pipeline, STT, LLM, TTS (Lead)
│       ├── api/         # FastAPI endpoints (Dev 2)
│       └── models/      # Database models (Dev 2)
├── frontend/
│   └── src/
│       ├── pages/       # Dashboard, Agents, Calls etc (Dev 1)
│       └── components/  # Reusable UI components (Dev 1)
├── .env.example
├── .gitignore
└── README.md