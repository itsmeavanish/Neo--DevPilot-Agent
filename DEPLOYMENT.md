# Deployment Guide

## Option 1: ngrok (Simplest)

```bash
# Terminal 1: Start server
python run.py

# Terminal 2: Expose publicly
ngrok http 8000
```

Copy the ngrok URL and update `Frontend/lib/config.ts`.

## Option 2: Render (Free Cloud)

1. Push to GitHub
2. Go to [render.com](https://render.com)
3. New → Web Service → Connect repo
4. Settings:
   - Environment: Docker
   - Dockerfile: `Dockerfile.cloud`
5. Add env vars:
   ```
   JARVIS_API_KEY=your-key
   OPENAI_API_KEY=sk-...
   ```

## Option 3: Fly.io

```bash
fly auth login
fly launch
fly deploy
```

## Build APK

```bash
cd Frontend
npm install -g eas-cli
eas login
eas build --platform android --profile preview --local
```

## Environment Variables

| Variable | Description |
|----------|-------------|
| `JARVIS_API_KEY` | API authentication key |
| `JARVIS_LLM_PROVIDER` | `ollama`, `openai`, or `copilot` |
| `OPENAI_API_KEY` | OpenAI API key (if using) |
