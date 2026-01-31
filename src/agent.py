"""LiveKit Voice Agent - SSE streaming for voice progress updates"""
import os
import asyncio
import httpx
import json
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import logging
from typing import AsyncGenerator

load_dotenv(Path(__file__).parent.parent / ".env")

from livekit.agents import AutoSubscribe, JobContext, JobProcess, WorkerOptions, cli, llm
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, elevenlabs, silero, openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

GATEWAY_URL = os.getenv("CLAWDBOT_GATEWAY_URL", "http://127.0.0.1:18789")
GATEWAY_TOKEN = os.getenv("CLAWDBOT_GATEWAY_TOKEN", "")

# Agent configuration (customizable via env)
AGENT_NAME = os.getenv("AGENT_NAME", "Voice Assistant")
USER_NAME = os.getenv("USER_NAME", "")

_session: AgentSession = None
_busy = False

# Tool name → spoken description mapping
TOOL_DESCRIPTIONS = {
    "memory_search": "Searching my memory...",
    "memory_get": "Reading from notes...",
    "web_search": "Searching the web...",
    "web_fetch": "Fetching that page...",
    "exec": "Running a command...",
    "Read": "Reading a file...",
    "read": "Reading a file...",
    "Write": "Writing to a file...",
    "browser": "Checking the browser...",
    "message": "Sending a message...",
    "cron": "Checking schedules...",
    "nodes": "Checking devices...",
    "sessions_list": "Looking at sessions...",
    "sessions_history": "Checking chat history...",
    "image": "Analyzing an image...",
}

# Progress phrases for result counts
RESULT_PHRASES = [
    "Found {count} results...",
    "Got {count} items...",
    "Found {count} matches...",
]


def get_context(user_name: str = "") -> str:
    """Generate context instructions based on config."""
    greeting_name = f" {user_name}" if user_name else ""
    return f"""You are {AGENT_NAME}, a fast and helpful voice assistant.

VOICE STYLE:
- 1-2 sentences MAX
- Casual, conversational, fast
- Sound like a friendly human, not a robot

YOUR DEEP BRAIN (via deep_think tool) CAN:
- Search memory and past conversations
- Read/write files and code
- Run shell commands
- Check GitHub, Google services, Strava, Instagram
- Search the web, control browser
- Monitor LiveKit rooms
- Notion, Slack, and more

WHEN TO USE deep_think:
- Questions needing memory, files, APIs, or web
- "What did we work on?" / "Check my calendar" / "Search for X"

WHEN NOT TO USE deep_think:
- Simple chat, greetings, small talk
- Things you can answer from context

Call deep_think ONCE per topic. Say "Let me check..." then chat while waiting."""


async def parse_sse_stream(response: httpx.Response) -> AsyncGenerator[dict, None]:
    """Parse Server-Sent Events from streaming response."""
    buffer = ""
    async for chunk in response.aiter_text():
        buffer += chunk
        while "\n\n" in buffer:
            event, buffer = buffer.split("\n\n", 1)
            for line in event.split("\n"):
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        return
                    try:
                        yield json.loads(data)
                    except json.JSONDecodeError:
                        continue


