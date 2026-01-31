# Voice Agent with Streaming Progress

Real-time voice assistant that speaks **progress updates** while working on complex tasks.

## What's Different?

Instead of generic "Still working..." messages, this agent:
1. **Streams** the response from Clawdbot Gateway using SSE
2. **Announces tool calls** as they happen ("Searching memory...", "Checking calendar...")
3. **Speaks progress** from the response ("Found 3 results, analyzing...")
4. **Delivers the final answer** when done

### Example Flow

```
You: "What did we work on yesterday?"

Agent: "On it, let me dig into that."
Agent: "Searching memory..."           ← Tool call detected
Agent: "Found 3 results, analyzing..."  ← Progress from response
Agent: "Yesterday you worked on the    ← Final answer
        voice agent streaming feature 
        and fixed the LiveKit config."
```

## Architecture

```
┌─────────────────┐     SSE Stream      ┌──────────────────┐
│  Voice Agent    │◄────────────────────│ Clawdbot Gateway │
│  (LiveKit)      │                     │ (Opus + Tools)   │
├─────────────────┤                     ├──────────────────┤
│ Tool call?      │ → Speak tool name   │ memory_search    │
│ Progress line?  │ → Speak progress    │ web_fetch        │
│ Final answer?   │ → Speak result      │ exec             │
└─────────────────┘                     └──────────────────┘
```

## Setup

```bash
# Clone and install
cd voice-agent-streaming
pip install -r requirements.txt

# Configure
cp .env.example .env
# Edit .env with your credentials

# Run
python src/agent.py dev
```

## Configuration

| Variable | Description |
|----------|-------------|
| `AGENT_NAME` | Name for the assistant (default: "Voice Assistant") |
| `USER_NAME` | User's name for personalized greetings |
| `CLAWDBOT_GATEWAY_URL` | Your Clawdbot Gateway endpoint |
| `CLAWDBOT_GATEWAY_TOKEN` | Auth token for the gateway |

## Tool Progress Mapping

The agent announces these tools when detected:

| Tool | Spoken Progress |
|------|-----------------|
| `memory_search` | "Searching my memory..." |
| `web_search` | "Searching the web..." |
| `exec` | "Running a command..." |
| `browser` | "Checking the browser..." |
| `Read` | "Reading a file..." |

Add more in `TOOL_DESCRIPTIONS` dict.

## How It Works

1. User asks a complex question
2. Fast LLM (gpt-5.2) decides to call `deep_think`
3. Agent says "On it, let me dig into that"
4. `_think_with_progress()` opens SSE stream to Gateway
5. As stream delivers events:
   - Tool calls → speak tool description
   - Progress markers → speak progress line
   - Content accumulates → speak final answer
6. Agent speaks the complete answer

## Extending

### Custom Progress Phrases

Edit `TOOL_DESCRIPTIONS` in `agent.py`:

```python
TOOL_DESCRIPTIONS = {
    "my_custom_tool": "Doing something cool...",
    # ...
}
```

### Progress Detection

The agent looks for progress markers in responses:
- Lines containing "found", "searching", "checking", "analyzing"
- Lines ending with "..."
- Short lines (< 80 chars)

Tune this in `_think_with_progress()`.
