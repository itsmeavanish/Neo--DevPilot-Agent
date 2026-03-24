# JARVIS Cloud Deployment Guide

Deploy JARVIS to work 24/7, even when your laptop is off.

## Architecture Overview

```
┌─────────────────┐     ┌─────────────────────────────┐
│   Your Phone    │     │      Cloud Server           │
│   (APK App)     │────▶│   (Railway/Render/Fly.io)   │
└─────────────────┘     └─────────────────────────────┘
                                     │
                                     ▼ (Optional - when laptop is ON)
                        ┌─────────────────────────────┐
                        │      Your Laptop            │
                        │   (Remote Agent)            │
                        └─────────────────────────────┘
```

---

## Part 1: Deploy Backend to Cloud

### Option A: Railway (Recommended - Free tier available)

1. **Create Railway Account**
   ```
   https://railway.app
   ```

2. **Install Railway CLI**
   ```bash
   npm install -g @railway/cli
   railway login
   ```

3. **Deploy from your project**
   ```bash
   cd c:\Users\7CIN\Desktop\Jarvis
   railway init
   railway up
   ```

4. **Add Environment Variables** (in Railway Dashboard)
   ```
   JARVIS_API_HOST=0.0.0.0
   JARVIS_API_PORT=$PORT
   JARVIS_DEBUG=false
   JARVIS_API_KEY=your-secure-key-here
   JARVIS_LLM_PROVIDER=ollama
   ```

5. **Add PostgreSQL** (optional)
   - Click "New" → "Database" → "PostgreSQL"
   - Railway auto-injects `DATABASE_URL`

6. **Add Redis** (optional)
   - Click "New" → "Database" → "Redis"
   - Railway auto-injects `REDIS_URL`

7. **Get your public URL**
   ```
   https://jarvis-production-xxxx.up.railway.app
   ```

---

### Option B: Render (Free tier available)

1. **Create render.yaml**
   ```yaml
   services:
     - type: web
       name: jarvis-api
       env: docker
       dockerfilePath: ./Dockerfile.cloud
       envVars:
         - key: JARVIS_API_KEY
           sync: false
         - key: JARVIS_LLM_PROVIDER
           value: ollama
   ```

2. **Connect GitHub repo to Render**
   - Go to https://render.com
   - New → Web Service → Connect your repo
   - Select Dockerfile.cloud

---

### Option C: Fly.io

1. **Install Fly CLI**
   ```bash
   curl -L https://fly.io/install.sh | sh
   fly auth login
   ```

2. **Create fly.toml**
   ```toml
   app = "jarvis-api"
   primary_region = "ord"

   [build]
     dockerfile = "Dockerfile.cloud"

   [http_service]
     internal_port = 8000
     force_https = true

   [env]
     JARVIS_API_HOST = "0.0.0.0"
     JARVIS_LLM_PROVIDER = "ollama"
   ```

3. **Deploy**
   ```bash
   fly launch
   fly deploy
   ```

---

## Part 2: Build Mobile App (APK)

### Prerequisites
```bash
npm install -g eas-cli
cd Frontend
eas login
```

### Update API URL
Edit `Frontend/lib/api.ts`:
```typescript
export const API_CONFIG = {
  // Replace with your Railway/Render URL
  baseUrl: 'https://jarvis-production-xxxx.up.railway.app',
  apiKey: 'your-secure-key-here',
};
```

### Build APK for Android

1. **Configure EAS**
   ```bash
   cd Frontend
   eas build:configure
   ```

2. **Build APK (local)**
   ```bash
   # Build locally (faster, no Expo account needed)
   eas build --platform android --profile preview --local
   ```

3. **Build APK (cloud)**
   ```bash
   # Build on Expo servers
   eas build --platform android --profile preview
   ```

4. **Download and Install**
   - APK will be at: `Frontend/build-xxx.apk`
   - Transfer to phone and install
   - Enable "Install from unknown sources" if needed

### Build for iOS (requires Mac + Apple Developer Account)
```bash
eas build --platform ios --profile preview
```

---

## Part 3: Remote Agent (Control Laptop When It's ON)

When your laptop is ON, you can still control it through the cloud server.

### Setup Remote Agent on Laptop

1. **Create agent script** (`run_agent.py`)
   ```python
   # This runs on your laptop and connects to cloud server
   import asyncio
   import websockets
   import subprocess
   import json

   CLOUD_SERVER = "wss://jarvis-production-xxxx.up.railway.app/ws/agent"
   AGENT_TOKEN = "your-agent-token"

   async def agent():
       async with websockets.connect(
           f"{CLOUD_SERVER}?token={AGENT_TOKEN}"
       ) as ws:
           print("Connected to cloud server")
           async for message in ws:
               cmd = json.loads(message)
               if cmd["type"] == "execute":
                   result = subprocess.run(
                       cmd["command"],
                       shell=True,
                       capture_output=True,
                       text=True
                   )
                   await ws.send(json.dumps({
                       "stdout": result.stdout,
                       "stderr": result.stderr,
                       "code": result.returncode
                   }))

   asyncio.run(agent())
   ```

2. **Run on startup** (Windows Task Scheduler)
   ```
   Action: Start a program
   Program: python
   Arguments: C:\Users\7CIN\Desktop\Jarvis\run_agent.py
   Trigger: At log on
   ```

---

## Part 4: AI Provider Setup for Cloud

### GitHub Copilot (Not Available in Cloud)
- Copilot CLI requires local `gh` installation
- Use OpenAI/Anthropic for cloud deployment

### OpenAI (Recommended for Cloud)
```bash
# Set in Railway/Render environment:
JARVIS_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key-here
```

### Ollama (Self-hosted)
- Deploy Ollama to a GPU server
- Or use Ollama Cloud: https://ollama.com/cloud

---

## Quick Start Commands

```bash
# 1. Deploy backend
cd c:\Users\7CIN\Desktop\Jarvis
railway up

# 2. Build mobile app
cd Frontend
eas build --platform android --profile preview --local

# 3. Install APK on phone (via USB or download)
adb install build-*.apk
```

---

## Environment Variables Reference

| Variable | Required | Description |
|----------|----------|-------------|
| `JARVIS_API_HOST` | Yes | `0.0.0.0` for cloud |
| `JARVIS_API_PORT` | Yes | Railway uses `$PORT` |
| `JARVIS_API_KEY` | Yes | Secure API key |
| `JARVIS_LLM_PROVIDER` | Yes | `openai`, `ollama`, `anthropic` |
| `OPENAI_API_KEY` | If using OpenAI | Your OpenAI key |
| `JARVIS_DATABASE_URL` | Optional | PostgreSQL connection |
| `JARVIS_REDIS_URL` | Optional | Redis connection |

---

## Troubleshooting

### "Cannot connect to server"
- Check if Railway/Render deployment is running
- Verify API URL in app settings
- Check API key matches

### "AI not responding"
- In cloud, use OpenAI/Anthropic (not Copilot)
- Check API keys are set correctly

### Build fails
- Run `eas build --clear-cache`
- Check `eas.json` configuration
