# Computer Use Agent AI - Control Center

A production-ready web application for **Anthropic Computer Use Agent** session control, built with **FastAPI**, **PostgreSQL**, **WebSockets**, **noVNC Desktop integration**, and **Docker**.

Includes a side-by-side control dashboard featuring a live interactive **noVNC Linux Desktop**, **real-time progress streaming**, **segment screenshot analysis**, and a **dark glassmorphism theme**.

---

## 📹 Video Demo

Watch the full project walkthrough with voice narration demonstrating session control, live noVNC desktop automation, and real-time streaming:
▶️ **[Watch Video Demo with Voice Narration](https://drive.google.com/file/d/1Da5HPH-8Sle4pdkTjWZw5l6DCPCvjxpq/view?usp=drive_link)**

---

## 🚀 Quick Start with Docker (Recommended)

Follow these simple steps to clone the repository and run the full stack locally:

### Step 1: Clone the Repository

```bash
git clone https://github.com/Zahid-Hasan-Mozumder/claude-computer-use.git
cd claude-computer-use
```

### Step 2: Configure Environment Variables

Create your `.env` configuration file from `.env.example`:

```bash
# On Linux/macOS
cp .env.example .env

# On Windows (PowerShell)
copy .env.example .env
```

Open `.env` and set your **Anthropic API Key**:

```env
ANTHROPIC_API_KEY=sk-ant-api03-...
```

### Step 3: Run with Docker Compose

Build and launch all services (FastAPI Backend + PostgreSQL + Xvfb + tint2 Desktop + noVNC):

```bash
docker-compose up --build
```

> [!TIP]
> To run containers in detached background mode:
> ```bash
> docker-compose up -d --build
> ```

---

## 🌐 Application URLs

Once Docker Compose finishes starting up, access the application in your browser:

| Service | Access URL | Description |
| :--- | :--- | :--- |
| **Control Dashboard** | [http://localhost:8000](http://localhost:8000) | Main split-view dashboard (Chat + Live noVNC) |
| **API Documentation** | [http://localhost:8000/docs](http://localhost:8000/docs) | Interactive Swagger OpenAPI docs |
| **noVNC Screen Viewer** | [http://localhost:6080/vnc.html](http://localhost:6080/vnc.html) | Direct full-screen noVNC desktop stream |

---

## 🎯 How to Use the Control Dashboard

1. Open [http://localhost:8000](http://localhost:8000) in your browser.
2. Click **`+ New Session`** on the top left sidebar and create a session.
3. In the prompt input box at the bottom, type your instruction (e.g., `Open browser and search for weather`).
4. Click **`Send`** (or press Enter).
5. Watch the agent execute actions step-by-step:
   - **Left Panel**: Real-time thoughts, step logs, and compact segment screenshot badges.
   - **Right Panel**: Live interactive **noVNC Desktop Stream** (with taskbar, clock, Firefox browser, and mouse movements).

---

## 💻 Alternative: Running Locally without Docker (Python / uv)

If you wish to run the FastAPI backend locally using `uv` or standard Python:

```bash
# 1. Install dependencies
uv sync

# 2. Set environment variables (PowerShell)
$env:ANTHROPIC_API_KEY="sk-ant-api03-..."
$env:PYTHONIOENCODING="utf-8"

# 3. Start Uvicorn development server
uv run uvicorn main:app --reload --port 8000
```

> [!NOTE]
> Running locally outside Docker streams virtual desktop screenshots in **Desktop Screen** mode. Running via Docker is recommended for the full interactive noVNC stream on port 6080.

---

## 🛑 Useful Docker Commands

```bash
# Stop all running containers
docker-compose down

# Stop containers and remove database volumes
docker-compose down -v

# View container logs in real time
docker-compose logs -f backend

# Rebuild containers from scratch
docker-compose up --build --force-recreate
```

---

## 🛠️ Features & Architecture

- **Side-by-Side Control Center**: 50/50 split view with live noVNC desktop viewer.
- **Segment Screenshot Analysis**: Computer agent captures screenshots after actions, analyzes layout, and reports findings.
- **Race-Condition-Free Session Manager**: Concurrent session locks (`asyncio.Lock`) preventing conflicting sampling loops.
- **Real-Time WebSockets**: Live progress streaming for thoughts, tool calls, and screenshots.
- **Complete Desktop Environment**: Xvfb virtual framebuffer, Openbox window manager, tint2 taskbar panel, firefox-esr, xterm, x11vnc, and noVNC websockify.
- **Persistence**: Async SQLAlchemy database persistence for chat history and tool results.
