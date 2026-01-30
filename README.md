# 🦡 Badgeroo Voice Agent

Two-step voice architecture: **instant responses** + **deep thinking**.

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────────────────────┐
│   Browser   │────▶│  LiveKit Cloud  │────▶│  Voice Agent                    │
│  (WebRTC)   │◀────│                 │◀────│                                 │
└─────────────┘     └─────────────────┘     │  ┌───────────────────────────┐  │
                                            │  │ gpt-5.2-chat-latest       │  │
                                            │  │ (instant voice responses) │  │
                                            │  └─────────────┬─────────────┘  │
                                            │                │                │
                                            │         deep_think()            │
                                            │                │                │
                                            │  ┌─────────────▼─────────────┐  │
                                            │  │ Clawdbot Gateway → Opus   │  │
                                            │  │ (tools, memory, code,     │  │
                                            │  │  web, APIs, files)        │  │
                                            │  └───────────────────────────┘  │
                                            └─────────────────────────────────┘
```

### Two-Step Flow

1. **Fast Layer** (gpt-5.2-chat-latest)
   - Instant voice responses
   - Handles greetings, simple questions, conversation
   - Decides when to call `deep_think`

2. **Deep Layer** (Opus via Clawdbot Gateway)
   - Complex tasks: code, files, memory, research
   - Full tool access: Strava, Instagram, Google, GitHub, web search, browser
   - Returns voice-friendly responses (prompted for casual speech)
   - Includes current date for correct relative references

### Pipeline

| Component | Service | Purpose |
|-----------|---------|---------|
| VAD | Silero | Detects speech |
| STT | Deepgram Nova-2 | Speech → Text |
| LLM (fast) | gpt-5.2-chat-latest | Instant responses |
| LLM (deep) | Opus via Gateway | Tools & memory |
| TTS | ElevenLabs Turbo v2.5 | Text → Speech |

## Quick Start

### 1. Install

```bash
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Configure

```bash
cp .env.example .env
```

Edit `.env`:
```bash
LIVEKIT_URL=wss://your-project.livekit.cloud
LIVEKIT_API_KEY=your-api-key
LIVEKIT_API_SECRET=your-api-secret

DEEPGRAM_API_KEY=your-deepgram-key
ELEVENLABS_API_KEY=your-elevenlabs-key
ELEVENLABS_VOICE_ID=your-voice-id
OPENAI_API_KEY=your-openai-key

CLAWDBOT_GATEWAY_URL=http://127.0.0.1:18789
CLAWDBOT_GATEWAY_TOKEN=your-gateway-token
```

### 3. Run

```bash
# Connect to a specific room
python src/agent.py connect --room my-room

# Or dev mode (auto-dispatch)
python src/agent.py dev
```

### 4. Join

Generate a token:
```bash
lk token create --identity user --room my-room --join --create
```

Open in browser:
```
https://meet.livekit.io/custom?liveKitUrl=wss://your-project.livekit.cloud&token=YOUR_TOKEN
```

## What deep_think Can Do

The fast voice model knows to call `deep_think` for:

- **Memory**: "What did we work on today?"
- **Strava**: "How many km did I run this week?"
- **Instagram**: "How's my latest post doing?"
- **Google**: "What's on my calendar?"
- **GitHub**: "Any open PRs?"
- **Code**: "Write a function that..."
- **Files**: "Check the logs for errors"
- **Web**: "Search for..."
- **Browser**: "Go to..."

## Progress Updates

While Opus thinks, the voice agent keeps you updated:
- "Still digging into that..."
- "Working on it, almost there..."
- "Just a bit more..."

## Customization

### Voice

Find voices at [elevenlabs.io/voices](https://elevenlabs.io/voices):
```bash
ELEVENLABS_VOICE_ID=your-voice-id
```

### Context

Edit the `CONTEXT` string in `src/agent.py` to customize:
- Who the assistant is
- What it knows about the user
- When to use deep_think

## License

MIT - Part of the LiveLabs ecosystem.
