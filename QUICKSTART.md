# JARVIS Quick Start Guide

This guide explains how to run the JARVIS backend and the mobile frontend together.

## Prerequisites

- Python 3.11+
- Node.js 18+ and npm
- Expo CLI (`npm install -g expo-cli` or use npx)
- Expo Go app on your phone (from App Store / Play Store)

## Step 1: Start the Backend

### Option A: Direct Python (Recommended for Development)

```bash
# Navigate to project root
cd c:\Users\7CIN\Desktop\Jarvis

# Install dependencies (first time only)
pip install -r src/requirements.txt

# Start the backend server
python run.py
```

The backend will start at:

- API: http://localhost:8000
- Docs: http://localhost:8000/docs

### Option B: Using Docker

```bash
# Make sure Docker Desktop is running first!

# Start all services (backend + PostgreSQL + Redis)
docker-compose up -d

# View logs
docker-compose logs -f jarvis
```

## Step 2: Configure Frontend API URL

### For Web/Emulator (localhost works)

The default config should work. No changes needed.

### For Physical Device (Expo Go)

You need to update the API URL to your computer's IP address.

1. Find your computer's IP:
   - Windows: Run `ipconfig` in terminal, look for IPv4 Address
   - Mac/Linux: Run `ifconfig` or `ip addr`

2. Edit `Frontend/lib/api.ts`:
   ```typescript
   export const API_CONFIG = {
     baseUrl: "http://YOUR_IP:8000", // e.g., http://192.168.1.100:8000
     apiKey: "", // Leave empty for development
   };
   ```

## Step 3: Start the Frontend

```bash
# Navigate to Frontend directory
cd c:\Users\7CIN\Desktop\Jarvis\Frontend

# Install dependencies (first time only)
npm install

# Start Expo development server
npx expo start
```

This will show a QR code. Scan it with:

- **iOS**: Camera app, then tap the notification
- **Android**: Expo Go app, tap "Scan QR Code"

## Quick Commands Summary

```bash
# Terminal 1: Backend
cd c:\Users\7CIN\Desktop\Jarvis
python run.py

# Terminal 2: Frontend
cd c:\Users\7CIN\Desktop\Jarvis\Frontend
npx expo start
```

## Troubleshooting

### "Network request failed" on phone

1. Make sure your phone and computer are on the same WiFi network
2. Update `API_CONFIG.baseUrl` in `Frontend/lib/api.ts` to your computer's IP
3. Make sure Windows Firewall allows incoming connections on port 8000

### Backend won't start

```bash
# Check if port 8000 is in use
netstat -ano | findstr :8000

# Install missing dependencies
pip install -r src/requirements.txt
```

### Expo issues

```bash
# Clear Expo cache
npx expo start --clear

# Reinstall node_modules
rm -rf node_modules
npm install
```

## Features Available

Once connected, you can:

- **Chat Tab**: Send commands, ask AI questions, interact with JARVIS agent
- **IDE Tab** (NEW!): Full IDE experience with:
  - **File Explorer**: Browse your project folders and open files
  - **Code Editor**: View file contents with syntax highlighting
  - **Terminal**: Execute shell commands and see live output
  - **Copilot Chat**: Ask GitHub Copilot or Ollama AI for code help
  - **Project Navigation**: Switch between folders and see file structure
- **Files Tab**: Browse files on your computer
- **Terminal Tab**: Execute shell commands remotely
- **Analytics Tab**: View system metrics (CPU, RAM, Disk)
- **Settings Tab**: Check connection status and configure AI provider

## IDE Tab Guide

### How to Use the IDE

1. **Open IDE Tab**: Tap the 💻 "IDE" icon in the bottom navigation

2. **Navigate Projects**:
   - Tap the folder path at the top to change directory
   - You'll see a list of files and folders on the left sidebar
   - Tap any folder to navigate into it
   - Tap the up arrow to go to parent folder

3. **View Code**:
   - Tap any file to open it in the editor (center panel)
   - Code is displayed with syntax highlighting based on file type
   - Use the copy button to copy file contents

4. **Run Commands**:
   - Type commands in the Terminal section (bottom)
   - Examples:
     ```
     npm start
     git status
     python script.py
     ```
   - See live output as commands execute

5. **Get Code Help**:
   - Type in the "Copilot" chat panel (right side)
   - Start with `/copilot` for GitHub Copilot suggestions
   - Otherwise, ask Ollama AI for explanations
   - Examples:
     ```
     /copilot how do I fix this TypeScript error?
     explain what this function does
     how to optimize this code?
     ```

### IDE Layout

```
┌─────────────────────────────────────────────┐
│ Folder Path    [up] [refresh]              │
├──────┬──────────────────────────┬───────────┤
│      │  📄 File Editor          │ Copilot   │
│Files │  ┌──────────────────────┐│ Chat      │
│ side │  │ code content...      ││ ────────  │
│ bar  │  │ ...                  ││ messages  │
│      │  └──────────────────────┘│ ────────  │
│      ├──────────────────────────┤ input    │
│      │ Terminal $ output...     │           │
│      │ $ your-command-here      │           │
└──────┴──────────────────────────┴───────────┘
```

### Example Workflow

1. Navigate to your project:
   ```
   Tap folder path → Enter: C:\Users\7CIN\Desktop\Jarvis
   ```

2. Open a file:
   ```
   Tap "run.py" from file list
   ```

3. Ask about it:
   ```
   In Copilot chat: "what does this script do?"
   ```

4. Make a change and test:
   ```
   In Terminal: "python run.py" to run it
   ```

5. Check git status:
   ```
   In Terminal: "git status"
   ```

## Docker Commands Reference

```bash
# Start services
docker-compose up -d

# Stop services
docker-compose down

# View logs
docker-compose logs -f

# Rebuild after code changes
docker-compose up -d --build

# Clean everything
docker-compose down -v
```

---

**Enjoy using JARVIS!**
