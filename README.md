# Computer Use Agent Backend

A scalable, production-ready backend for Anthropic Computer Use Agent session management built with **FastAPI**, **PostgreSQL**, **WebSockets / SSE**, **noVNC Virtual Desktop integration**, and **Docker**.

---

## Features

- **Session Management APIs**: RESTful endpoints to create, list, inspect, and delete agent sessions.
- **Race-Condition-Free Concurrency**: In-memory async locking (`asyncio.Lock` per session) preventing simultaneous conflicting sampling loops.
- **Database Persistence**: PostgreSQL / SQLAlchemy async models for full chat history, tool calls, and screenshots.
- **Real-Time Progress Streaming**: Live streaming of tool execution, thoughts, screenshots, and status updates via WebSockets (`/ws/sessions/{id}`) and SSE (`/api/v1/sessions/{id}/stream`).
- **VNC Screen Connection**: Embedded noVNC display server integration (`http://localhost:6080`) providing live visual desktop interaction.
- **Interactive Control Dashboard**: Single-page web interface (`app/static/index.html`) with dark glassmorphism design.
- **Docker Containerization**: Complete `Dockerfile` and `docker-compose.yml` for local development and remote deployment.

---

## Tech Stack

- **Backend**: Python 3.12+, FastAPI, Uvicorn, SQLAlchemy (Async), Asyncpg, Anthropic Python SDK
- **Database**: PostgreSQL
- **Desktop Environment**: Xvfb, Openbox, x11vnc, noVNC, websockify
- **Frontend**: HTML5, Vanilla JS, CSS3 (Glassmorphism design system)

---

## Getting Started

### 1. Environment Setup

Copy `.env.example` to `.env` and add your Anthropic API Key:

```bash
cp .env.example .env
```

Edit `.env`:
```env
ANTHROPIC_API_KEY=sk-ant-api03-...
DATABASE_URL=postgresql+asyncpg://postgres:postgrespassword@localhost:5432/computer_use_db
```

---

### 2. Local Development with Docker Compose (Recommended)

Run the full stack (FastAPI + PostgreSQL + Xvfb + noVNC):

```bash
docker-compose up --build
```

Access services at:
- **Web Control Dashboard**: [http://localhost:8000](http://localhost:8000)
- **FastAPI OpenAPI Docs**: [http://localhost:8000/docs](http://localhost:8000/docs)
- **noVNC Desktop Viewer**: [http://localhost:6080/vnc.html](http://localhost:6080/vnc.html)

---

### 3. Local Python Execution

Install dependencies:
```bash
uv sync
```

Run FastAPI server:
```bash
uv run uvicorn main:app --reload --port 8000
```

---

## API Reference

### Sessions
- `POST /api/v1/sessions` - Create a new session.
- `GET /api/v1/sessions` - List all active/past sessions.
- `GET /api/v1/sessions/{session_id}` - Retrieve session details.
- `DELETE /api/v1/sessions/{session_id}` - Delete session & clean resources.
- `GET /api/v1/sessions/{session_id}/messages` - Fetch chat/event message history.
- `POST /api/v1/sessions/{session_id}/messages` - Send instruction prompt to trigger background agent.
- `POST /api/v1/sessions/{session_id}/stop` - Interrupt active task execution.

### Streaming & Real-Time
- `WebSocket /ws/sessions/{session_id}` - Real-time event stream.
- `GET /api/v1/sessions/{session_id}/stream` - Server-Sent Events (SSE) stream.
