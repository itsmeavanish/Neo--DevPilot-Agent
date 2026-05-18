# JARVIS - Remote Dev Control

Control your laptop from your phone with AI assistance.

## Quick Start

### 1. Start Backend

`python run.py`

### 2. Expose with ngrok

`ngrok http 8000`

Copy the **https** forwarding URL and keep it in sync with:

- `Frontend/lib/config.ts` → `DEFAULT_BACKEND_URL`
- `agent-installer/jarvis_agent.py` → default `JARVIS_SERVER` (or set `JARVIS_SERVER` in `%USERPROFILE%\.jarvis\config.env`)

### 3. Run Mobile App

`cd Frontend`
`npm install`
`npx expo start`

## Features

| Feature          | Description                      |
| ---------------- | -------------------------------- |
| **Terminal**     | Execute shell commands remotely  |
| **Files**        | Browse and edit code files       |
| **AI Chat**      | GitHub Copilot / Ollama / OpenAI |
| **IDE**          | Open VS Code or Cursor           |
| **Git**          | Status, commit, push, pull       |
| **Multi-Laptop** | Switch between devices           |

## Project Structure
