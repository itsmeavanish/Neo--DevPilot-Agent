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

## GitHub Actions Automated Deployment

You can automate deployments using GitHub Actions.

### Deploying to Render via GitHub Actions

1. In your Render Dashboard, go to your Web Service settings and find the **Deploy Hook** URL.
2. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**.
3. Create a new repository secret:
   - Name: `RENDER_DEPLOY_HOOK_URL`
   - Secret: (Paste the Deploy Hook URL from Render)
4. The workflow in `.github/workflows/deploy-render.yml` will automatically trigger a deployment whenever you push to the `main` branch.

### Deploying to Fly.io via GitHub Actions

1. Generate a Fly API token by running:
   ```bash
   fly tokens create deploy -x 999999h
   ```
2. Go to your GitHub repository → **Settings** → **Secrets and variables** → **Actions**.
3. Create a new repository secret:
   - Name: `FLY_API_TOKEN`
   - Secret: (Paste the token generated in step 1)
4. The workflow in `.github/workflows/deploy-fly.yml` will automatically deploy your app using `flyctl` whenever you push to the `main` branch.

## Custom Domain via GitHub Student Developer Pack

If you have the [GitHub Student Developer Pack](https://education.github.com/pack), you can get a free custom domain (e.g., from Namecheap, Name.com, or .tech domains). Note that **GitHub Pages cannot host a Python backend**, so you must host the backend on Render, Fly.io, or DigitalOcean, and then point your custom domain to that service.

### 1. Claim Your Free Domain
1. Go to the [GitHub Student Developer Pack](https://education.github.com/pack) and authenticate.
2. Find the offer for **Namecheap** (.me), **Name.com**, or **.tech domains**.
3. Follow their instructions to register your free domain name.

### 2. Connect Custom Domain to Render
1. In your Render Dashboard, select your Web Service.
2. Go to **Settings** → scroll down to **Custom Domains**.
3. Click **Add Custom Domain** and enter your new domain (e.g., `api.yourdomain.com`).
4. Render will provide a DNS record to add (usually a `CNAME` pointing to `your-app.onrender.com`).
5. Go to your domain registrar's DNS settings (Namecheap/Name.com/.tech) and add the `CNAME` record provided by Render.

### 3. Connect Custom Domain to Fly.io
1. In your terminal, add the certificate for your custom domain:
   ```bash
   fly certs add api.yourdomain.com
   ```
2. Run `fly ips list` to get the IPv4 and IPv6 addresses for your app.
3. Go to your domain registrar's DNS settings and add:
   - An `A` record pointing to the IPv4 address.
   - An `AAAA` record pointing to the IPv6 address.
4. Run `fly certs show api.yourdomain.com` to check the status of your SSL certificate.

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