async def _think_with_progress(q: str):
    """Route to Clawdbot with streaming progress updates."""
    global _session, _busy
    logger.info(f"🧠 Thinking: {q[:50]}...")
    
    now = datetime.now()
    date_str = now.strftime("%A, %d %B %Y")
    
    # Prompt that encourages progress markers
    voice_prompt = f"""IMPORTANT: This response will be READ ALOUD via text-to-speech.
Today is {date_str}. Use this for relative dates.

PROGRESS INSTRUCTIONS:
When you start a tool/search, emit a brief progress line like:
- "Searching memory..."
- "Found 3 results, analyzing..."
- "Checking calendar..."

Then give your final answer in 2-3 casual spoken sentences MAX.
No lists, bullets, markdown, or technical formatting.
Sound like a friendly human chatting.

User's question: {q}"""
    
    spoken_tools = set()  # Track tools we've announced
    full_response = ""
    last_spoken_progress = None
    
    try:
        async with httpx.AsyncClient(timeout=180) as client:
            async with client.stream(
                "POST",
                f"{GATEWAY_URL}/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {GATEWAY_TOKEN}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": "clawdbot:main",
                    "messages": [{"role": "user", "content": voice_prompt}],
                    "stream": True,
                },
            ) as response:
                if response.status_code != 200:
                    error_text = await response.aread()
                    logger.error(f"Gateway {response.status_code}: {error_text[:200]}")
                    if _session:
                        await _session.say("Sorry, ran into an issue with that.")
                    return
                
                async for event in parse_sse_stream(response):
                    # Check for tool calls in delta
                    choices = event.get("choices", [])
                    if not choices:
                        continue
                    
                    delta = choices[0].get("delta", {})
                    
                    # Handle tool calls - announce what we're doing
                    tool_calls = delta.get("tool_calls", [])
                    for tc in tool_calls:
                        func = tc.get("function", {})
                        tool_name = func.get("name", "")
                        
                        if tool_name and tool_name not in spoken_tools:
                            spoken_tools.add(tool_name)
                            progress_msg = TOOL_DESCRIPTIONS.get(
                                tool_name, 
                                f"Working on {tool_name}..."
                            )
                            logger.info(f"🔧 Tool: {tool_name} → {progress_msg}")
                            
                            # Speak the progress update
                            if _session and _busy:
                                await _session.say(progress_msg)
                    
                    # Accumulate content
                    content = delta.get("content", "")
                    if content:
                        full_response += content
                        
                        # Check for progress markers in the response
                        # e.g., "Found 3 results..." or "Searching..."
                        lower = content.lower()
                        if any(marker in lower for marker in ["found", "searching", "checking", "analyzing"]):
                            # Only speak if it's a new progress line
                            lines = full_response.strip().split("\n")
                            last_line = lines[-1] if lines else ""
                            if last_line and last_line != last_spoken_progress and len(last_line) < 80:
                                # Check if it looks like a progress update (short, ends with ...)
                                if "..." in last_line or any(w in last_line.lower() for w in ["found", "got", "checking"]):
                                    last_spoken_progress = last_line
                                    logger.info(f"📢 Progress: {last_line}")
                                    if _session and _busy:
                                        await _session.say(last_line)
                
                # Speak final result (skip progress lines we already spoke)
                if full_response.strip():
                    # Get the last substantial part (after progress updates)
                    final_answer = full_response.strip()
                    
                    # If we spoke progress, try to get just the conclusion
                    if last_spoken_progress and last_spoken_progress in final_answer:
                        final_answer = final_answer.split(last_spoken_progress)[-1].strip()
                    
                    if final_answer and _session:
                        logger.info(f"🎤 Final: {final_answer[:100]}...")
                        await _session.say(final_answer)
                else:
                    logger.warning("Empty response from gateway")
                    if _session:
                        await _session.say("Hmm, didn't get anything back on that.")
                        
    except httpx.TimeoutException:
        logger.error("Gateway timeout")
        if _session:
            await _session.say("That's taking too long, let me try again later.")
    except Exception as e:
        logger.error(f"Think error: {e}")
        if _session:
            await _session.say("Had trouble with that one.")
    finally:
        _busy = False


@llm.function_tool
async def deep_think(question: str) -> str:
    """Route to Opus for: memory, files, code, APIs (Strava/Instagram/Google/GitHub), web search, browser. Call ONCE per topic."""
    global _busy
    if _busy:
        return "Still working on the last one, give me a sec."
    _busy = True
    asyncio.create_task(_think_with_progress(question))
    return "On it, let me dig into that."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    global _session
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    p = await ctx.wait_for_participant()
    logger.info(f"Participant: {p.identity}")

    greeting = f"Hey{' ' + USER_NAME if USER_NAME else ''}!"
    
    agent = Agent(
        instructions=get_context(USER_NAME),
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM(model="gpt-5.2-chat-latest", max_completion_tokens=512),
        tts=elevenlabs.TTS(
            voice_id=os.getenv("ELEVENLABS_VOICE_ID", "xvbIPX7VE9oYkosnkbGT"),
            model="eleven_turbo_v2_5",
        ),
        tools=[deep_think],
    )

    _session = AgentSession()
    await _session.start(agent, room=ctx.room)
    logger.info(f"Ready! Agent: {AGENT_NAME}")
    await _session.say(greeting)
    await asyncio.Event().wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
