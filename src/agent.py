"""LiveKit Voice Agent - gpt-5.2-chat-latest with full context + deep_think"""
import os
import asyncio
import httpx
from pathlib import Path
from datetime import datetime
from dotenv import load_dotenv
import logging

load_dotenv(Path(__file__).parent.parent / ".env")

from livekit.agents import AutoSubscribe, JobContext, JobProcess, WorkerOptions, cli, llm
from livekit.agents.voice import Agent, AgentSession
from livekit.plugins import deepgram, elevenlabs, silero, openai

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("voice-agent")

GATEWAY_URL = os.getenv("CLAWDBOT_GATEWAY_URL", "http://127.0.0.1:18789")
GATEWAY_TOKEN = os.getenv("CLAWDBOT_GATEWAY_TOKEN", "")

_session: AgentSession = None
_busy = False

CONTEXT = """You are Badgeroo 🦡, Armand's voice assistant at LiveLabs Ventures.

ABOUT ARMAND:
- Founder of LiveLabs Ventures, Cape Town
- Building StreamBridge (multi-camera streaming) and real-time video products
- Ultra runner: Hardrock 100, UTCT 100km
- Ex-CTO Hornet Networks (30M users)

VOICE STYLE:
- 1-2 sentences MAX
- Casual, conversational, fast

YOUR DEEP BRAIN (via deep_think tool) CAN:
- Read/write files and code
- Search memory and past conversations
- Run shell commands
- Check GitHub issues and PRs
- Access Google services (Gmail, Calendar, Drive)
- Check Strava running stats
- Check Instagram posts/engagement
- Monitor LiveKit rooms
- Generate images
- Deploy to Google Cloud
- Search the web
- Control browser automation

WHEN TO USE deep_think:
- "What did we work on?" → deep_think (needs memory)
- "Check my Strava" → deep_think (needs API)
- "What's in my calendar?" → deep_think (needs Google)
- "How many viewers in the stream?" → deep_think (LiveKit)
- "Write some code for X" → deep_think (needs files)
- "Search for X" → deep_think (web search)

WHEN NOT TO USE deep_think:
- Simple chat/questions you can answer from context
- Greetings, small talk
- Things in your context above

Call deep_think ONCE per topic. Say "Let me check..." then chat while waiting."""


async def _progress_updates():
    """Send progress updates while thinking"""
    updates = [
        "Still digging into that...",
        "Working on it, almost there...",
        "Just a bit more...",
    ]
    for i, msg in enumerate(updates):
        await asyncio.sleep(8)  # Every 8 seconds
        if _busy and _session:
            await _session.say(msg)
        else:
            break


async def _think(q: str):
    global _session, _busy
    logger.info(f"🧠 Thinking: {q[:50]}...")
    
    # Start progress updates in background
    progress_task = asyncio.create_task(_progress_updates())
    
    # Wrap question with voice-friendly instructions + current date
    now = datetime.now()
    date_str = now.strftime("%A, %d %B %Y")  # e.g. "Thursday, 30 January 2026"
    
    voice_prompt = f"""IMPORTANT: This response will be READ ALOUD via text-to-speech.
Today's date is {date_str}. Use this for any relative date references (last year = {now.year - 1}, this year = {now.year}).
Reply in 2-3 casual spoken sentences MAX. No lists, bullets, markdown, or technical formatting.
Sound like a friendly human chatting, not a robot reading documentation.

User's question: {q}"""
    
    try:
        async with httpx.AsyncClient(timeout=120) as c:
            r = await c.post(f"{GATEWAY_URL}/v1/chat/completions",
                headers={"Authorization": f"Bearer {GATEWAY_TOKEN}", "Content-Type": "application/json"},
                json={"model": "clawdbot:main", "messages": [{"role": "user", "content": voice_prompt}]})
            if r.status_code == 200:
                ans = r.json().get("choices", [{}])[0].get("message", {}).get("content", "")
                logger.info(f"🧠 Got: {ans[:100]}...")
                
                if _session:
                    await _session.say(ans)
            else:
                logger.error(f"Gateway {r.status_code}: {r.text[:100]}")
                if _session:
                    await _session.say("Sorry, ran into an issue getting that.")
    except Exception as e:
        logger.error(f"Think error: {e}")
        if _session:
            await _session.say("Had trouble with that request.")
    finally:
        _busy = False
        progress_task.cancel()


@llm.function_tool
async def deep_think(question: str) -> str:
    """Route to Opus agent for: memory, files, code, APIs (Strava/Instagram/Google/GitHub), 
    web search, browser, shell commands, image gen, deployments. Call ONCE per topic."""
    global _busy
    if _busy:
        return "Still working on the last request."
    _busy = True
    asyncio.create_task(_think(question))
    return "Checking that now, one sec."


def prewarm(proc: JobProcess):
    proc.userdata["vad"] = silero.VAD.load()


async def entrypoint(ctx: JobContext):
    global _session
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)
    p = await ctx.wait_for_participant()
    logger.info(f"Participant: {p.identity}")

    agent = Agent(
        instructions=CONTEXT,
        vad=ctx.proc.userdata["vad"],
        stt=deepgram.STT(model="nova-2"),
        llm=openai.LLM(model="gpt-5.2-chat-latest"),
        tts=elevenlabs.TTS(voice_id=os.getenv("ELEVENLABS_VOICE_ID", "xvbIPX7VE9oYkosnkbGT"), model="eleven_turbo_v2_5"),
        tools=[deep_think],
    )

    _session = AgentSession()
    await _session.start(agent, room=ctx.room)
    await _session.say("Hey Armand, what's up?")
    await asyncio.Event().wait()


if __name__ == "__main__":
    cli.run_app(WorkerOptions(entrypoint_fnc=entrypoint, prewarm_fnc=prewarm))
