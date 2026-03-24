# JARVIS Cloud Deployment Guide

Deploy JARVIS to run 24/7 from the cloud, accessible from anywhere.

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         CLOUD                                    │
│  ┌─────────────────┐    ┌─────────────────┐    ┌─────────────┐  │
│  │  Railway/Render │    │   Neon/Supabase │    │   Upstash   │  │
│  │  (JARVIS API)   │───▶│   (PostgreSQL)  │    │   (Redis)   │  │
│  └────────┬────────┘    └─────────────────┘    └─────────────┘  │
│           │                                                      │
└───────────┼──────────────────────────────────────────────────────┘
            │
            │  HTTPS
            ▼
┌─────────────────────┐         ┌─────────────────────┐
│   Your Phone        │         │   Your Laptop       │
│   (JARVIS APK)      │         │   (Optional Agent)  │
└─────────────────────┘         └─────────────────────┘
```

---

## Step 1: Deploy Backend to Cloud

### Option A: Railway (Recommended - Free Tier)

1. **Create Railway Account**
   ```
   https://railway.app
   ```

2. **Deploy from GitHub**
   - Connect your GitHub repo
   - Railway auto-detects `Dockerfile.cloud`
   - Set environment variables:
     ```
     JARVIS_API_KEY=your-secure-key
     JARVIS_LLM_PROVIDER=ollama
     ```

3. **Get Your URL**
   ```
   https://jarvis-xxx.up.railway.app
   ```

### Option B: Render (Free Tier)

1. **Create render.yaml**
   ```yaml
   services:
     - type: web
       name: jarvis
       env: docker
       dockerfilePath: ./Dockerfile.cloud
       envVars:
         - key: JARVIS_API_KEY
           sync: false
   ```

2. **Deploy**
   - Connect GitHub
   - Render deploys automatically

### Option C: Self-Hosted VPS

```bash
# On your VPS (DigitalOcean, Linode, etc.)
git clone https://github.com/yourusername/jarvis.git
cd jarvis
docker build -f Dockerfile.cloud -t jarvis .
docker run -d -p 8000:8000 \
  -e JARVIS_API_KEY=your-key \
  jarvis
```

---

## Step 2: Build Mobile APK

### Prerequisites
```bash
cd Frontend
npm install -g eas-cli
eas login
```

### Build APK
```bash
# Development build (for testing)
eas build -p android --profile preview

# Production build
eas build -p android --profile production
```

### Download & Install
- EAS provides download link when build completes
- Transfer APK to phone and install
- Enable "Install from Unknown Sources"

---

## Step 3: Configure App

1. **Open JARVIS app on phone**
2. **Go to Settings**
3. **Update Backend URL** to your cloud URL:
   ```
   https://jarvis-xxx.up.railway.app
   ```
4. **Set API Key** (must match server)
5. **Test Connection**

---

## Step 4: Remote Laptop Control (Optional)

To control your laptop when it's ON (but you're away):

### On Your Laptop
```bash
# Install ngrok for tunnel
choco install ngrok  # Windows
brew install ngrok   # Mac

# Start JARVIS locally
python run.py

# Create tunnel
ngrok http 8000
```

### On Cloud Server
Set environment variable:
```
JARVIS_REMOTE_AGENT_URL=https://abc123.ngrok.io
```

Now the cloud server proxies commands to your laptop!

---

## Cloud AI Options

Since GitHub Copilot CLI requires local `gh` installation, for cloud use:

### Option 1: OpenAI API
```env
JARVIS_LLM_PROVIDER=openai
OPENAI_API_KEY=sk-your-key
```

### Option 2: Anthropic Claude
```env
JARVIS_LLM_PROVIDER=anthropic
ANTHROPIC_API_KEY=sk-ant-your-key
```

### Option 3: Self-hosted Ollama
Deploy Ollama on a GPU server:
```env
JARVIS_OLLAMA_HOST=https://your-ollama-server.com
```

---

## Cost Breakdown

| Service | Free Tier | Paid |
|---------|-----------|------|
| Railway | 500 hours/month | $5/month |
| Render | 750 hours/month | $7/month |
| Neon (DB) | 0.5GB storage | $19/month |
| Upstash (Redis) | 10k commands/day | $0.2/100k |
| OpenAI | Pay-per-use | ~$0.01/request |

**Estimated Monthly Cost: $0-15** (depending on usage)

---

## Quick Start Commands

```bash
# 1. Deploy to Railway
railway login
railway link
railway up

# 2. Build APK
cd Frontend
eas build -p android --profile preview

# 3. Update app config
# Open app → Settings → Backend URL → paste Railway URL
```

---

## Troubleshooting

### "Connection Failed" on Phone
- Check if cloud server is running: `curl https://your-url.railway.app/`
- Verify API key matches
- Check phone has internet

### "AI Not Available"
- Cloud doesn't have `gh` CLI
- Switch to OpenAI/Anthropic provider
- Or deploy Ollama separately

### Build Failed
```bash
# Clear cache and rebuild
eas build:cancel
eas build -p android --clear-cache
```
