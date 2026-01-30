# 🎙️ LiveKit Voice Agent for Clawdbot

Real-time voice interface that routes through Clawdbot Gateway, maintaining full session context, memory, and tool access.

## Architecture

```
┌─────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   Browser   │────▶│  LiveKit Server │────▶│  Voice Agent    │
│  (WebRTC)   │◀────│   (Chumo SFU)   │◀────│  (Python)       │
└─────────────┘     └─────────────────┘     └────────┬────────┘
                                                     │
                    ┌─────────────────┐              │
                    │  Clawdbot       │◀─────────────┘
                    │  Gateway        │  HTTP API
                    │  (Sessions,     │
                    │   Memory, Tools)│
                    └─────────────────┘
```

**Pipeline:**
1. **VAD** (Silero) - Detects when user is speaking
2. **STT** (Deepgram Nova-2) - Transcribes speech to text
3. **LLM** (Clawdbot Gateway) - Processes with full context
4. **TTS** (ElevenLabs Turbo) - Speaks the response

## Quick Start

### 1. Install Dependencies

```bash
cd livekit-voice-agent
python -m venv venv
source venv/bin/activate  # or `venv\Scripts\activate` on Windows
pip install -r requirements.txt
pip install livekit-api  # For token generation
```

### 2. Configure Environment

```bash
cp .env.example .env
# Edit .env with your credentials
```

**Required credentials:**

| Service | Get from |
|---------|----------|
| LiveKit | [livekit.cloud](https://cloud.livekit.io) or Chumo's server |
| Deepgram | [console.deepgram.com](https://console.deepgram.com) |
| ElevenLabs | [elevenlabs.io](https://elevenlabs.io) |
| Clawdbot | Your local Gateway (`clawdbot status`) |

### 3. Get Clawdbot Gateway Token

```bash
# Check your Clawdbot config for the API token
cat ~/.config/clawdbot/config.yaml | grep -A2 api:
```

### 4. Run the Agent

**Development mode** (auto-reload):
```bash
python -m livekit.agents.cli dev --entrypoint src.agent:entrypoint
```

**Production mode:**
```bash
python -m livekit.agents.cli start --entrypoint src.agent:entrypoint
```

### 5. Test It

Generate a test token:
```bash
python scripts/create_token.py badgeroo-voice armand
```

This outputs a URL you can open in your browser to join the room with audio.

## Configuration

### Session Keys

By default, the agent creates a session key per participant:
```
agent:voice:{participant_identity}
```

For shared context (same memory across all callers):
```bash
CLAWDBOT_SESSION_KEY=agent:voice:shared
```

### Voice Selection

Find ElevenLabs voice IDs at [elevenlabs.io/voices](https://elevenlabs.io/voices):

```bash
# Example voices
ELEVENLABS_VOICE_ID=pNInz6obpgDQGcFmaJgB  # Adam (default)
ELEVENLABS_VOICE_ID=21m00Tcm4TlvDq8ikWAM  # Rachel
ELEVENLABS_VOICE_ID=your-cloned-voice-id   # Custom clone
```

### Deepgram Models

```python
# In src/agent.py, modify STT config:
stt=deepgram.STT(
    model="nova-2",        # Best quality
    # model="nova-2-general",  # Faster
    language="en",
    # language="multi",    # Auto-detect language
)
```

## Using with Chumo

If you're running this with Chumo's LiveKit infrastructure:

1. **Use Chumo's LiveKit credentials** in `.env`
2. **Configure dispatch rules** so the agent joins specific rooms:
   - Room name pattern: `voice-*`
   - Or room metadata: `{"agent": "badgeroo"}`

3. **Optional: Add to Chumo UI** - Create a "Talk to Badgeroo" button that:
   - Creates a room with the right metadata
   - Generates a token for the user
   - Opens the WebRTC connection

## Extending

### Custom System Prompt

The Clawdbot session inherits its system prompt from the Gateway config. To customize for voice:

1. Create a dedicated agent in `config.yaml`:
```yaml
agents:
  voice:
    model: claude-sonnet-4-5
    systemPrompt: |
      You are Badgeroo, a voice assistant. Keep responses concise 
      and conversational - you're speaking, not writing.
      Aim for 1-2 sentences per response unless more detail is needed.
```

2. Update the session key:
```bash
CLAWDBOT_SESSION_KEY=agent:voice
```

### Adding Wake Word

For "Hey Badgeroo" activation, add a wake word detector:

```python
from livekit.plugins import silero

# Add to assistant config:
wake_word=silero.WakeWord(
    wake_words=["hey badgeroo", "badgeroo"],
    threshold=0.5,
)
```

### Function Calling

The Clawdbot Gateway handles all tool execution. The voice agent automatically has access to:
- Web search
- File operations
- Browser control
- Calendar/email (if configured)
- Everything in your Clawdbot setup

## Troubleshooting

### "Connection refused" to Gateway
```bash
# Check Gateway is running
clawdbot status

# Check the port
curl http://localhost:3033/health
```

### High latency
1. Use `eleven_turbo_v2_5` for TTS (fastest)
2. Enable Deepgram interim results
3. Reduce `min_endpointing_delay`
4. Use a closer LiveKit region

### Interruption not working
Adjust these in `VoiceAssistant`:
```python
interrupt_speech_duration=0.3,  # Lower = more sensitive
interrupt_min_words=1,          # Lower = more sensitive
```

## License

MIT - Part of the Clawdbot ecosystem.
